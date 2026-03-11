# Frontend (Next.js)

This frontend is a Next.js App Router migration of the previous static SPA.

## Requirements

- Node.js 20.9+
- Backend running on `http://127.0.0.1:8000`

## Environment

Create `frontend/.env.local`:

```bash
API_BASE_URL=http://127.0.0.1:8000
AGENT_API_KEY=local-dev-token
```
Both values are required by the Next.js server-side proxy. The browser always calls the app's
same-origin `/api/agent/...` routes; it never talks directly to the backend host.
In Docker Compose, the frontend container uses `API_BASE_URL=http://personal-agent:8001` by
default and reuses `AGENT_API_KEY` from the root `.env` file, falling back to a local-only
proxy token when `AGENT_API_KEY` is unset or empty. When backend auth is enabled, the
frontend `AGENT_API_KEY` must match the backend token or proxied requests will return `401`.

For production deployment on Vercel, use the runbook in [`../docs/vercel-setup.md`](../docs/vercel-setup.md). Production uses the same env var names (`API_BASE_URL` and `AGENT_API_KEY`) as private Vercel env vars.

## Run

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

## Build

```bash
npm run build
npm run start
```
