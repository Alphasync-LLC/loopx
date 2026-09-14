from __future__ import annotations

import json
from html import escape, unescape


USER_TODO_HEADER_MARKERS = (
    "user todo",
    "owner review reading queue",
    "owner reading queue",
)
AGENT_TODO_HEADER_MARKERS = (
    "agent todo",
    "codex todo",
    "project agent todo",
)
TODO_ARCHIVE_HEADER_MARKERS = (
    "todo archive",
    "work archive",
    "completed archive",
    "completed work",
    "完成归档",
    "待办归档",
)


def markdown_frontmatter_string(value: str) -> str:
    encoded = json.dumps(value, ensure_ascii=False)
    for separator in ("\x85", "\u2028", "\u2029"):
        encoded = encoded.replace(separator, f"\\u{ord(separator):04x}")
    return encoded


def markdown_blockquote(value: str) -> str:
    return "\n".join(f"> {escape(line, quote=False)}" for line in value.splitlines())


def active_state_section_text(state_text: str, heading: str) -> str:
    lines = state_text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.rstrip(" \t") == f"## {heading}"
        ) + 1
    except StopIteration:
        return ""
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    section_lines = [line for line in lines[start:end] if line]
    if heading == "Objective" and section_lines and all(
        line.startswith("> ") for line in section_lines
    ):
        text = " ".join(unescape(line[2:]) for line in section_lines)
    else:
        text = " ".join(
            line.strip().removeprefix("- ").strip()
            for line in section_lines
            if line.strip() and not line.lstrip().startswith("<!--")
        )
    return " ".join(text.split())


def parse_state_frontmatter(state_text: str) -> dict[str, str]:
    if not state_text.startswith("---"):
        return {}
    parts = state_text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def todo_role_for_heading(heading: str) -> str | None:
    normalized = heading.strip().lower()
    if any(marker in normalized for marker in TODO_ARCHIVE_HEADER_MARKERS):
        return None
    if any(marker in normalized for marker in USER_TODO_HEADER_MARKERS):
        return "user"
    if any(marker in normalized for marker in AGENT_TODO_HEADER_MARKERS):
        return "agent"
    return None
