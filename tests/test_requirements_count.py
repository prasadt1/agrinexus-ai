"""Every requirement count stated in the docs matches docs/requirements.md."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("count_requirements", ROOT / "scripts" / "count_requirements.py")
count_requirements = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(count_requirements)

CLAIM_RE = re.compile(r"(\d{2,4})\**\s*(?:active\s+)?(?:EARS\s+)?requirements|requirements[^|\n]{0,40}\|\s*\**(\d{2,4})\**")
DOCS = ["README.md", "docs/IMPLEMENTATION-QUALITY-METRICS.md"]


def _claims(path):
    out = []
    for line in (ROOT / path).read_text().splitlines():
        if "requirements" not in line.lower() or ("EARS" not in line and "requirements.md" not in line):
            continue
        for m in CLAIM_RE.finditer(line):
            out.append(int(m.group(1) or m.group(2)))
    return out


def test_counts_are_consistent():
    c = count_requirements.count(ROOT / "docs" / "requirements.md")
    assert c["active"] == c["defined"] - len(c["inactive"])
    assert set(c["inactive"]) == {"REQ-GUARD-002", "REQ-GUARD-004"}


def test_docs_state_the_active_count():
    active = count_requirements.count(ROOT / "docs" / "requirements.md")["active"]
    for path in DOCS:
        claims = _claims(path)
        assert claims, f"no requirement count found in {path}"
        assert set(claims) == {active}, (path, claims, active)
