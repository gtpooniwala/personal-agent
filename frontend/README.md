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
