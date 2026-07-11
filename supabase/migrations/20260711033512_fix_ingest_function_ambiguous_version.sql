-- Fix: RETURNS TABLE(..., version text, ...) creates an implicit
-- PL/pgSQL OUT variable named `version`, which collided with the bare
-- `documents.version` column reference in the existing-document lookup
-- ("column reference \"version\" is ambiguous", confirmed live when the
-- function was first exercised — the CLI's parse/chunk/embed/upload
-- steps all succeeded, only this RPC call failed, and it failed on the
-- very first statement in the function body, before any INSERT, so no
-- rows were ever written by the buggy version). This migration
-- re-creates the function with the lookup's columns qualified by table
-- name to disambiguate. No other changes.

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
    select documents.id, documents.version into v_old_document_id, v_old_version
    from documents
    where documents.association_id = p_association_id
      and documents.title = p_title
      and documents.status != 'superseded'
    order by documents.created_at desc
    limit 1;

    if v_old_document_id is not null then
        update documents set status = 'superseded' where documents.id = v_old_document_id;
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
    returning documents.id into v_new_document_id;

    if v_old_document_id is not null then
        delete from rule_chunks where rule_chunks.document_id = v_old_document_id;
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

    update documents set status = 'indexed', indexed_at = now() where documents.id = v_new_document_id;

    return query select v_new_document_id, v_new_version, v_old_document_id, v_count;
end;
$$;

-- Grants are unaffected by CREATE OR REPLACE (they persist on the
-- existing function object), but re-asserted here for certainty.
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from public;
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from anon;
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from authenticated;
grant execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) to service_role;
