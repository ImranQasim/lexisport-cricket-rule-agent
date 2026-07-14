"""Baseline evaluation harness -- stage 2: scoring.

Reads the raw generation JSONL produced by run_baseline.py and scores
each record per the approved plan's category mapping:

- expected_behavior == "answer": Ragas Faithfulness, ContextPrecision,
  ContextRecall, AnswerRelevancy (ragas.metrics.collections, gpt-4o-mini
  + text-embedding-3-small via the local gateway), plus behavior_match
  and judge-vs-Ragas agreement (0.8 faithfulness threshold).
- expected_behavior == "web_answer": AnswerRelevancy only (no rulebook
  ground-truth context exists), plus behavior_match.
- expected_behavior == "honest_fallback": no Ragas metrics. behavior_match
  via a rubric classifier call, plus a hard regex check for invented
  citations (a citation-shaped string in a fallback answer is always a
  fail regardless of the classifier).
- expected_behavior == "flag_acceptable": behavior_match via a
  dedicated acceptance-rubric classifier call, using each row's own
  notes/expected_answer text as the acceptance criterion (did it ask a
  clarifying question or present the relevant branches, rather than
  silently pick one).

This is evals-only scoring logic -- it reads generation output, it
never re-invokes or modifies the agent pipeline.
"""

from __future__ import annotations

# --- Compatibility shim, must run before any `import ragas` -----------------
# ragas==0.4.3 unconditionally imports langchain_community.chat_models.vertexai
# at import time; langchain-community>=0.4 removed that module (moved to the
# standalone langchain-google-vertexai package) but ragas's own import wasn't
# updated for it. We use neither Vertex AI nor langchain-community for
# anything real, so this stubs the module out with the real ChatVertexAI class
# (already installed as a dependency) purely to satisfy ragas's import chain.
# Contained entirely in evals/'s own venv -- does not touch backend/.
import sys
import types

from langchain_google_vertexai import ChatVertexAI

_vertexai_shim = types.ModuleType("langchain_community.chat_models.vertexai")
_vertexai_shim.ChatVertexAI = ChatVertexAI
sys.modules.setdefault("langchain_community.chat_models.vertexai", _vertexai_shim)
# -----------------------------------------------------------------------------

import argparse
import asyncio
import json
import os
import re
import sys as _sys
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel
from ragas.embeddings import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

REPO_ROOT = Path(__file__).resolve().parents[1]
_sys.path.insert(0, str(REPO_ROOT))

RAGAS_MODEL = "gpt-4o-mini"
RAGAS_EMBEDDING_MODEL = "text-embedding-3-small"
FAITHFULNESS_PASS_THRESHOLD = 0.8

# Mirrors backend/api.py's own citation-extraction regex (copied, not
# imported, to keep this scoring script decoupled from the API module's
# import-time side effects like FastAPI app construction). Used only to
# detect whether a supposedly-honest-fallback answer smuggled in a citation.
_RULE_CITATION_RE = re.compile(r"\(Section\s+([\w.]+)(?:,\s*([^)]+))?\)")
_WEB_CITATION_RE = re.compile(r"\(Source:\s*(\S+)\)")


# ---------------------------------------------------------------------------
# Cost tracking: an httpx response hook on the raw AsyncOpenAI client used by
# both ragas' llm_factory/embedding_factory and the two classifier calls
# below. Works at the transport level so it captures usage regardless of
# which higher-level client wraps it (ragas 0.4.3's LLM wrapper is
# instructor-based, not langchain, so LangChain callbacks won't see it).
# ---------------------------------------------------------------------------


class TokenTap:
    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    async def hook(self, response: httpx.Response) -> None:
        try:
            await response.aread()
            data = response.json()
        except Exception:  # noqa: BLE001 -- best-effort accounting only
            return
        usage = data.get("usage") if isinstance(data, dict) else None
        if not usage:
            return
        self.input_tokens += usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        self.output_tokens += usage.get("completion_tokens") or usage.get("output_tokens") or 0
        self.calls += 1

    def totals(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "llm_calls": self.calls}


def cost_usd(input_tokens: int, output_tokens: int, *, is_embedding: bool = False) -> float:
    if is_embedding:
        return input_tokens / 1_000_000 * 0.02
    return input_tokens / 1_000_000 * 0.15 + output_tokens / 1_000_000 * 0.60


# ---------------------------------------------------------------------------
# Rubric classifiers -- plain gpt-4o-mini calls via the local gateway,
# structured output, evals-only (not part of the frozen pipeline).
# ---------------------------------------------------------------------------


class ContentBehaviorLabel(BaseModel):
    label: Literal["answer", "web_answer", "honest_fallback", "mixed"]
    rationale: str


