from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from loguru import logger


@dataclass(frozen=True)
class AdvisorDefinition:
    """Single advisor definition loaded from the markdown config."""

    advisor_id: str
    name: str
    category: str
    role: str
    style: list[str]
    tags: list[str]
    primary_tag: str
    tabler_icon: str


class AdvisorsService:
    """Loads advisor personas from the markdown configuration file."""

    CONFIG_PATH = Path(settings.BASE_DIR) / "config" / "advisors.md"
    _HEADER_RE = re.compile(r"^### advisor/([a-z0-9_]+)$")
    _FIELD_RE = re.compile(r"^- ([a-z_]+):(?: (.+))?$")
    PRIMARY_TAG_LABELS: dict[str, str] = {
        "investments": "💰 Investments",
        "business": "🏢 Business",
        "books": "📚 Books",
        "films": "🎬 Films",
        "anime": "🧠 Anime",
        "games": "🎮 Games",
    }
    PRIMARY_TAG_ALIASES: dict[str, str] = {
        "investment": "investments",
        "invest": "investments",
        "film": "films",
    }
    PRIMARY_TAG_IDS: tuple[str, ...] = tuple(PRIMARY_TAG_LABELS.keys())
    _cached_advisors: list[AdvisorDefinition] | None = None
    _cached_mtime_ns: int | None = None

    @classmethod
    def list_advisors(cls) -> list[AdvisorDefinition]:
        """Return all advisors from the markdown config."""
        started_at = time.perf_counter()
        try:
            mtime_ns = cls.CONFIG_PATH.stat().st_mtime_ns
        except OSError:
            mtime_ns = None

        if (
            cls._cached_advisors is not None
            and mtime_ns is not None
            and cls._cached_mtime_ns == mtime_ns
        ):
            logger.info(
                "advisors.list_advisors cache=hit advisors={} total_ms={}",
                len(cls._cached_advisors),
                round((time.perf_counter() - started_at) * 1000),
            )
            return list(cls._cached_advisors)

        read_started = time.perf_counter()
        content = cls.CONFIG_PATH.read_text(encoding="utf-8")
        read_ms = round((time.perf_counter() - read_started) * 1000)

        parse_started = time.perf_counter()
        advisors = cls._parse_markdown(content)
        parse_ms = round((time.perf_counter() - parse_started) * 1000)

        cls._cached_advisors = list(advisors)
        cls._cached_mtime_ns = mtime_ns
        logger.info(
            "advisors.list_advisors cache=miss advisors={} read_ms={} parse_ms={} total_ms={}",
            len(advisors),
            read_ms,
            parse_ms,
            round((time.perf_counter() - started_at) * 1000),
        )
        return list(advisors)

    @classmethod
    def list_advisors_by_primary_tag(cls, raw_primary_tag: str | None) -> list[AdvisorDefinition]:
        """Return advisors filtered by primary tag when provided."""
        advisors = cls.list_advisors()
        if raw_primary_tag is None or raw_primary_tag.strip() == "":
            return advisors
        primary_tag = cls._normalize_primary_tag(raw_primary_tag)
        if primary_tag not in cls.PRIMARY_TAG_LABELS:
            allowed = ", ".join(cls.PRIMARY_TAG_IDS)
            raise ValueError(f"Invalid primary_tag '{raw_primary_tag}'. Allowed: {allowed}")
        return [advisor for advisor in advisors if advisor.primary_tag == primary_tag]

    @classmethod
    def get_unique_primary_tags(cls) -> list[tuple[str, str]]:
        """Return unique primary tags with emoji: (tag, emoji_label)."""
        advisors = cls.list_advisors()
        seen: set[str] = set()
        tags = []
        for advisor in advisors:
            if advisor.primary_tag not in seen:
                seen.add(advisor.primary_tag)
                tags.append(
                    (
                        advisor.primary_tag,
                        cls.PRIMARY_TAG_LABELS.get(advisor.primary_tag, advisor.primary_tag),
                    )
                )
        return tags

    @classmethod
    def _parse_markdown(cls, content: str) -> list[AdvisorDefinition]:
        """Parse advisors registry markdown."""
        advisors: list[AdvisorDefinition] = []
        current_id: str | None = None
        current_category: str | None = None
        current_name: str | None = None
        current_role: str | None = None
        current_style: list[str] = []
        current_tags: list[str] = []
        current_list_field: str | None = None

        def flush_current() -> None:
            nonlocal current_id, current_category, current_name, current_role, current_style, current_tags, current_list_field, current_primary_tag, current_tabler_icon
            if current_id:
                advisors.append(
                    AdvisorDefinition(
                        advisor_id=current_id,
                        name=current_name,
                        category=current_category,
                        role=current_role,
                        style=list(current_style),
                        tags=list(current_tags),
                        primary_tag=current_primary_tag,
                        tabler_icon=current_tabler_icon,
                    )
                )
            current_id = None
            current_category = None
            current_name = None
            current_role = None
            current_style = []
            current_tags = []
            current_list_field = None
            current_primary_tag = ""
            current_tabler_icon = ""

        current_primary_tag = ""
        current_tabler_icon = ""
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("# "):
                continue
            if line.startswith("## "):
                current_list_field = None
                continue

            header_match = cls._HEADER_RE.match(line)
            if header_match:
                flush_current()
                current_id = header_match.group(1)
                continue

            field_match = cls._FIELD_RE.match(line)
            if field_match and current_id:
                field_name = field_match.group(1)
                field_value = (field_match.group(2) or "").strip()
                current_list_field = None

                if field_name == "category":
                    current_category = field_value
                    continue
                if field_name == "name":
                    current_name = field_value
                    continue
                if field_name == "role":
                    current_role = field_value
                    continue
                if field_name == "style":
                    current_list_field = "style"
                    continue
                if field_name == "tags":
                    current_list_field = "tags"
                    continue
                if field_name == "primary_tag":
                    current_primary_tag = cls._normalize_primary_tag(field_value)
                    continue
                if field_name == "tabler_icon":
                    current_tabler_icon = field_value
                    continue
                continue

            if current_id and current_list_field and raw_line.startswith("  - "):
                item_value = raw_line[4:].strip()
                if current_list_field == "style":
                    current_style.append(item_value)
                    continue
                if current_list_field == "tags":
                    current_tags.append(item_value)
                    continue

        flush_current()
        cls._validate_advisors(advisors)
        return advisors

    @staticmethod
    def _validate_advisors(advisors: list[AdvisorDefinition]) -> None:
        """Validate parsed advisors."""
        for advisor in advisors:
            if not advisor.category:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing category")
            if not advisor.name:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing name")
            if not advisor.role:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing role")
            if not advisor.style:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing style")
            if not advisor.tags:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing tags")
            if not advisor.primary_tag:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing primary_tag")
            if advisor.primary_tag not in AdvisorsService.PRIMARY_TAG_LABELS:
                allowed = ", ".join(AdvisorsService.PRIMARY_TAG_LABELS.keys())
                raise ValueError(
                    f"Advisor '{advisor.advisor_id}' has invalid primary_tag '{advisor.primary_tag}'. "
                    f"Allowed: {allowed}"
                )
            if not advisor.tabler_icon:
                raise ValueError(f"Advisor '{advisor.advisor_id}' is missing tabler_icon")

    @classmethod
    def _normalize_primary_tag(cls, raw_value: str) -> str:
        normalized = raw_value.strip().lower().replace(" ", "_")
        return cls.PRIMARY_TAG_ALIASES.get(normalized, normalized)
