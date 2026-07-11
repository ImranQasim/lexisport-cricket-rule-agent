-- Follow-up to 20260711031607: Supabase's own default privileges grant
-- EXECUTE on new public-schema functions to anon/authenticated/service_role
-- at creation time (ALTER DEFAULT PRIVILEGES), independent of and not
-- undone by "REVOKE ... FROM PUBLIC". Verified live: after the previous
-- migration, information_schema.routine_privileges still showed anon and
-- authenticated with EXECUTE. This migration explicitly revokes from
-- those two named roles, leaving only service_role (and postgres, the
-- function owner) able to call it.
-- Additive-only in spirit: tightens access, touches no table/column/data.

revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from anon;
revoke execute on function public.ingest_document_version(uuid, text, text, text, text, bigint, text, jsonb) from authenticated;
