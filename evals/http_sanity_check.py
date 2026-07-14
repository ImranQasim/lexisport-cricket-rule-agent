"""Baseline evaluation harness -- HTTP sanity sample.

The baseline's primary data source is the local graph invocation (see
run_baseline.py's docstring for why). This script is the check against
that choice: a small stratified sample of real HTTP calls against the
live deployed Render API (/api/chat), to catch any prod/local config
drift (stale deploy, different env vars, different proxy routing) that
a purely local-invocation run could never surface.

Not a scoring pass -- LLM output is stochastic run to run, so this
reports structural/behavioral agreement (needs_human_review, which
citation types appear) rather than expecting verbatim-identical text,
and prints both answers in full for a human to read side by side.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# One row per category family, spanning expected_behavior values.
SAMPLE_IDS = ["eval-002", "eval-003", "eval-010", "eval-017", "eval-023", "eval-033"]


def call_api(base_url: str, api_key: str, row: dict) -> dict:
    thread_id = f"sanity-{uuid.uuid4().hex[:8]}"
    body = {
        "association_id": row["association_id"],
        "thread_id": thread_id,
        "question": row["question"],
        "grade_scope": row.get("grade_scope"),
    }
    resp = httpx.post(
        f"{base_url}/api/chat",
        json=body,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        timeout=190.0,  # matches frontend/app/api/proxy/route.ts's cold-start-aware timeout budget
    )
    resp.raise_for_status()
    return resp.json()


def citation_shape(citations: list[dict]) -> str:
    has_rule = any(c.get("type") == "rule" for c in citations)
    has_web = any(c.get("type") == "web" for c in citations)
    if has_rule and has_web:
        return "rule+web"
    if has_rule:
        return "rule"
    if has_web:
        return "web"
    return "none"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-set", default=str(REPO_ROOT / "evals" / "golden_set.json"))
    parser.add_argument("--local-raw", required=True, help="run_baseline.py's raw JSONL, for the local-invocation comparison")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_API_URL", "https://lexisport-agent-api.onrender.com"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ["API_KEY"]

    with open(args.golden_set) as f:
        golden_set = json.load(f)
    golden_by_id = {row["id"]: row for row in golden_set}

    local_by_id: dict[str, dict] = {}
    with open(args.local_raw) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["run_index"] == 0 and rec["id"] not in local_by_id:
                local_by_id[rec["id"]] = rec

    results = []
    for row_id in SAMPLE_IDS:
        row = golden_by_id[row_id]
        local = local_by_id.get(row_id)
        print(f"[{row_id}] calling live API ({args.backend_url}) ...", end=" ", flush=True)
        try:
            api_resp = call_api(args.backend_url, api_key, row)
            error = None
        except Exception as exc:  # noqa: BLE001
            api_resp = None
            error = repr(exc)
        print("ok" if error is None else f"ERROR: {error}")

        record = {
            "id": row_id,
            "question": row["question"],
            "error": error,
            "api_answer": api_resp.get("answer") if api_resp else None,
            "api_citations_shape": citation_shape(api_resp.get("citations", [])) if api_resp else None,
            "api_needs_human_review": api_resp.get("needs_human_review") if api_resp else None,
            "local_answer": local.get("answer") if local else None,
            "local_tools_called": local.get("tools_called") if local else None,
            "local_needs_human_review": local.get("needs_human_review") if local else None,
        }
        if api_resp and local:
            record["needs_human_review_agrees"] = record["api_needs_human_review"] == record["local_needs_human_review"]
            local_shape = "rule+web" if (
                "search_rules_tool" in (local.get("tools_called") or []) and "web_search_tool" in (local.get("tools_called") or [])
            ) else ("rule" if "search_rules_tool" in (local.get("tools_called") or []) else (
                "web" if "web_search_tool" in (local.get("tools_called") or []) else "none"
            ))
            record["citation_shape_agrees"] = record["api_citations_shape"] == local_shape
        results.append(record)

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nWrote {args.out}")
    for r in results:
        print(f"- {r['id']}: needs_human_review_agrees={r.get('needs_human_review_agrees')}, "
              f"citation_shape_agrees={r.get('citation_shape_agrees')}, error={r['error']}")


if __name__ == "__main__":
    main()
