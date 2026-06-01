#!/bin/bash
# One-shot script to initialize git, commit, and push to
# git@github.com:Enigma277/ICPC-Training.git
#
# Usage from this folder:
#     bash setup_and_push.sh
#
# Prereqs:
#   - You've created the empty repo at https://github.com/Enigma277/ICPC-Training
#     (Don't tick "Initialize this repository with a README" — we already have one.)
#   - Your SSH key is registered with GitHub. Test with: ssh -T git@github.com

set -euo pipefail

cd "$(dirname "$0")"

# 0) Wipe any half-baked .git directory left over from earlier attempts.
if [ -d .git ]; then
  echo "[setup] removing existing .git/ ..."
  rm -rf .git
fi

# 1) Sanity: refuse to run if a known secret would be committed.
for f in .flask_secret .cf_api_key problems.db; do
  if [ -e "$f" ] && ! grep -qF "$f" .gitignore; then
    echo "[setup] ABORT: $f exists but isn't in .gitignore"; exit 1
  fi
done

# 2) Init repo on main.
git init -q -b main
git config user.email "${GIT_EMAIL:-deepak.gour@newtonschool.co}"
git config user.name  "${GIT_NAME:-Deepak Gour}"

# 3) Stage and check what's about to be committed.
git add -A
echo
echo "=== About to commit ($(git diff --cached --name-only | wc -l | tr -d ' ') files) ==="
git diff --cached --stat | tail -30
echo

# 4) Make sure no obvious secret slipped in.
if git diff --cached --name-only | grep -E '^(\.flask_secret|\.cf_api_key|problems\.db|.*\.env)$' >/dev/null; then
  echo "[setup] ABORT: secret-looking file is staged"; exit 1
fi

# 5) Commit.
git commit -q -m "Initial commit: ICPC Training Problem Repository

Flask + libSQL (Turso) backend with REST CRUD, Excel export, and
auth/teams. Frontend is a single static HTML page (no build step).

Includes Vercel deployment config, GitHub Actions for CI + auto-deploy,
and a seed script to migrate from local SQLite to Turso."

# 6) Add remote (idempotent) and push.
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin git@github.com:Enigma277/ICPC-Training.git
else
  git remote add origin git@github.com:Enigma277/ICPC-Training.git
fi

echo "[setup] pushing to github.com:Enigma277/ICPC-Training (main) ..."
git push -u origin main

echo
echo "=== Done ==="
echo "View at: https://github.com/Enigma277/ICPC-Training"
