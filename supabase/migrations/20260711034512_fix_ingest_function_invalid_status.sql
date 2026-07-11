-- Fix: the previous version tried to mark a superseded document's status
-- as 'superseded', but documents.status has a pre-existing check
-- constraint (check_document_status) that only allows
-- pending|processing|indexed|failed — confirmed live when re-running the
-- CLI on the same PDF a second time (23514 check-constraint violation).
--
-- Rather than force version-currency semantics into a status column
-- that's actually about indexing progress, this drops the status-based
-- "supersede" marker entirely. The old document_id/version this function
-- returns is now determined purely by recency (created_at DESC, same as
-- before) among rows for the same (association_id, title) — no status
-- filter, no status mutation on the old row. The old row simply stays
-- 'indexed' (which is still true: it *was* successfully indexed), and
-- becomes historical only in the sense that a newer row now exists for
-- the same title. Its rule_chunks are still deleted as before, so it
-- carries no chunks and won't be retrieved from.

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
    order by documents.created_at desc
    limit 1;

    if v_old_document_id is not null then
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

revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from public;
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from anon;
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from authenticated;
grant execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) to service_role;
