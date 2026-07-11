"""CLI entry point: python -m ingestion.run --association-id X --pdf path ...

Wires parse -> chunk -> embed -> store in sequence. Structured as a thin
CLI over the four modules so the same core (parse_pdf, chunk_items,
embed_texts, store_document_and_chunks) can be reused by a future API
endpoint without rework.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ingestion.chunk import chunk_items
from ingestion.embed import embed_texts
from ingestion.parse import ParseError, parse_pdf
from ingestion.store import _client, store_document_and_chunks, upload_pdf


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a MYCA rule PDF into rule_chunks.")
    parser.add_argument("--association-id", required=True, help="associations.id (uuid)")
    parser.add_argument("--pdf", required=True, help="path to the source PDF")
    parser.add_argument("--title", required=True, help="documents.title, e.g. 'Senior Men's Playing Rules'")
    parser.add_argument("--document-type", required=True, choices=["rules", "form"])
    parser.add_argument(
        "--grade-scope",
        choices=["junior", "senior_men", "senior_women"],
        default=None,
        help="omit for non-grade-specific documents (e.g. the two operational forms)",
    )
    return parser


def run(args: argparse.Namespace) -> None:
    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"ERROR: no such file: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {pdf_path.name}...")
    try:
        parsed_items = parse_pdf(str(pdf_path), args.document_type)
    except ParseError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(parsed_items)} parsed items.")

    print("Chunking...")
    chunks = chunk_items(parsed_items)
    print(f"  {len(chunks)} chunks.")

    print(f"Embedding {len(chunks)} chunks via local LiteLLM proxy...")
    embeddings = embed_texts([c.text for c in chunks])

    doc_name = pdf_path.name
    print(f"Uploading {doc_name} to rule-documents/{args.association_id}/{doc_name}...")
    client = _client()
    upload_pdf(client, args.association_id, doc_name, str(pdf_path))

    print("Writing documents + rule_chunks (versioned, atomic)...")
    result = store_document_and_chunks(
        association_id=args.association_id,
        title=args.title,
        filename=doc_name,
        original_filename=doc_name,
        mime_type="application/pdf",
        file_size_bytes=pdf_path.stat().st_size,
        document_type=args.document_type,
        grade_scope=args.grade_scope,
        chunks=chunks,
        embeddings=embeddings,
    )

    print(
        f"Done. document_id={result.document_id} version={result.version} "
        f"chunks_inserted={result.chunks_inserted}"
        + (f" (superseded old document_id={result.old_document_id})" if result.old_document_id else "")
    )


def main() -> None:
    load_dotenv()
    args = build_arg_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
