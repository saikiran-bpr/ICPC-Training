# ICPC Training - Problem Repository

A self-contained problem repository for Indian ICPC teams preparing for **Regionals**, **Asia West Finals**, and the **World Finals**. Stores curated problems from Codeforces, AtCoder, CodeChef, ICPC Archives and other platforms with rich metadata, a web UI for CRUD, and one-click Excel export.

## Stack

- **Backend:** Python 3.10+, Flask, SQLite (file-based, no server to install)
- **Frontend:** Single static HTML page (no build step, no npm)
- **Export:** `openpyxl` (XLSX with header styling, freeze pane, auto filter)

## Setup

```bash
cd problem-repository
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000/> in your browser. The database file `problems.db` is created on first run.

## Metadata schema

| Field             | Type         | Notes                                                                |
|-------------------|--------------|----------------------------------------------------------------------|
| `id`              | int          | auto                                                                 |
| `name`            | string       | required                                                             |
| `url`             | string       | required, unique                                                     |
| `platform`        | enum         | required - Codeforces / AtCoder / CodeChef / ICPC Archive / Kattis / UVa / SPOJ / Google Code Jam / Meta Hacker Cup / USACO / HackerEarth / Other |
| `contest_name`    | string       | e.g. *ICPC Asia Amritapuri Regional 2023*                            |
| `contest_type`    | enum         | ICPC World Finals / Asia West Finals / ICPC Regional / CF Round / ABC / ARC / AGC / CodeChef Long / Cook-Off / GCJ / MHC / Practice / Gym / Other |
| `contest_year`    | int          |                                                                      |
| `problem_index`   | string       | A, B, F, P1                                                          |
| `rating`          | int          | numeric difficulty (CF rating, AtCoder difficulty, etc.)             |
| `difficulty`      | enum         | Easy / Easy-Medium / Medium / Medium-Hard / Hard / Very Hard         |
| `topic`           | enum         | Graph / DP / Greedy / Math / Geometry / Strings / Data Structures / ... |
| `sub_topic`       | string       | e.g. *Lazy Segment Tree*                                             |
| `tags`            | list[string] | free-form                                                            |
| `importance`      | enum         | Critical / High / Medium / Low                                       |
| `suggested_role`  | enum         | Algo / DS / Math / Geometry / Implementation / Any                   |
| `prerequisites`   | string       | comma-separated topic list                                           |
| `key_idea`        | text         | the trick / observation                                              |
| `editorial_url`   | string       |                                                                      |
| `time_limit_ms`   | int          |                                                                      |
| `memory_limit_mb` | int          |                                                                      |
| `status`          | enum         | Todo / In Progress / Done / Upsolve / Skipped                        |
| `assigned_to`     | string       | team or member                                                       |
| `notes`           | text         |                                                                      |
| `date_added`      | timestamp    | auto                                                                 |
| `date_updated`    | timestamp    | auto (trigger)                                                       |

Allowed enum values are also exposed via `GET /api/meta` so the frontend dropdowns stay in sync.

## REST API

Base URL: `http://127.0.0.1:5000/api`

| Method | Path                        | Purpose                                  |
|--------|-----------------------------|------------------------------------------|
| GET    | `/meta`                     | enum values for dropdowns                |
| GET    | `/stats`                    | counts grouped by platform/topic/etc.    |
| GET    | `/problems`                 | list with filters & search               |
| GET    | `/problems/<id>`            | fetch one                                |
| POST   | `/problems`                 | create                                   |
| PUT    | `/problems/<id>`            | full or partial update                   |
| PATCH  | `/problems/<id>`            | partial update (alias)                   |
| DELETE | `/problems/<id>`            | delete                                   |
| POST   | `/problems/bulk`            | bulk insert (`{"items": [ ... ]}`)       |
| GET    | `/export/xlsx`              | export filtered list as XLSX             |

### List filters

`GET /api/problems` accepts these query params (all optional, combinable):

```
q                 free-text on name, notes, key_idea, sub_topic, tags
platform          exact match
topic             exact match
difficulty        exact match
importance        exact match
status            exact match
suggested_role    exact match
contest_type      exact match
contest_year      int
rating_min        int
rating_max        int
sort              name | rating | date_added | importance | id   (default: date_added)
order             asc | desc                                       (default: desc)
limit, offset     pagination
```

### Examples

Create a problem:

```bash
curl -X POST http://127.0.0.1:5000/api/problems \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bear and Forgotten Tree 3",
    "url": "https://codeforces.com/problemset/problem/639/F",
    "platform": "Codeforces",
    "contest_name": "Codeforces Round 350 Div. 1",
    "contest_type": "Codeforces Round",
    "contest_year": 2016,
    "problem_index": "F",
    "rating": 3000,
    "difficulty": "Very Hard",
    "topic": "Graph",
    "sub_topic": "2-edge connectivity, DSU offline",
    "tags": ["graph","dsu","trees","offline"],
    "importance": "High",
    "suggested_role": "Algo",
    "key_idea": "Reduce to bridge / 2-ecc components processed offline",
    "status": "Upsolve"
  }'
```

List Codeforces DP problems with rating ≥ 2200:

```bash
curl 'http://127.0.0.1:5000/api/problems?platform=Codeforces&topic=DP&rating_min=2200&sort=rating&order=desc'
```

