-- Filtered similarity search for the baseline retrieval pipeline
-- (backend/retrieval.py). Additive only: one new function, no existing
-- table/column/policy/data touched.
--
-- association_id is filtered in the WHERE clause, inside the function,
-- before ranking — not a Python post-filter. This guarantees a query
-- against an association with zero chunks returns zero rows from the
-- database itself, and that ranking always happens within the correct
-- association's chunks only (never crowded out by another
-- association's chunks ranking higher globally).
--
-- Joins to documents for title/version since rule_chunks itself has no
-- doc_name/doc_version columns (see docs/submission.md's Data Strategy
-- section and the ingestion task's store.py — those live on documents,
-- reached via rule_chunks.document_id).
--
-- Pure SELECT, no writes, so none of documents'/rule_chunks' CHECK
-- constraints apply here (verified full constraint list on both tables
-- before writing this, after the ingestion task's check_document_status
-- miss).
--
-- security definer + explicit search_path (extensions isn't on this
-- database's default search_path, needed for the vector type and <=>
-- operator) + locked to service_role only, same posture as
-- ingest_document_version.

create or replace function public.match_rule_chunks(
    p_association_id uuid,
    p_query_embedding extensions.vector(1536),
    p_top_k int
)
returns table (
    chunk text,
    section_number text,
    doc_name text,
    doc_version text,
    content_type text,
    similarity float
)
language sql
security definer
set search_path = public, extensions
as $$
    select
        rc.chunk,
        rc.section_number,
        d.title as doc_name,
        d.version as doc_version,
        rc.content_type,
        1 - (rc.embedding <=> p_query_embedding) as similarity
    from rule_chunks rc
    join documents d on d.id = rc.document_id
    where rc.association_id = p_association_id
    order by rc.embedding <=> p_query_embedding
    limit p_top_k;
$$;

revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int) from public;
revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int) from anon;
revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int) from authenticated;
grant execute on function public.match_rule_chunks(uuid, extensions.vector, int) to service_role;
