-- Atomic versioning transaction for the ingestion pipeline.
-- Additive only: adds one new function, does not alter any existing
-- table/column/policy/data.
--
-- Called via the supabase-py client's .rpc(), authenticated with the
-- service role (SUPABASE_SECRET_KEY) — the same principal that already
-- bypasses RLS on rule_chunks/documents. security definer + explicit
-- search_path make the function self-contained regardless of caller
-- privileges, following Postgres's own recommended practice for
-- security definer functions (an unset search_path on a definer
-- function is a known injection vector).
--
-- Versioning policy (per user decision): re-running ingestion for the
-- same (association_id, title) marks the previous non-superseded
-- documents row as 'superseded', inserts a new documents row at the
-- next version, deletes the old row's rule_chunks, inserts the new
-- rule_chunks tied to the new document_id, then marks the new row
-- 'indexed'. All in one function body = one implicit transaction, so a
-- failure at any step rolls back everything ("no orphans").

create or replace function public.ingest_document_version(
    p_association_id uuid,
    p_title text,
    p_filename text,
    p_original_filename text,
    p_mime_type text,
    p_file_size_bytes bigint,
    p_documents_document_type text,
    p_chunks jsonb
)
returns table (
    document_id uuid,
    version text,
    old_document_id uuid,
    chunks_inserted integer
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_old_document_id uuid;
    v_old_version text;
    v_new_version text;
    v_new_document_id uuid;
    v_chunk jsonb;
    v_count integer := 0;
begin
    select id, version into v_old_document_id, v_old_version
    from documents
    where association_id = p_association_id
      and title = p_title
      and status != 'superseded'
    order by created_at desc
    limit 1;

    if v_old_document_id is not null then
        update documents set status = 'superseded' where id = v_old_document_id;
        begin
            v_new_version := 'v' || (substring(v_old_version from 2)::int + 1);
        exception when others then
            v_new_version := 'v1';
        end;
    else
        v_new_version := 'v1';
    end if;

    insert into documents (
        association_id, filename, original_filename, mime_type,
        file_size_bytes, document_type, title, version, status
    )
    values (
        p_association_id, p_filename, p_original_filename, p_mime_type,
        p_file_size_bytes, p_documents_document_type, p_title, v_new_version, 'pending'
    )
    returning id into v_new_document_id;

    if v_old_document_id is not null then
        delete from rule_chunks where document_id = v_old_document_id;
    end if;

    for v_chunk in select * from jsonb_array_elements(p_chunks)
    loop
        insert into rule_chunks (
            document_id, association_id, chunk, embedding,
            document_type, grade_scope, section_number, content_type
        )
        values (
            v_new_document_id,
            p_association_id,
            v_chunk->>'chunk',
            (v_chunk->>'embedding')::extensions.vector,
            v_chunk->>'document_type',
            v_chunk->>'grade_scope',
            v_chunk->>'section_number',
            v_chunk->>'content_type'
        );
        v_count := v_count + 1;
    end loop;

    update documents set status = 'indexed', indexed_at = now() where id = v_new_document_id;

    return query select v_new_document_id, v_new_version, v_old_document_id, v_count;
end;
$$;

-- Lock down: only the service role may call this (matches rule_chunks/
-- documents' own service-role-only posture). Postgres grants EXECUTE to
-- PUBLIC by default on new functions, so this must be explicit.
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from public;
grant execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) to service_role;
