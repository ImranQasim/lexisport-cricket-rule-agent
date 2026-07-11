-- Enable pgvector for rule-chunk embeddings.
-- Installed into the `extensions` schema per Supabase convention (keeps
-- `public` clean). NOTE: this database's search_path is `"$user", public`
-- and does not include `extensions`, so downstream migrations reference
-- the type explicitly as `extensions.vector(...)`.
create extension if not exists vector with schema extensions;
