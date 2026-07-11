"""CLI entry point: python -m backend.chat --association-id X --thread-id Y "question"

Multi-turn agent CLI. ask.py stays untouched as the frozen single-turn
baseline for comparison. Each invocation opens a fresh Postgres
connection for the checkpointer, runs one turn, and closes it on exit —
persistence comes entirely from the checkpoint tables in Supabase, not
from anything held across invocations.
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver

from backend.agent import build_graph


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-turn chat against one association's rules.")
    parser.add_argument("question", help="the question or message to send")
    parser.add_argument("--association-id", required=True, help="associations.id (uuid)")
    parser.add_argument("--thread-id", required=True, help="conversation thread id; reuse to continue, change to start fresh")
    parser.add_argument(
        "--grade-scope",
        choices=["junior", "senior_men", "senior_women"],
        default=None,
        help="trusted, caller-supplied grade filter for this whole conversation; the model cannot set or change it. Omit to search all grades.",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()

    with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        graph = build_graph(args.association_id, checkpointer, grade_scope=args.grade_scope)
        config = {"configurable": {"thread_id": args.thread_id}}
        result = graph.invoke({"messages": [HumanMessage(content=args.question)]}, config=config)
        print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
