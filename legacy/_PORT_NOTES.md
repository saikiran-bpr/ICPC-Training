# Flask → FastAPI port notes

Living document. Updated as each domain is read line-by-line and ported into
`/backend/`. Cross-references the `.agents/skills/supabase-postgres-best-practices/`
rules I apply during each query rewrite.

Status legend: ⬜ not started · 🟡 in progress · ✅ ported · 🛑 deferred

---

## 0. Helpers (legacy/app.py)

| Helper | Lines | Purpose | Lands in |
|---|---|---|---|
| `generate_password_hash` | 48-53 | PBKDF2-SHA256 wrapper around werkzeug | `app/security.py` |
| `_load_secret` | 134-159 | Read FLASK_SECRET_KEY / persist to file | `app/config.py` (pydantic-settings reads env directly) |
| `get_db` / `close_db` | 171-188 | Per-request DB connection | `app/db.py` + `app/deps.py` (FastAPI dep) |
| `current_user` | 190-207 | Resolve session.user_id → user row | `app/deps.py` |
| `login_required` / `role_required` | 209-230 | Auth decorators | `app/deps.py` (FastAPI deps `current_user`, `require_role(...)`) |
| `is_admin` / `is_coach_of` / `is_member_of` / `can_manage_team` | 233-263 | Permission helpers | `app/deps.py` |
| `_attempt_dict` | 267-284 | Defensive row → dict (handles legacy `attempt_phase` missing) | `app/repositories/problems.py` (private) |
| `row_to_dict` | 287-340 | **N+1 SOURCE** — runs 3 sub-queries per problem row | `app/repositories/problems.py`. **Fix**: collapse into one `LEFT JOIN ... json_agg(...) GROUP BY` per page |
| `_build_team_summary` | 345-425 | Per-team solved/total + per-member attempts for coach view | `app/repositories/problems.py` |
| `normalize_problem_payload` | 431-451 | Whitelist + JSON-encode tags + remap legacy enums | replaced by Pydantic model validators in `app/schemas/problem.py` |
| `validate_required` | 454-457 | Manual required-field check | replaced by Pydantic |
| `public_user` | 460-470 | Strip password_hash, coerce is_active to bool | `app/schemas/user.py` (Pydantic response model excludes hash automatically) |
| `fetch_problem_name`, `_clean_title`, `_cf_url_to_ids`, `_cf_fetch_index`, `detect_platform_and_contest`, `topic_from_cf_tags`, `fetch_codeforces_details`, `difficulty_from_cf_rating` | 524-780 | URL → CF metadata lookup pipeline (HTML/JSON scraping) | `app/services/lookup.py` (move as-is, sync helpers fine; called by `/api/lookup` router) |
| `_normalize_id_list` / `_validate_assignment` | 2250-2283 | Coerce + validate user/team id lists | `app/schemas/assignment.py` validators |
| `_replace_problem_teams` / `_replace_problem_users` | 2285-2305 | Reset many-to-many for a problem | `app/repositories/problems.py` |
| `resolve_problem_sort` | 2081-2109 | Whitelist-driven ORDER BY clause builder | `app/repositories/problems.py` |
| `_contest_summary` / `_contest_with_problems` | 1662-1718 | Hydrate contest row with counts + assignees | `app/repositories/contests.py` |
| `_tutorial_role_audience` / `_check_audience_authorised` / `_generation_allowed` | 2501-2700 | Tutorial-flow permission helpers | `app/services/tutorials.py` |
| `_spawn_worker` | 2702-2719 | Popen tutorial_worker.py | 🛑 returns 503 stub (worker not ported) |
| `_user_can_see_problem` | 856-872 | Visibility check used by attempt endpoint | `app/repositories/problems.py` |
| `serialize_team` | 1218-1239 | Hydrate team row with members + coaches | `app/repositories/teams.py` |
| `http_error` | 2886-2893 | Convert HTTPException → JSON | replaced by FastAPI's default + custom handlers in `app/errors.py` |
| `cli_create_admin` | 2895-2940 | One-shot admin user creation | `backend/scripts/create_admin.py` |