Bulk import:

```bash
curl -X POST http://127.0.0.1:5000/api/problems/bulk \
  -H "Content-Type: application/json" \
  -d '{"items":[{"name":"...","url":"...","platform":"AtCoder"}, ...]}'
```

Download XLSX (respects filters):

```bash
curl -OJ 'http://127.0.0.1:5000/api/export/xlsx?topic=Geometry&difficulty=Hard'
```

## Web UI features

- Sortable, sticky-header table with one-line preview of contest, sub-topic and tags.
- Sidebar filters: platform, topic, difficulty, importance, status, role, contest type, year, rating range.
- Full-text search across name, key idea, sub-topic, tags and notes.
- Modal-based create / edit form with all metadata fields.
- One-click delete with confirmation.
- "Export Excel" button downloads the currently-filtered set as a styled `.xlsx` (frozen header, auto-filter, sensible column widths).

## File layout

```
problem-repository/
├── app.py            # Flask app: API + Excel export
├── schema.sql        # SQLite DDL
├── requirements.txt
├── static/
│   └── index.html    # frontend (vanilla JS, no build)
└── problems.db       # auto-created on first run (gitignored if you wish)
```

## Backups & sharing

Because storage is a single SQLite file, backup is just `cp problems.db problems-YYYYMMDD.db`. To share a snapshot with the team, send the `.db` file or, easier, the exported XLSX.

## Deploying publicly (Vercel + Turso)

The app ships with everything needed to host it on Vercel for free, with a Turso (libSQL) database providing persistent storage. Local SQLite continues to work for development — the `db.py` adapter picks the backend at runtime based on env vars.

### 1. Create the Turso database

```bash
# Install once (https://docs.turso.tech/quickstart)
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup     # or: turso auth login

turso db create icpc-training
turso db show icpc-training --url     # -> libsql://icpc-training-<org>.turso.io
turso db tokens create icpc-training  # -> long auth token
```

### 2. Seed Turso from your local DB

```bash
export TURSO_DATABASE_URL='libsql://...'
export TURSO_AUTH_TOKEN='...'

python -m pip install -r requirements.txt
python scripts/seed_turso.py            # applies schema + copies all rows
# Re-running is safe: INSERT OR IGNORE on every row.
```

Pass `--schema-only` to apply the schema without copying data, or `--skip TABLE` to leave a table untouched.

### 3. Deploy to Vercel

The repo includes `vercel.json` and `api/index.py` (Flask WSGI entry).

Easiest path — use Vercel's GitHub integration:

1. Push this repo to GitHub (instructions below).
2. Go to <https://vercel.com/new> and import the repo.
3. Under **Environment Variables**, add:
   - `FLASK_SECRET_KEY` — `python -c "import secrets; print(secrets.token_hex(32))"`
   - `TURSO_DATABASE_URL`
   - `TURSO_AUTH_TOKEN`
4. Hit **Deploy**. Vercel will auto-deploy on every push to `main` from then on.

CLI alternative:

```bash
npm i -g vercel
vercel link        # connects this folder to a Vercel project
vercel env add FLASK_SECRET_KEY production
vercel env add TURSO_DATABASE_URL production
vercel env add TURSO_AUTH_TOKEN production
vercel --prod
```

### 4. (Optional) Auto-deploy via GitHub Actions

`.github/workflows/deploy.yml` deploys on push to `main` using the Vercel CLI. This is **redundant** if you've already enabled Vercel's GitHub integration in step 3 — pick one or the other. To use the workflow, add three repo secrets under **Settings → Secrets and variables → Actions**:

- `VERCEL_TOKEN` — from <https://vercel.com/account/tokens>
- `VERCEL_ORG_ID` — found in `.vercel/project.json` after `vercel link`
- `VERCEL_PROJECT_ID` — same file

`.github/workflows/ci.yml` runs syntax checks and an import smoke-test on every push and PR.

## Local development

Set the same env vars as production but leave Turso vars empty to use a local SQLite file:

```bash
cp .env.example .env
# edit .env, set FLASK_SECRET_KEY at minimum
export $(grep -v '^#' .env | xargs)   # or use direnv / dotenv loader
python app.py
```

Without `TURSO_DATABASE_URL`, the app falls back to `./problems.db`.

## What runs on Vercel vs locally

| File / script | Vercel? | Notes |
|---|---|---|
| `app.py` (Flask) | yes (serverless) | All HTTP requests go through `api/index.py`. |
| `db.py` adapter | yes | Picks Turso vs local SQLite at runtime. |
| `static/index.html` | yes | Served by Flask via `static_url_path="/static"`. |
| `tutorial_worker.py` | **no** | Long-running background worker — run on your laptop or a VM. |
| `import_*.py`, `fetch_*.py` | **no** | One-shot scripts. Run locally with `TURSO_*` env vars set to write directly to prod, or run against local SQLite and re-seed.

## Roadmap ideas (not implemented)

- Auth / per-user assignments
- Problem-level discussion threads
- Auto-fetch problem metadata from Codeforces / AtCoder APIs given a URL
- Track per-team submission attempts and verdicts
- Tag taxonomy auto-suggest based on co-occurrence
# ICPC-Training
