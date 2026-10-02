"""CI runs the whole test suite, not a hand-picked subset."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_runs_every_test():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    runs = [s.get("run", "") for job in wf["jobs"].values() for s in job["steps"]]
    pytest_runs = [r for r in runs if "pytest" in r and "pip install" not in r]
    assert pytest_runs, "CI has no pytest step"
    for r in pytest_runs:
        args = r.split("pytest", 1)[1].split()
        targets = [a for a in args if not a.startswith("-")]
        assert targets == ["tests/"], r
