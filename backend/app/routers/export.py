"""
GET /api/export/xlsx — XLSX dump of the current Assigned Problems view.
legacy/app.py:2402-2459.

Respects the same filter/search/sort query params as `/api/problems`.
Streams the file as a StreamingResponse so we don't buffer the whole bytes
in memory longer than necessary.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.deps import ConnDep, CurrentUser
from app.repositories import problems as problems_repo
from app.schemas.problem import ProblemFilters

router = APIRouter(tags=["export"])

# (db_column, header_label, width) — matches legacy EXPORT_COLUMNS.
_EXPORT_COLUMNS: list[tuple[str, str, int]] = [
    ("id",             "ID",             8),
    ("name",           "Name",           38),
    ("url",            "URL",            50),
    ("platform",       "Platform",       14),
    ("contest_type",   "Contest Type",   18),
    ("rating",         "Rating",         8),
    ("difficulty",     "Difficulty",     14),
    ("topic",          "Topic",          18),
    ("sub_topic",      "Sub-topic",      28),
    ("tags",           "Tags",           28),
    ("importance",     "Importance",     12),
    ("assigned_users", "Assigned Users", 28),
    ("assigned_teams", "Assigned Teams", 28),
    ("notes",          "Notes",          38),
    ("date_added",     "Added",          18),
]


def _decode_tags(raw: object) -> list[str]:
    """The `problems.tags` column is text-encoded JSON; decode for export."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            return [t.strip() for t in raw.split(",") if t.strip()]
    return []


def _cell_value(item: dict, key: str) -> object:
    """Render the spreadsheet cell value for a column."""
    if key == "assigned_users":
        return ", ".join(u["name"] for u in (item.get("assigned_users") or []))
    if key == "assigned_teams":
        summaries = item.get("team_summary") or []
        if summaries:
            # Prefer "Team (solved/total)" format when available (admin view).
            return ", ".join(
                f"{t['team_name']} ({t['solved']}/{t['total']})"
                for t in summaries
                if t.get("team_id") is not None
            )
        return ", ".join(t["name"] for t in (item.get("assigned_teams") or []))
    if key == "tags":
        return ", ".join(_decode_tags(item.get("tags")))
    v = item.get(key)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if isinstance(v, datetime):
        return v.replace(tzinfo=None).isoformat(sep=" ", timespec="minutes")
    return v


@router.get("/export/xlsx")
async def export_xlsx(
    me: CurrentUser,
    conn: ConnDep,
    filters: Annotated[ProblemFilters, Query()],
) -> StreamingResponse:
    """Stream an .xlsx of the same problems /api/problems would return."""
    rows, _total = await problems_repo.list_assigned(conn, filters, me)
    items = await problems_repo.hydrate_many(conn, rows, me)

    wb = Workbook()
    ws = wb.active
    ws.title = "Assigned Problems"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4F6F")

    for col_idx, (_, label, _w) in enumerate(_EXPORT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r, item in enumerate(items, start=2):
        for col_idx, (key, _label, _w) in enumerate(_EXPORT_COLUMNS, start=1):
            ws.cell(row=r, column=col_idx, value=_cell_value(item, key))

    for col_idx, (_, _label, width) in enumerate(_EXPORT_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"icpc_assigned_problems_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
