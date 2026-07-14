"""Baseline evaluation harness -- stage 1: generation.

Runs each evals/golden_set.json row through backend.agent.build_graph()
in-process (the same function backend.api's /api/chat calls per
request) -- fresh thread_id per run, N runs per row per the approved
protocol below. Captures the full graph state (answer, retrieved
rule/web contexts, judge verdict, tool calls, token usage, latency) to
a resumable append-only JSONL: on restart, any (id, run_index) pair
already present in --out is skipped.

Read-only against the golden set and the frozen agent pipeline -- this
script only invokes backend.agent.build_graph() unchanged and observes
its output. No prompt, tool, retrieval, or judge code is touched here.

Requires a local LiteLLM gateway already running (backend.agent
defaults LITELLM_PROXY_BASE_URL to http://localhost:4000) and
DATABASE_URL/SUPABASE_URL/SUPABASE_SECRET_KEY/TAVILY_API_KEY in the
environment (loaded from the repo-root .env).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.agent import build_graph  # noqa: E402

# N-run protocol approved for this baseline: eval-015/eval-018 are the
# true F2 arithmetic-nondeterminism family (multi-branch formula
# application); eval-033/034/035/047 are grade-ambiguity questions
# where the risk is behavioral variance (did it silently pick one
# grade), not arithmetic -- a lighter N=3 is enough to distinguish
# stable from coin-flip there. Every other row runs once.
N_RUNS_OVERRIDE = {
    "eval-015": 5,
    "eval-018": 5,
    "eval-033": 3,
    "eval-034": 3,
    "eval-035": 3,
    "eval-047": 3,
}


class UsageCollector(BaseCallbackHandler):
    """Non-invasive token accounting via LangChain's public callbacks
    API -- attached through graph.invoke(config=...), not by touching
    backend/agent.py. Captures every underlying LLM call this turn
    (agent_node, judge_node, retry reformulation)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                usage = None
                if msg is not None:
                    usage = getattr(msg, "usage_metadata", None)
                    if not usage:
                        usage = (getattr(msg, "response_metadata", None) or {}).get("token_usage")
                if usage:
                    self.calls.append(dict(usage))

    def totals(self) -> dict:
        input_tokens = sum((c.get("input_tokens") or c.get("prompt_tokens") or 0) for c in self.calls)
        output_tokens = sum((c.get("output_tokens") or c.get("completion_tokens") or 0) for c in self.calls)
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "llm_calls": len(self.calls)}


def _messages_since_last_human(messages: list) -> list:
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i + 1 :]
    return list(messages)


# search_rules_tool joins retrieved chunks with "\n\n", each block starting
# "[Section ...]"; web_search_tool joins results with "\n\n", each block
# starting "[title](url)". Retrieved rule-chunk text itself frequently
# contains internal blank lines (paragraph breaks within one chunk -- see
# docs/submission.md's chunking strategy, 500-800 token chunks), so a naive
# `.split("\n\n")` fragments a single retrieved chunk into many spurious
# contexts. Splitting only at a blank line immediately followed by "[" (a new
# block's header) recovers the tool's actual block boundaries instead.
_BLOCK_BOUNDARY_RE = re.compile(r"\n\n(?=\[)")


def _split_blocks(text: str) -> list[str]:
    return [block.strip() for block in _BLOCK_BOUNDARY_RE.split(text) if block.strip()]


def _extract_tool_contexts(messages: list, tool_name: str, empty_markers: tuple[str, ...]) -> list[str]:
    contexts: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name == tool_name:
            if any(marker in m.content for marker in empty_markers):
                continue
            contexts.extend(_split_blocks(m.content))
    return contexts


# retry_retrieval_node (backend/agent.py) calls backend.retrieval.search_rules
# directly in Python and injects the broadened, reformulated-query results as a
# SystemMessage instruction -- NOT through the ToolNode, so no ToolMessage is
# ever appended for a retry. Any row that triggered a retry would silently lose
# that context from _extract_tool_contexts alone. This marker is the fixed
# sentence retry_retrieval_node always ends its instruction with, verbatim,
# right before the formatted chunks it injects.
_RETRY_CONTEXT_MARKER = (
    "if these excerpts still don't cover it — say so honestly instead.\n\n"
)


def _extract_retry_contexts(messages: list) -> list[str]:
    contexts: list[str] = []
    for m in messages:
        if isinstance(m, SystemMessage) and _RETRY_CONTEXT_MARKER in m.content:
            _, _, tail = m.content.partition(_RETRY_CONTEXT_MARKER)
            if "No matching rule excerpts were found" in tail:
                continue
            contexts.extend(_split_blocks(tail))
    return contexts


def _tools_called(messages: list) -> list[str]:
    tools: list[str] = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            tools.extend(tc["name"] for tc in m.tool_calls)
    return tools


