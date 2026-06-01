# ICPC Training — Web Frontend

Vite + React + TypeScript + Tailwind + shadcn/ui SPA. Talks to the Flask/FastAPI
backend at `/api/*`. Designed to be deployed as a separate Vercel project from
the backend, sharing the same git repo.

## Stack

- **Vite 7** — build tool and dev server
- **React 19 + TypeScript** — UI
- **Tailwind CSS 3** + **shadcn/ui** — styling and components
- **TanStack Query** — server state (caching, polling, mutations)
- **TanStack Table** — headless table logic for the problem/contest/team grids
- **React Router v6** — client routing
- **React Hook Form + Zod** — forms and validation
- **react-markdown** + `rehype-raw` + `rehype-katex` — tutorial viewer

## Dev

```bash
cd web
npm install
npm run dev          # → http://localhost:5173, proxies /api → :5000
```

In another terminal, run the Flask backend from the repo root:

```bash
python app.py
```

## Layout

```
src/
├── lib/            # api fetch wrapper, queryClient, utils
├── services/       # one file per resource; functions that call /api/*
├── schemas/        # Zod schemas (source of truth for types)
├── hooks/          # TanStack Query hooks (useProblems, useTeams, …)
├── contexts/       # AuthContext etc.
├── components/
│   ├── ui/         # shadcn primitives
│   ├── layout/     # AppShell, Sidebar, ProtectedRoute, RoleGate
│   ├── common/     # pills, multi-selects, confirm dialogs
│   ├── data-table/ # generic TanStack Table wrappers
│   └── <domain>/   # problems/, teams/, contests/, users/, bank/, tutorials/
├── pages/          # one component per route
└── types/          # shared response wrappers
```

## Env

Copy `.env.example` → `.env` and edit `VITE_API_BASE_URL` if you're not using
the dev proxy.
