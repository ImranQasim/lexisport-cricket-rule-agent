"""Storage + database writes.

Uploading the PDF to the rule-documents bucket is a separate step from
the atomic documents/rule_chunks write (storage isn't part of a Postgres
transaction anyway). The documents/rule_chunks write itself goes through
the ingest_document_version RPC function (see
supabase/migrations/20260711031607_create_ingest_document_version_function.sql),
which does the whole versioning transaction — mark old row superseded,
insert new documents row, delete old rule_chunks, insert new rule_chunks,
mark new row indexed — as one Postgres transaction server-side, so a
failure at any step rolls back everything. Locked down to service_role
only (see the follow-up migration), matching this project's service
role-only RLS posture on rule_chunks/documents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client

from ingestion.chunk import Chunk

BUCKET_NAME = "rule-documents"

# rule_chunks.document_type ('rules'|'form', the enum this project defined
# and documented in docs/submission.md) is a DIFFERENT, independently
# constrained column from documents.document_type, which has its own
# pre-existing check constraint from before this project
# (laws_of_cricket|playing_conditions|regulations|guidelines|other). This
# map bridges CLI intent to what the documents table will actually accept.
DOCUMENTS_DOCUMENT_TYPE_MAP = {
    "rules": "playing_conditions",
    "form": "other",
}


@dataclass
class StoreResult:
    document_id: str
    version: str
    old_document_id: str | None
    chunks_inserted: int


def _client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


def upload_pdf(client: Client, association_id: str, doc_name: str, pdf_path: str) -> str:
    """Uploads the PDF to rule-documents/{association_id}/{doc_name}.
    upsert=true so a re-ingest of the same doc_name overwrites the
    previously stored file rather than erroring."""
    storage_path = f"{association_id}/{doc_name}"
    with open(pdf_path, "rb") as f:
        client.storage.from_(BUCKET_NAME).upload(
            storage_path,
            f.read(),
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    return storage_path


def store_document_and_chunks(
    association_id: str,
    title: str,
    filename: str,
    original_filename: str,
    mime_type: str,
    file_size_bytes: int,
    document_type: str,  # 'rules' | 'form' — CLI-level; mapped below for `documents`
    grade_scope: str | None,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> StoreResult:
    if len(chunks) != len(embeddings):
        raise ValueError(f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")
    if document_type not in DOCUMENTS_DOCUMENT_TYPE_MAP:
        raise ValueError(f"document_type must be 'rules' or 'form', got {document_type!r}")

    chunk_payload = [
        {
            "chunk": c.text,
            "embedding": e,
            "document_type": document_type,
            "grade_scope": grade_scope,
            "section_number": c.section_number,
            "content_type": c.content_type,
        }
        for c, e in zip(chunks, embeddings)
    ]

    client = _client()
    response = (
        client.rpc(
            "ingest_document_version",
            {
                "p_association_id": association_id,
                "p_title": title,
                "p_filename": filename,
                "p_original_filename": original_filename,
                "p_mime_type": mime_type,
                "p_file_size_bytes": file_size_bytes,
                "p_documents_document_type": DOCUMENTS_DOCUMENT_TYPE_MAP[document_type],
                "p_chunks": chunk_payload,
            },
        )
        .execute()
    )

    row = response.data[0]
    return StoreResult(
        document_id=row["document_id"],
        version=row["version"],
        old_document_id=row["old_document_id"],
        chunks_inserted=row["chunks_inserted"],
    )
