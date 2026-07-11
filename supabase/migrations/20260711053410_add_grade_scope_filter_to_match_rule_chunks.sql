-- Add an optional grade_scope filter to match_rule_chunks.
--
-- Was safe with only one document (MYCA Senior Men's) ingested for the
-- association. Now that Junior, Senior Women's, and the two grade-
-- agnostic forms are also ingested under the same association_id, a
-- query intended for one grade could retrieve another grade's chunk and
-- cite it as if it applied -- exactly the cross-grade contamination risk
-- docs/submission.md's Data Strategy section already called out and
-- said retrieval would filter on. It wasn't wired into the SQL until now.
--
-- p_grade_scope is nullable and defaults to null:
--   - null (not provided): search across all grades for the association,
--     unchanged behavior from before this migration.
--   - a specific grade: return that grade's chunks, PLUS grade-agnostic
--     chunks (grade_scope is null on rule_chunks -- the two forms, and
--     any future non-grade-specific document), since a form's procedure
--     text should surface regardless of which grade the umpire asking
--     about it plays.
--
-- Function identity in Postgres is the argument type list, so adding a
-- parameter is a new overload, not a replacement of the 3-arg version --
-- dropping the old one first avoids PostgREST's RPC route having two
-- ambiguous candidates to choose between.

drop function if exists public.match_rule_chunks(uuid, extensions.vector, int);

create function public.match_rule_chunks(
    p_association_id uuid,
    p_query_embedding extensions.vector(1536),
    p_top_k int,
    p_grade_scope text default null
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
    select
        rc.chunk,
        rc.section_number,
        d.title as doc_name,
        d.version as doc_version,
        rc.content_type,
        rc.grade_scope,
        1 - (rc.embedding <=> p_query_embedding) as similarity
    from rule_chunks rc
    join documents d on d.id = rc.document_id
    where rc.association_id = p_association_id
      and (
        p_grade_scope is null
        or rc.grade_scope = p_grade_scope
        or rc.grade_scope is null
      )
    order by rc.embedding <=> p_query_embedding
    limit p_top_k;
$$;

revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int, text) from public;
revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int, text) from anon;
revoke execute on function public.match_rule_chunks(uuid, extensions.vector, int, text) from authenticated;
grant execute on function public.match_rule_chunks(uuid, extensions.vector, int, text) to service_role;