CONTENT_CLASSIFIER_SYSTEM = """You classify one turn of a cricket-rules assistant's answer into exactly one category, based on the answer text alone:

- "answer": the answer asserts specific rule content from the association's own rulebook (cites a section/document, e.g. "(Section J15, ...)") as its real answer, and cites no URL / "(Source: ...)" anywhere.
- "web_answer": the answer asserts content sourced from a web search (cites a URL / "(Source: ...)") as its real answer, and cites no rulebook section anywhere.
- "honest_fallback": the answer states plainly that it could not find an answer, that the rules do not cover the question, or that this is outside the association's own documents -- with no confident rule-grounded or web-grounded claim asserted as the actual answer.
- "mixed": the answer cites BOTH a rulebook section AND a URL/"(Source: ...)" as genuinely asserted parts of its real answer -- not just one appearing after an otherwise-honest fallback statement.

Use "mixed" only when both a rulebook-section citation and a URL/Source citation are actually present in the answer text. An answer that only cites rulebook sections, even if it discusses multiple sub-topics or elaborates at length, is "answer", not "mixed". Classify based on what the answer actually asserts as its substantive content, not on stylistic hedging alone."""


class AcceptanceCheck(BaseModel):
    meets_criterion: bool
    rationale: str


FLAG_ACCEPTABLE_SYSTEM = """You check whether an assistant's answer to a genuinely ambiguous cricket-rules question meets a stated acceptance criterion, rather than confidently guessing one interpretation.

You will be given: the question, the documented reason it's ambiguous (drawn from this question's own notes), and the assistant's actual answer. Decide: did the answer either (a) ask a clarifying question back to the user, or (b) honestly present the relevant branches/grades/interpretations rather than silently picking one and stating it as if unambiguous? Either (a) or (b) counts as meeting the criterion. Confidently stating a single number or a single grade's rule as if it were the only answer does not."""


def _classifier_llm() -> ChatOpenAI:
    proxy_base_url = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
    return ChatOpenAI(
        model=RAGAS_MODEL,
        base_url=proxy_base_url,
        api_key=os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy"),
    )


def classify_content_behavior(llm: ChatOpenAI, question: str, answer: str) -> ContentBehaviorLabel:
    structured = llm.with_structured_output(ContentBehaviorLabel)
    return structured.invoke(
        [
            SystemMessage(content=CONTENT_CLASSIFIER_SYSTEM),
            HumanMessage(content=f"Question: {question}\n\nAnswer:\n{answer}"),
        ]
    )


def classify_flag_acceptable(llm: ChatOpenAI, question: str, expected_answer: str, notes: str, answer: str) -> AcceptanceCheck:
    structured = llm.with_structured_output(AcceptanceCheck)
    return structured.invoke(
        [
            SystemMessage(content=FLAG_ACCEPTABLE_SYSTEM),
            HumanMessage(
                content=(
                    f"Question: {question}\n\n"
                    f"Documented ambiguity / acceptance criterion (from the golden set's expected_answer and notes):\n"
                    f"{expected_answer}\n{notes}\n\n"
                    f"Assistant's actual answer:\n{answer}"
                )
            ),
        ]
    )


def has_invented_citation(answer: str) -> bool:
    return bool(_RULE_CITATION_RE.search(answer) or _WEB_CITATION_RE.search(answer))


# ---------------------------------------------------------------------------
# Ragas metric scoring
# ---------------------------------------------------------------------------


def build_ragas_clients(tap: TokenTap):
    proxy_base_url = os.environ.get("LITELLM_PROXY_BASE_URL", "http://localhost:4000")
    api_key = os.environ.get("LITELLM_PROXY_API_KEY", "routed-through-proxy")
    http_client = httpx.AsyncClient(event_hooks={"response": [tap.hook]})
    async_client = AsyncOpenAI(base_url=proxy_base_url, api_key=api_key, http_client=http_client)

    llm = llm_factory(RAGAS_MODEL, provider="openai", client=async_client)
    embeddings = embedding_factory(provider="openai", model=RAGAS_EMBEDDING_MODEL, client=async_client)
    return llm, embeddings


async def score_answer_row(record: dict, faithfulness, context_precision, context_recall, answer_relevancy) -> dict:
    scores: dict = {}
    contexts = record["rule_contexts"]
    question = record["question"]
    answer = record["answer"]
    reference = record["expected_answer"]

    for name, coro in (
        ("faithfulness", faithfulness.ascore(user_input=question, response=answer, retrieved_contexts=contexts)),
        (
            "context_precision",
            context_precision.ascore(user_input=question, reference=reference, retrieved_contexts=contexts),
        ),
        (
            "context_recall",
            context_recall.ascore(user_input=question, retrieved_contexts=contexts, reference=reference),
        ),
        ("answer_relevancy", answer_relevancy.ascore(user_input=question, response=answer)),
    ):
        try:
            result = await coro
            scores[name] = float(result.value)
        except Exception as exc:  # noqa: BLE001
            scores[name] = None
            scores[f"{name}_error"] = repr(exc)
    return scores


