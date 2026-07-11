# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project stage

This repo currently contains only framing documentation for an AI Engineer Certification Challenge project (AI Makerspace AIE10 cohort). No application code exists yet. Do not scaffold the FastAPI/LangGraph/Next.js app or create new folders unless explicitly asked — `docs/submission.md` is the spec, not an implementation task.

## What this project is

Lexi Sport Rules Agent: an agentic RAG assistant that answers questions about a specific cricket association's rules, grounded in that association's own rule documents, with citations to document and section. See `docs/submission.md` for the full problem framing, solution, infrastructure, evaluation questions, and data strategy — treat it as the source of truth over anything summarized here.

Stack decisions already locked in `docs/submission.md` (do not re-derive or second-guess these when implementation starts):
- FastAPI backend, LangGraph agent, behind a LiteLLM proxy gateway
- Supabase: existing relational tables (countries, cities, associations) plus a new pgvector table (rule chunks scoped by `association_id`) and a storage bucket for source PDFs
- OpenAI GPT-4o-mini (or a subsequent equivalent small/medium OpenAI model) for generation, judge, and fallback nodes; OpenAI `text-embedding-3-small` (1536 dim) for embeddings
- Tavily for public/current-info questions and base Laws of Cricket questions the association's documents assume rather than define
- Next.js frontend, deployed on Vercel; agent API on Render
- Ragas + LangSmith for evaluation and monitoring
- First corpus: MYCA (Mid Year Cricket Association) — Junior, Senior Men's, and Senior Women's playing-conditions documents plus two operational forms (Player Conduct Report, Suspect Bowling Action), chunked on each document's own section numbering, tagged with `association_id` / `document_type` / `grade_scope` / `section_number` / `content_type`

## Editing docs/submission.md

This file is reviewed and committed by the user only — never commit changes to it. When editing it:
- No em dashes anywhere. Short sentences. Plain human grammar.
- No marketing language, no hype words.
- First person singular throughout ("I", never "we") — this is Imran's voice, not a team's.
- Interview before drafting new sections when the request is open-ended; state back what you understood and get confirmation before writing prose.
- Show the full drafted section for review before writing it to the file.
- Keep sections to exactly what's asked — don't pad with extra subsections or restate requirements as headers.
