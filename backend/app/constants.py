"""
Project-wide enum constants — the single source of truth referenced by
`/api/meta`, the Pydantic field validators, and any business-rule checks.

Mirror values from legacy/app.py:60-104 — change here propagates everywhere.
"""

from __future__ import annotations

from typing import Literal

# --- Roles / team caps ------------------------------------------------------

UserRole = Literal["Admin", "Coach", "Contestant"]
USER_ROLES: tuple[UserRole, ...] = ("Admin", "Coach", "Contestant")

TeamRole = Literal["Member", "Reserve"]
TEAM_ROLES: tuple[TeamRole, ...] = ("Member", "Reserve")

MAX_MEMBERS_PER_TEAM = 3
MAX_RESERVES_PER_TEAM = 1


# --- Problem enums ----------------------------------------------------------

PLATFORMS: tuple[str, ...] = (
    "Codeforces", "AtCoder", "CodeChef", "ICPC Archive", "Kattis", "UVa",
    "SPOJ", "CSES", "Google Code Jam", "Meta Hacker Cup", "USACO",
    "HackerEarth", "Other",
)

CONTEST_TYPES: tuple[str, ...] = (
    "ICPC World Finals", "Asia West Finals", "ICPC Regional",
    "Codeforces Round", "AtCoder ABC", "AtCoder ARC", "AtCoder AGC",
    "CodeChef Long", "CodeChef Cook-Off", "Google Code Jam",
    "Meta Hacker Cup", "Practice", "Gym", "Other",
)

DIFFICULTIES: tuple[str, ...] = (
    "Easy", "Normal", "Normal-Hard", "Hard", "Very Hard", "Challenge",
)

TOPICS: tuple[str, ...] = (
    "Ad-hoc", "Implementation", "Greedy", "Constructive",
    "Math", "Number Theory", "Combinatorics", "Probability", "Game Theory",
    "Graph", "Tree", "DP", "Strings", "Geometry",
    "Data Structures", "Segment Tree", "DSU", "Trie",
    "Binary Search", "Two Pointers", "Sorting",
    "Bitmask", "Flows / Matching", "FFT / NTT", "Misc",
)

IMPORTANCE_LEVELS: tuple[str, ...] = (
    "Critical", "Very Important", "Important", "Normal",
)

ROLES_SUGGESTED: tuple[str, ...] = (
    "Algo", "DS", "Math", "Geometry", "Implementation", "Any",
)

STATUSES: tuple[str, ...] = (
    "Todo", "In Progress", "Done", "Upsolve", "Skipped",
)


# --- Per-user attempt enums (problem_attempts table) ------------------------

ATTEMPT_STATUSES: tuple[str, ...] = (
    "TODO", "Accepted", "Wrong Answer", "TLE", "RE",
)

ATTEMPT_PHASES: tuple[str, ...] = (
    "During Contest", "Upsolve",
)

PROBLEM_FACED: tuple[str, ...] = (
    "Stuck in Implementation",
    "Stuck in Logic",
    "Stuck in Both",
    "Didn't know the necessary topic",
    "Couldn't understand problem",
    "Didn't Attempt",
    "No Problem Faced",
)
