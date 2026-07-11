"""CLI entry point: python -m backend.ask --association-id X "question"

Manual testing tool for the baseline retrieval + answer pipeline.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from backend.answer import answer


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask a question against one association's rules.")
    parser.add_argument("question", help="the question to ask")
    parser.add_argument("--association-id", required=True, help="associations.id (uuid)")
    parser.add_argument("--top-k", type=int, default=None, help="override TOP_K_DEFAULT")
    parser.add_argument(
        "--grade-scope",
        choices=["junior", "senior_men", "senior_women"],
        default=None,
        help="restrict to one grade (plus grade-agnostic chunks like the forms); omit to search all grades",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()

    kwargs = {"question": args.question, "association_id": args.association_id}
    if args.top_k is not None:
        kwargs["top_k"] = args.top_k
    if args.grade_scope is not None:
        kwargs["grade_scope"] = args.grade_scope

    result = answer(**kwargs)

    print(result.answer)
    print("\nRetrieved chunks:")
    for c in result.retrieved_chunks:
        print(
            f"  [{c.similarity:.4f}] Section {c.section_number} | {c.doc_name} {c.doc_version or ''} "
            f"| grade={c.grade_scope or 'any'} | {c.content_type}"
        )
        preview = c.chunk[:120].replace("\n", " ")
        print(f"    {preview}...")


if __name__ == "__main__":
    main()