async def score_web_answer_row(record: dict, answer_relevancy) -> dict:
    try:
        result = await answer_relevancy.ascore(user_input=record["question"], response=record["answer"])
        return {"answer_relevancy": float(result.value)}
    except Exception as exc:  # noqa: BLE001
        return {"answer_relevancy": None, "answer_relevancy_error": repr(exc)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def score_all(records: list[dict], golden_by_id: dict[str, dict]) -> list[dict]:
    tap = TokenTap()
    llm, embeddings = build_ragas_clients(tap)
    faithfulness = Faithfulness(llm=llm)
    context_precision = ContextPrecision(llm=llm)
    context_recall = ContextRecall(llm=llm)
    answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
    classifier_llm = _classifier_llm()

    scored: list[dict] = []
    for record in records:
        row_id = record["id"]
        golden_row = golden_by_id[row_id]
        expected_behavior = record["expected_behavior"]
        out = dict(record)

        if record["error"] is not None or record["answer"] is None:
            out["scoring"] = {"skipped": f"generation error: {record['error']}"}
            scored.append(out)
            print(f"  {row_id} run{record['run_index']}: skipped (generation error)")
            continue

        scoring: dict = {"expected_behavior": expected_behavior}

        if expected_behavior == "answer":
            ragas_scores = await score_answer_row(record, faithfulness, context_precision, context_recall, answer_relevancy)
            scoring.update(ragas_scores)
            label = classify_content_behavior(classifier_llm, record["question"], record["answer"])
            scoring["content_label"] = label.label
            scoring["behavior_match"] = ("search_rules_tool" in record["tools_called"]) and label.label != "honest_fallback"
            judge_verdict = (record.get("judge_verdict") or {}).get("verdict")
            scoring["judge_verdict"] = judge_verdict
            if judge_verdict in ("PASS", "FAIL") and ragas_scores.get("faithfulness") is not None:
                judge_pass = judge_verdict == "PASS"
                ragas_pass = ragas_scores["faithfulness"] >= FAITHFULNESS_PASS_THRESHOLD
                scoring["judge_ragas_agree"] = judge_pass == ragas_pass
            else:
                scoring["judge_ragas_agree"] = None

        elif expected_behavior == "web_answer":
            ragas_scores = await score_web_answer_row(record, answer_relevancy)
            scoring.update(ragas_scores)
            label = classify_content_behavior(classifier_llm, record["question"], record["answer"])
            scoring["content_label"] = label.label
            scoring["behavior_match"] = ("web_search_tool" in record["tools_called"]) and label.label != "honest_fallback"

        elif expected_behavior == "honest_fallback":
            label = classify_content_behavior(classifier_llm, record["question"], record["answer"])
            scoring["content_label"] = label.label
            scoring["behavior_match"] = label.label == "honest_fallback"
            scoring["no_invented_citations"] = not has_invented_citation(record["answer"])

        elif expected_behavior == "flag_acceptable":
            check = classify_flag_acceptable(
                classifier_llm,
                record["question"],
                golden_row["expected_answer"],
                golden_row.get("notes", ""),
                record["answer"],
            )
            scoring["behavior_match"] = check.meets_criterion
            scoring["acceptance_rationale"] = check.rationale

        out["scoring"] = scoring
        scored.append(out)
        bm = scoring.get("behavior_match")
        print(f"  {row_id} run{record['run_index']}: behavior_match={bm}")

    ragas_totals = tap.totals()
    print(
        f"\nRagas + classifier LLM usage: {ragas_totals['llm_calls']} calls, "
        f"{ragas_totals['input_tokens']} in / {ragas_totals['output_tokens']} out tokens, "
        f"~${cost_usd(ragas_totals['input_tokens'], ragas_totals['output_tokens']):.4f}"
    )
    for rec in scored:
        rec.setdefault("scoring_run_totals", ragas_totals)
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", required=True, help="raw JSONL from run_baseline.py")
    parser.add_argument("--out", required=True, help="scored JSONL output path")
    parser.add_argument("--golden-set", default=str(REPO_ROOT / "evals" / "golden_set.json"))
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    with open(args.golden_set) as f:
        golden_set = json.load(f)
    golden_by_id = {row["id"]: row for row in golden_set}

    records = []
    with open(args.in_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    already_scored: set[tuple[str, int]] = set()
    out_path = Path(args.out)
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    already_scored.add((rec["id"], rec["run_index"]))
        print(f"Resuming: {len(already_scored)} already-scored (id, run_index) pairs in {out_path}")

    to_score = [r for r in records if (r["id"], r["run_index"]) not in already_scored]
    print(f"Scoring {len(to_score)} of {len(records)} records ({len(already_scored)} already done)")

    scored = asyncio.run(score_all(to_score, golden_by_id))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        for rec in scored:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
