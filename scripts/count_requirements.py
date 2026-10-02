#!/usr/bin/env python3
"""Count EARS requirements in docs/requirements.md.

A requirement is a line starting with **REQ-AREA-NNN**. It is inactive when the
text right after the ID marks it retired, folded, superseded, removed or withdrawn.
IDs that are only mentioned (for example in a "removed" list) are not counted.
"""
import re
import sys
from pathlib import Path

DEF_RE = re.compile(r"^\*\*(REQ-[A-Z]+-\d+)\*\*(.*)$", re.M)
INACTIVE_RE = re.compile(r"^\s*\((?:retired|folded|superseded|removed|withdrawn)\b", re.I)


def count(path: Path) -> dict:
    defs = DEF_RE.findall(path.read_text())
    ids = [i for i, _ in defs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate requirement IDs: {sorted({i for i in ids if ids.count(i) > 1})}")
    inactive = [i for i, rest in defs if INACTIVE_RE.match(rest)]
    return {"defined": len(ids), "inactive": inactive, "active": len(ids) - len(inactive)}


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs" / "requirements.md"
    c = count(p)
    print(f"{c['active']} active ({c['defined']} defined, inactive: {', '.join(c['inactive']) or 'none'})")
