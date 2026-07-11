-- Rule chunks: the retrieval corpus for the agent's search_rules tool.
-- Additive only. Does not alter any existing table (associations, documents,
-- cities, countries, profiles).
--
-- document_id  -> reuses documents.title/version/status instead of
--                 duplicating doc_name/doc_version on this table.
-- association_id -> denormalized from documents.association_id so every
--                 retrieval query (always scoped to one association) can
--                 filter without a join.
-- Metadata schema (document_type, grade_scope, section_number, content_type)
-- matches docs/submission.md's Data Strategy section.

create table if not exists public.rule_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    association_id uuid not null references public.associations(id) on delete cascade,
    chunk text not null,
    embedding extensions.vector(1536) not null,
    document_type text not null check (document_type in ('rules', 'form')),
    grade_scope text check (grade_scope in ('junior', 'senior_men', 'senior_women')),
    section_number text,
    content_type text not null check (content_type in ('rule_text', 'table', 'procedure')),
    created_at timestamptz not null default now()
);

-- Primary filter every retrieval query uses: scope to one association
-- before ranking by similarity.
create index if not exists rule_chunks_association_id_idx
    on public.rule_chunks (association_id);

-- HNSW over IVFFlat: no need to pre-choose a `lists` parameter based on
-- row count, and this per-association corpus is small enough that HNSW's
-- build cost is a non-issue while giving better recall/speed.
create index if not exists rule_chunks_embedding_hnsw_idx
    on public.rule_chunks
    using hnsw (embedding extensions.vector_cosine_ops);

-- Deny-by-default: the backend accesses this table with the service role,
-- which bypasses RLS entirely. No anon/authenticated policies are needed
-- or added, so this table is unreachable from the frontend's anon/user
-- keys, satisfying Supabase's "every public table must have RLS enabled"
-- posture without opening any access.
alter table public.rule_chunks enable row level security;
