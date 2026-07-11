Next.js chat frontend for the Lexi Sport cricket rules agent, deployed on Vercel. See `docs/submission.md` for architecture.

The browser never sees the backend's API key. `app/api/proxy/route.ts` is a
server-side proxy: the browser calls same-origin `/api/proxy`, which attaches
`X-API-Key` server-side (from `BACKEND_API_KEY`, never `NEXT_PUBLIC_`-prefixed)
before calling the Render API.

## Run locally

```bash
cp .env.local.example .env.local   # fill in BACKEND_API_KEY
npm install
npm run dev
```

## Deploy

Vercel project settings: Root Directory = `frontend/`. Env vars `BACKEND_API_URL`
and `BACKEND_API_KEY`, both server-side (Production + Preview), no
`NEXT_PUBLIC_` prefix on either.
