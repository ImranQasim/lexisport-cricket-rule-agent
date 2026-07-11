# LiteLLM proxy gateway

Local LiteLLM proxy exposing exactly two models: `gpt-4o-mini` and
`text-embedding-3-small`. All backend code (ingestion, agent) calls
these through this proxy instead of hitting OpenAI directly, per
`docs/submission.md`'s infrastructure design.

## Run it

```
uv venv gateway/.venv
uv pip install -r gateway/requirements.txt --python gateway/.venv
gateway/.venv/bin/litellm --config gateway/config.yaml
```

Listens on `http://localhost:4000` (LiteLLM's default proxy port).
No `master_key` is set, so no `Authorization` header is required for
local calls — fine for a single-developer cert-scope setup, but a
real deployment would need one.

## Budget cap

LiteLLM's `litellm_settings.max_budget` / `budget_duration` require a
Postgres `database_url` in `general_settings` for spend tracking —
there's no in-memory or file-based fallback, confirmed from the
current docs. Standing up a database just to cap spend on a
single-developer local proxy is more infrastructure than this project
needs, so the spend limit is set directly on the OpenAI project
dashboard instead. If this proxy is ever deployed for real multi-user
traffic, add `database_url` and the budget settings then.
