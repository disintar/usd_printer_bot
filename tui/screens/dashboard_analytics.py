"""Helpers for rendering analytics table in dashboard."""
from __future__ import annotations

import logging
from typing import Any

from textual.widgets import DataTable

logger = logging.getLogger(__name__)


class DashboardAnalyticsService:
    """Populate dashboard analytics table from API responses."""

    @classmethod
    def populate(cls, table: DataTable, api: Any, asset_id: str) -> None:
        table.clear()
        if asset_id == "USDt":
            table.add_row("System", "Cash ticker USDt has no adviser analytics. Select a tradeable asset.")
            return
        try:
            logger.info("DashboardAnalyticsService.populate asset_id=%s", asset_id)
            analysis = api.get_advisor_analysis(asset_id)
            notes = analysis.get("advisor_notes", [])
            if isinstance(notes, list):
                cls._add_adviser_rows(table, analysis, notes)
            reasoning = api.get_reasoning(asset_id)
            cls._add_agent_rows(table, reasoning)
        except Exception as exc:
            logger.warning("DashboardAnalyticsService.populate failed asset_id=%s error=%s", asset_id, exc)
            table.add_row("Error", f"Analytics unavailable for {asset_id}")

    @staticmethod
    def _add_adviser_rows(table: DataTable, analysis: dict[str, Any], notes: list[Any]) -> None:
        recommendation = str(analysis.get("recommendation", "")).strip()
        summary = str(analysis.get("summary", "")).strip()
        if recommendation:
            table.add_row("Committee", f"Recommendation: {recommendation.upper()}")
        if summary:
            table.add_row("Committee", summary)
        for note in notes:
            if not isinstance(note, dict):
                continue
            name = str(note.get("name", note.get("advisor_id", "")))
            thought = str(note.get("thought", ""))
            table.add_row(f"Adviser: {name}", thought)

    @staticmethod
    def _add_agent_rows(table: DataTable, reasoning: dict[str, Any]) -> None:
        recommendation = str(reasoning.get("recommendation", "")).strip()
        lines = reasoning.get("reasoning", [])
        if recommendation:
            table.add_row("Agent Engine", f"Recommendation: {recommendation}")
        if not isinstance(lines, list):
            return
        for line in lines:
            table.add_row("Agent Engine", str(line))