---

## 1. Routes by domain

### Auth (port to `app/routers/auth.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| POST | `/api/auth/signup` | 980-1018 | Public; always creates Contestant |
| POST | `/api/auth/login` | 1020-1041 | Email+password; sets session cookie |
| POST | `/api/auth/logout` | 1043-1047 | Clears session |
| GET  | `/api/auth/me` | 1049-1055 | Returns `{authenticated, user}` |
| POST | `/api/auth/password` | 1057-1078 | Change password (needs current_password) |

### Users (port to `app/routers/users.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/users` | 1080-1123 | Filtered by role; Admin sees all, Coach sees own teams' members, Contestant sees self |
| GET | `/api/users/<uid>` | 1125-1135 | Auth-gated |
| PATCH | `/api/users/<uid>` | 1137-1180 | self_only vs admin_only field split |
| POST | `/api/users` | 1182-1216 | Admin-create any-role |
| GET | `/api/users/<uid>/problems` | 1502-1564 | Problems assigned to that user (visibility-gated) |

### Teams (port to `app/routers/teams.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/teams` | 1241-1258 | `?mine=1` filter for coach view |
| GET | `/api/teams/<tid>` | 1260-1271 | Hydrated members + coaches |
| POST | `/api/teams` | 1273-1297 | Coach/Admin only |
| PATCH | `/api/teams/<tid>` | 1299-1323 | `can_manage_team()` |
| DELETE | `/api/teams/<tid>` | 1325-1336 | Admin only |
| POST | `/api/teams/<tid>/members` | 1338-1379 | Enforces 3-Member + 1-Reserve cap |
| PATCH | `/api/teams/<tid>/members/<uid>` | 1381-1412 | Promote/demote between Member/Reserve |
| DELETE | `/api/teams/<tid>/members/<uid>` | 1414-1429 | – |
| POST | `/api/teams/<tid>/coaches` | 1431-1455 | – |
| DELETE | `/api/teams/<tid>/coaches/<uid>` | 1457-1468 | – |
| GET | `/api/teams/<tid>/problems` | 1470-1500 | Same view as `/api/problems` but team-scoped |

### Meta + Assignment-options (small routers)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/meta` | 501-521 | Static enums; cache forever |
| GET | `/api/lookup` | 783-825 | URL → problem metadata via `services/lookup.py` |
| GET | `/api/assignment-options` | 827-854 | Active users + active teams; Admin/Coach only |

### Problems + Attempts (port to `app/routers/problems.py` + `attempts.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/problems` | 2112-2193 | **Big query.** 8 filters + rating range + free-text. **Apply skill rules**: composite index `(platform, topic)`, partial index `WHERE via_contest = 0`. Fix N+1 in `row_to_dict` here. |
| GET | `/api/problems/<id>` | 2195-2208 | Single hydrated row |
| POST | `/api/problems` | 2210-2248 | Replaces user/team assignments via helpers |
| PUT/PATCH | `/api/problems/<id>` | 2307-2336 | Same shape as create |
| DELETE | `/api/problems/<id>` | 2338-2347 | – |
| POST | `/api/problems/bulk` | 2349-2400 | **Apply batch-insert skill rule**: switch from per-row INSERT to `executemany` |
| PUT | `/api/problems/<id>/attempt` | 875-978 | Upsert; "Accepted requires phase + time + notes" business rule |

### Contests (port to `app/routers/contests.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/contests/assigned` | 1720-1862 | Heavy phase-rollup query — per-contest phase counts |
| POST | `/api/contests/<id>/tutorial/generate` | 2782-2833 | 🛑 503 stub |
| GET | `/api/contests/<id>/tutorial/status` | 2835-2884 | Returns per-contest tutorial counts |

