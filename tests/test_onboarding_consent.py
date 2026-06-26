"""Tests for the consent-gated enrollment loop (A1).

Covers the engine side of "close the loop":
- a partner pre-seeded `pending_consent` profile is prompted (not read as consent) on first contact;
- "Yes" from a partner-enrolled farmer records consent=granted without re-creating a membership;
- a self-onboarding farmer's "Yes" finalizes the profile and auto-assigns a single matching cohort;
- auto-assign skips when zero or more than one active cohort matches the district.
"""

import os
import sys
import types
import importlib.util
from pathlib import Path


def _stub_modules():
    common = types.ModuleType("common")
    sys.modules["common"] = common
    wa = types.ModuleType("common.whatsapp")
    wa.send_whatsapp_message = lambda *a, **k: True
    wa.send_whatsapp_list = lambda *a, **k: True
    wa.send_whatsapp_buttons = lambda *a, **k: True
    wa.VOICE_RECEIVED_ACK = {"hi": "ACK"}
    sys.modules["common.whatsapp"] = wa
    al = types.ModuleType("common.allowlist")
    al.is_approved_user = lambda *a, **k: True
    al.allowlist_expiry_hint = lambda *a, **k: ""
    sys.modules["common.allowlist"] = al
    hl = types.ModuleType("common.district_helplines")
    hl.maybe_append_helpline_footer = lambda text, *a, **k: text
    sys.modules["common.district_helplines"] = hl
    out = types.ModuleType("output")
    out.text_to_speech = lambda *a, **k: None
    out.truncate_for_voice = lambda s, *a, **k: s
    out.voice_truncation_prefix = ""
    sys.modules["output"] = out
    an = types.ModuleType("analyzer")
    an.process_image_message = lambda *a, **k: "x"
    sys.modules["analyzer"] = an


class FakeTable:
    def __init__(self, cohorts=None):
        self.puts = []
        self.updates = []
        self._cohorts = cohorts or []

    def put_item(self, Item=None, ConditionExpression=None, **k):
        self.puts.append(Item)
        return {}

    def update_item(self, **k):
        self.updates.append(k)
        return {}

    def get_item(self, **k):
        return {}

    def query(self, **k):
        return {"Items": list(self._cohorts)}


def _load_handler():
    os.environ.setdefault("TABLE_NAME", "tbl")
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    _stub_modules()
    path = Path(__file__).resolve().parents[1] / "src" / "processor" / "handler.py"
    spec = importlib.util.spec_from_file_location("processor_handler_consent_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _values(update_kwargs):
    return update_kwargs.get("ExpressionAttributeValues", {})


def test_pending_consent_first_contact_prompts_and_moves_to_consent():
    mod = _load_handler()
    mod.table = FakeTable()
    profile = {
        "onboarding_state": "pending_consent",
        "dialect": "en",
        "location": "Latur",
        "crop": "Cotton",
        "consent": "pending",
        "consentSource": "partner",
    }
    resp = mod.handle_onboarding("919800000012", "Hi", profile)
    assert resp["type"] == "buttons"
    assert "Latur" in resp["content"] and "Cotton" in resp["content"]
    # the first "Hi" must move them to the consent state, not be read as the answer
    assert any(_values(u).get(":onboarding_state") == "consent" for u in mod.table.updates)


def test_consent_yes_partner_grants_without_reassigning():
    mod = _load_handler()
    mod.table = FakeTable()
    profile = {
        "onboarding_state": "consent",
        "dialect": "en",
        "location": "Latur",
        "crop": "Cotton",
        "consentSource": "partner",
    }
    resp = mod.handle_onboarding("919800000012", "Yes", profile)
    assert resp["type"] == "text"
    granted = [u for u in mod.table.updates if _values(u).get(":consent") == "granted"]
    assert granted, "partner consent should be recorded as granted"
    assert _values(granted[0]).get(":onboarding_complete") is True
    # partner path must NOT write a fresh membership (it already exists)
    assert not any((p or {}).get("SK") == "MEMBERSHIP" for p in mod.table.puts)


def test_consent_yes_self_onboard_creates_profile_and_auto_assigns_single_cohort():
    mod = _load_handler()
    mod.table = FakeTable(cohorts=[{"cohortId": "c1", "tenantId": "t1", "district": "Latur"}])
    profile = {
        "onboarding_state": "consent",
        "dialect": "en",
        "location": "Latur",
        "crop": "Cotton",
        # no consentSource -> self
    }
    resp = mod.handle_onboarding("919800000012", "Yes", profile)
    assert resp["type"] == "text"
    profiles = [p for p in mod.table.puts if (p or {}).get("SK") == "PROFILE"]
    assert profiles and profiles[0]["consent"] == "granted"
    memberships = [p for p in mod.table.puts if (p or {}).get("SK") == "MEMBERSHIP"]
    assert memberships and memberships[0]["cohortId"] == "c1"
    assert memberships[0]["PK"] == "PHONE#919800000012"


def test_auto_assign_skips_when_multiple_cohorts_match():
    mod = _load_handler()
    mod.table = FakeTable(cohorts=[
        {"cohortId": "c1", "tenantId": "t1", "district": "Latur"},
        {"cohortId": "c2", "tenantId": "t2", "district": "Latur"},
    ])
    mod.auto_assign_cohort("919800000012", "Latur", "Cotton")
    assert not any((p or {}).get("SK") == "MEMBERSHIP" for p in mod.table.puts)


def test_auto_assign_writes_nothing_when_no_cohort_matches():
    mod = _load_handler()
    mod.table = FakeTable(cohorts=[])
    mod.auto_assign_cohort("919800000012", "Latur", "Cotton")
    assert mod.table.puts == []