def run_one(row: dict, run_index: int, run_date: str, checkpointer) -> dict:  # noqa: ANN001
    # uuid4 suffix guarantees a fresh thread even if this exact (run_date, id,
    # run_index) is ever re-invoked (e.g. re-running one row after a bugfix,
    # while keeping the same --run-date) -- the Postgres checkpointer persists
    # by thread_id independent of this script's own JSONL resume logic, so
    # without this a re-invocation would replay old conversation state into
    # what should be an independent run. Discovered live: a repeated smoketest
    # invocation under the same run-date silently reused the prior thread.
    thread_id = f"baseline-{run_date}-{row['id']}-run{run_index}-{uuid.uuid4().hex[:8]}"
    graph = build_graph(row["association_id"], checkpointer, grade_scope=row.get("grade_scope"))
    collector = UsageCollector()
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [collector],
        "tags": ["baseline", f"baseline-{run_date}"],
        "metadata": {"golden_set_id": row["id"], "run_index": run_index, "category": row["category"]},
    }

    t0 = time.monotonic()
    error = None
    result = None
    try:
        result = graph.invoke({"messages": [HumanMessage(content=row["question"])]}, config=config)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: log and continue to the next row/run
        error = repr(exc)
    latency = time.monotonic() - t0

    record = {
        "id": row["id"],
        "run_index": run_index,
        "thread_id": thread_id,
        "category": row["category"],
        "expected_behavior": row["expected_behavior"],
        "grade_scope": row.get("grade_scope"),
        "association_id": row["association_id"],
        "source": row.get("source"),
        "question": row["question"],
        "expected_answer": row["expected_answer"],
        "expected_source": row.get("expected_source"),
        "latency_seconds": round(latency, 2),
        "error": error,
    }

    if error is not None or result is None:
        record.update(
            {
                "answer": None,
                "rule_contexts": [],
                "web_contexts": [],
                "tools_called": [],
                "needs_human_review": None,
                "judge_verdict": None,
                "retry_count": None,
                "token_usage": collector.totals(),
            }
        )
        return record

    messages = result["messages"]
    needs_human_review = bool(result.get("needs_human_review", False))
    # Mirrors backend/api.py's own chat() handler exactly: flag_and_finalize_node
    # appends a banner-wrapped AIMessage last when flagged, so messages[-2] is
    # the actual judged draft.
    answer_text = messages[-2].content if needs_human_review else messages[-1].content
    turn_messages = _messages_since_last_human(messages)

    rule_contexts = _extract_tool_contexts(turn_messages, "search_rules_tool", ("No matching rule excerpts",))
    # Dedupe while preserving first-seen order: a retry's broadened search can
    # re-surface the same chunk the original call already retrieved.
    for ctx in _extract_retry_contexts(turn_messages):
        if ctx not in rule_contexts:
            rule_contexts.append(ctx)

    record.update(
        {
            "answer": answer_text,
            "rule_contexts": rule_contexts,
            "web_contexts": _extract_tool_contexts(
                turn_messages, "web_search_tool", ("No current web results", "currently unavailable")
            ),
            "tools_called": _tools_called(turn_messages),
            "needs_human_review": needs_human_review,
            "judge_verdict": result.get("judge_verdict"),
            "retry_count": result.get("retry_count", 0),
            "token_usage": collector.totals(),
        }
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", default=str(REPO_ROOT / "evals" / "golden_set.json"))
    parser.add_argument("--out", required=True, help="output JSONL path (append-only, resumable)")
    parser.add_argument("--run-date", required=True, help="YYYY-MM-DD, used in thread_id and LangSmith tags")
    parser.add_argument("--only", default=None, help="comma-separated golden_set ids, for a partial/sanity run")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    with open(args.golden_set) as f:
        golden_set = json.load(f)

    if args.only:
        wanted = set(args.only.split(","))
        golden_set = [row for row in golden_set if row["id"] in wanted]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done: set[tuple[str, int]] = set()
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                done.add((rec["id"], rec["run_index"]))
        if done:
            print(f"Resuming: {len(done)} (id, run_index) pairs already completed in {out_path}")

    with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        checkpointer.setup()  # idempotent
        with open(out_path, "a") as out_f:
            for row in golden_set:
                n_runs = N_RUNS_OVERRIDE.get(row["id"], 1)
                for run_index in range(n_runs):
                    if (row["id"], run_index) in done:
                        continue
                    print(
                        f"[{row['category']:>20}] {row['id']} run {run_index + 1}/{n_runs} ...",
                        end=" ",
                        flush=True,
                    )
                    record = run_one(row, run_index, args.run_date, checkpointer)
                    out_f.write(json.dumps(record) + "\n")
                    out_f.flush()
                    if record["error"]:
                        status = f"ERROR: {record['error']}"
                    elif record["needs_human_review"]:
                        status = "FLAGGED"
                    else:
                        status = "ok"
                    print(f"{status} ({record['latency_seconds']}s)")


if __name__ == "__main__":
    main()