### Bank (Admin/Coach catalog) (port to `app/routers/bank.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/bank/problems` | 1567-1616 | Same filters as `/api/problems` |
| POST | `/api/bank/problems/<id>/assign` | 1618-1660 | Adds rows to `problem_users` / `problem_teams` |
| GET | `/api/bank/contests` | 1865-1881 | Search by name/platform/notes |
| GET | `/api/bank/contests/<id>` | 1883-1907 | With problem list |
| POST | `/api/bank/contests` | 1909-1931 | – |
| PATCH | `/api/bank/contests/<id>` | 1933-1949 | – |
| DELETE | `/api/bank/contests/<id>` | 1951-1960 | Admin only |
| POST | `/api/bank/contests/<id>/problems` | 1962-1982 | Add problem to contest |
| DELETE | `/api/bank/contests/<id>/problems/<pid>` | 1984-1996 | Remove from contest |
| POST | `/api/bank/contests/<id>/assign` | 1998-2079 | Bulk assign contest's problems to users/teams; **apply upsert skill rule** |

### Tutorials (port to `app/routers/tutorials.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/problems/<id>/tutorial/status` | 2516-2571 | Real — reads `problem_tutorials` table |
| POST | `/api/problems/<id>/tutorial/unlock` | 2573-2614 | Real — writes `tutorial_unlocks` |
| GET | `/api/problems/<id>/tutorial` | 2631-2651 | Calls `tutorials.py` renderer — 🛑 503 until tutorials.py is ported |
| GET | `/api/problems/<id>/tutorial.pdf` | 2653-2689 | Same — 🛑 503 |
| POST | `/api/problems/<id>/tutorial/generate` | 2736-2780 | 🛑 503 stub |
| POST | `/api/contests/<id>/tutorial/generate` | 2782-2833 | 🛑 503 stub |
| GET | `/api/contests/<id>/tutorial/status` | 2835-2884 | Real — aggregate of problem_tutorials counts |

### Stats + Export (port to `app/routers/stats.py` + `export.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/api/stats` | 2466-2499 | Counts grouped by platform/topic/etc |
| GET | `/api/export/xlsx` | 2402-2464 | openpyxl XLSX response |

### Misc (port to `app/main.py`)

| Verb | Path | Lines | Notes |
|---|---|---|---|
| GET | `/` | 474-484 | Serve `static/index.html` (FastAPI StaticFiles) |
| GET | `/files/<path>` | 486-498 | Serve project-relative files (tutorial PDFs) |

---

## 2. Skill-rule applications committed for this port

| Source location | Skill rule | Action |
|---|---|---|
| `row_to_dict` (lines 287-340) | data-n-plus-one | Replace 3 sub-queries-per-row with one `json_agg` join per page |
| `/api/problems` (2112-2193) | query-composite-indexes + query-partial-indexes | Add `(platform, topic)` composite + `WHERE via_contest = 0` partial index in migration |
| `/api/problems/bulk` (2349-2400) | data-batch-inserts | Use `executemany` |
| `/api/problems/<id>/attempt` (875-978) | data-upsert | Already uses ON CONFLICT — verify deterministic |
| `_spawn_worker` (2702-2719) | n/a | 🛑 returns 503 until worker ported |
| Every request | lock-short-transactions | Wrap each request in one short transaction via FastAPI dep |
| Every request | conn-pooling | Use `psycopg_pool.AsyncConnectionPool` with min_size=2 max_size=10 |
| Every connection | conn-prepared-statements | `prepare_threshold=None` (works with transaction pooler when we migrate to it) |

---

## 3. New `/backend` structure being built

```
backend/
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── security.py
│   ├── deps.py
│   ├── errors.py
│   ├── schemas/
│   │   ├── auth.py, user.py, team.py, problem.py, attempt.py,
│   │   ├── contest.py, tutorial.py, assignment.py, meta.py, stats.py
│   ├── repositories/
│   │   ├── users.py, teams.py, problems.py, contests.py, tutorials.py
│   ├── routers/
│   │   ├── auth.py, users.py, teams.py, problems.py,
│   │   ├── contests.py, bank.py, tutorials.py,
│   │   ├── meta.py, assignment.py, stats.py, export.py
│   └── services/
│       ├── lookup.py            # URL → CF metadata
│       └── tutorials.py         # gate/audience logic (stub until worker ported)
├── migrations/
│   └── 0001_initial.sql
└── scripts/
    ├── migrate.py
    └── create_admin.py
```
