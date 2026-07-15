-- Hybrid retrieval experiment: dense (existing pgvector) + full-text search,
-- fused with Reciprocal Rank Fusion. Additive only: one new generated
-- column, one new index, one new function, alongside the existing
-- match_rule_chunks (untouched) -- baseline retrieval stays runnable
-- exactly as it is today, gated behind backend/retrieval.py's
-- RETRIEVAL_MODE env var, not this migration.
--
-- Fusion approach follows Supabase's own current hybrid-search guidance
-- (docs.supabase.com/guides/ai/hybrid-search, checked live rather than
-- from memory): two CTEs, one full-text (websearch_to_tsquery +
-- ts_rank_cd) and one semantic, row_number()'d independently, combined
-- via RRF (score = 1/(k + rank) per leg, weighted, summed). RRF is
-- rank-based rather than score-based specifically to avoid having to
-- normalize cosine similarity against ts_rank_cd's unrelated scale.
--
-- One deliberate deviation from Supabase's own example: their sample
-- ranks the semantic leg with inner product (<#>). This project's
-- existing rule_chunks_embedding_hnsw_idx is built with vector_cosine_ops
-- (see 20260710093142_create_rule_chunks.sql), so the semantic leg here
-- stays on cosine distance (<=>) to actually use that index, matching
-- match_rule_chunks's own existing ordering. RRF only consumes each
-- leg's *rank*, not its absolute score, so this substitution doesn't
-- change the fusion logic at all.

-- Generated column: kept in sync automatically by Postgres on every
-- insert/update to `chunk`, no ingestion-pipeline changes required.
alter table public.rule_chunks
    add column if not exists fts tsvector
    generated always as (to_tsvector('english', chunk)) stored;

create index if not exists rule_chunks_fts_idx
    on public.rule_chunks
    using gin (fts);

-- p_query_text: raw question text, for the full-text leg.
-- p_query_embedding: the same embedding backend/retrieval.py already
--   computes for the dense leg -- one embedding call total, not two.
-- p_grade_scope / p_association_id: filtered identically inside BOTH
--   CTEs (copied from match_rule_chunks's own WHERE clause, not
--   reinterpreted), so the hybrid path carries exactly the same
--   cross-grade/cross-association isolation guarantee as baseline.
-- Returned `similarity` is the fused RRF score for this function, not a
--   raw cosine similarity -- same column name as match_rule_chunks for
--   RetrievedChunk compatibility, but a different scale. Documented here
--   and in backend/retrieval.py.
create or replace function public.match_rule_chunks_hybrid(
    p_association_id uuid,
    p_query_text text,
    p_query_embedding extensions.vector(1536),
    p_top_k int,
    p_grade_scope text default null,
    p_full_text_weight float default 1,
    p_semantic_weight float default 1,
    p_rrf_k int default 50
)
returns table (
    chunk text,
    section_number text,
    doc_name text,
    doc_version text,
    content_type text,
    grade_scope text,
    similarity float
)
language sql
security definer
set search_path = public, extensions
as $$
    with full_text as (
        select
            rc.id,
            row_number() over (
                order by ts_rank_cd(rc.fts, websearch_to_tsquery('english', p_query_text)) desc
            ) as rank_ix
        from rule_chunks rc
        where rc.association_id = p_association_id
          and (
            p_grade_scope is null
            or rc.grade_scope = p_grade_scope
            or rc.grade_scope is null
          )
          and rc.fts @@ websearch_to_tsquery('english', p_query_text)
        order by rank_ix
        limit least(p_top_k, 30) * 2
    ),
    semantic as (
        select
            rc.id,
            row_number() over (
                order by rc.embedding <=> p_query_embedding
            ) as rank_ix
        from rule_chunks rc
        where rc.association_id = p_association_id
          and (
            p_grade_scope is null
            or rc.grade_scope = p_grade_scope
            or rc.grade_scope is null
          )
        order by rank_ix
        limit least(p_top_k, 30) * 2
    )
    select
        rc.chunk,
        rc.section_number,
        d.title as doc_name,
        d.version as doc_version,
        rc.content_type,
        rc.grade_scope,
        (
            coalesce(1.0 / (p_rrf_k + full_text.rank_ix), 0.0) * p_full_text_weight +
            coalesce(1.0 / (p_rrf_k + semantic.rank_ix), 0.0) * p_semantic_weight
        ) as similarity
    from full_text
    full outer join semantic on full_text.id = semantic.id
    join rule_chunks rc on rc.id = coalesce(full_text.id, semantic.id)
    join documents d on d.id = rc.document_id
    order by similarity desc
    limit least(p_top_k, 30);
$$;

revoke execute on function public.match_rule_chunks_hybrid(
    uuid, text, extensions.vector, int, text, float, float, int
) from public;
revoke execute on function public.match_rule_chunks_hybrid(
    uuid, text, extensions.vector, int, text, float, float, int
) from anon;
revoke execute on function public.match_rule_chunks_hybrid(
    uuid, text, extensions.vector, int, text, float, float, int
) from authenticated;
grant execute on function public.match_rule_chunks_hybrid(
    uuid, text, extensions.vector, int, text, float, float, int
) to service_role;
