"""Infrastructure claims in the docs match template.yaml."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _waf_protected_apis():
    t = (ROOT / "template.yaml").read_text()
    return {api for api in ("WhatsAppApi", "WebChatApi") if f"/restapis/${{{api}}}/stages" in t}


def test_readme_claims_waf_only_where_attached():
    protected = _waf_protected_apis()
    assert "WebChatApi" in protected
    for line in (ROOT / "README.md").read_text().splitlines():
        if "WAF" in line and "webhook" in line.lower() and "WhatsAppApi" not in protected:
            low = line.lower()
            assert "no waf" in low or "/chat" in low or "web chat" in low, line
