# Frontend (Next.js)

This frontend is a Next.js App Router migration of the previous static SPA.

## Requirements

- Node.js 18.17+
- Backend running on `http://127.0.0.1:8000`

## Environment

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

If omitted, the app defaults to `http://127.0.0.1:8000/api/v1`.

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
