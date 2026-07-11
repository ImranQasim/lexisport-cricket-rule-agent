-- LangGraph Postgres checkpointer tables.
-- These statements are the exact MIGRATIONS list from
-- langgraph.checkpoint.postgres.base.BasePostgresSaver, version 3.1.0
-- (verified by importing the installed package locally, not from memory
-- or docs). One deliberate deviation: CONCURRENTLY is dropped from the
-- three CREATE INDEX statements below, because CREATE INDEX CONCURRENTLY
-- cannot run inside a transaction block and migration runners commonly
-- wrap files in one; on these brand-new empty tables the non-concurrent
-- version is instant and carries no meaningful locking cost.
--
-- The INSERT INTO checkpoint_migrations rows at the end replicate what
-- PostgresSaver.setup() itself does after running each migration, so that
-- if the application calls .setup() at startup (the package's documented
-- usage pattern) it sees migrations 0-9 already applied and no-ops
-- instead of re-running them.
--
-- Additive only. Does not alter any existing table.

-- migration 0
create table if not exists public.checkpoint_migrations (
    v integer primary key
);

-- migration 1
create table if not exists public.checkpoints (
    thread_id text not null,
    checkpoint_ns text not null default '',
    checkpoint_id text not null,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb not null,
    metadata jsonb not null default '{}',
    primary key (thread_id, checkpoint_ns, checkpoint_id)
);

-- migration 2
create table if not exists public.checkpoint_blobs (
    thread_id text not null,
    checkpoint_ns text not null default '',
    channel text not null,
    version text not null,
    type text not null,
    blob bytea,
    primary key (thread_id, checkpoint_ns, channel, version)
);

-- migration 3
create table if not exists public.checkpoint_writes (
    thread_id text not null,
    checkpoint_ns text not null default '',
    checkpoint_id text not null,
    task_id text not null,
    idx integer not null,
    channel text not null,
    type text,
    blob bytea not null,
    primary key (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- migration 4
alter table public.checkpoint_blobs alter column blob drop not null;

-- migration 5 (no-op placeholder in the package's own migration history)
select 1;

-- migration 6 (CONCURRENTLY dropped, see note above)
create index if not exists checkpoints_thread_id_idx on public.checkpoints (thread_id);

-- migration 7 (CONCURRENTLY dropped, see note above)
create index if not exists checkpoint_blobs_thread_id_idx on public.checkpoint_blobs (thread_id);

-- migration 8 (CONCURRENTLY dropped, see note above)
create index if not exists checkpoint_writes_thread_id_idx on public.checkpoint_writes (thread_id);

-- migration 9
alter table public.checkpoint_writes add column if not exists task_path text not null default '';

-- Bookkeeping: mark migrations 0-9 as applied so PostgresSaver.setup()
-- no-ops on first call from the application.
insert into public.checkpoint_migrations (v)
values (0), (1), (2), (3), (4), (5), (6), (7), (8), (9)
on conflict (v) do nothing;

-- Deny-by-default RLS on all four tables: pure backend conversation-state,
-- never accessed by the frontend directly. Backend uses the service role,
-- which bypasses RLS, so no policies are added.
alter table public.checkpoint_migrations enable row level security;
alter table public.checkpoints enable row level security;
alter table public.checkpoint_blobs enable row level security;
alter table public.checkpoint_writes enable row level security;
