"""Source lines name documents by their metadata title, and scripts/kb-titles.py writes those titles."""
import importlib.util
import io
import json
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import advice_filter as af  # noqa: E402
from common import district_helplines as dh  # noqa: E402
from common.source_labels import source_labels, source_line  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _ref(uri, title=None):
    ref = {"location": {"s3Location": {"uri": uri}}}
    if title is not None:
        ref["metadata"] = {"x-amz-bedrock-kb-source-uri": uri, "title": title}
    return ref


@pytest.fixture(autouse=True)
def _no_metrics(monkeypatch):
    monkeypatch.setattr(af, "_emit_metric", lambda *_a, **_k: None)


class TestLabels:
    def test_title_from_metadata_else_file_name(self):
        citations = [
            {"retrievedReferences": [_ref("s3://kb/en/cotton-08-e75ba3c0.pdf", "  PAU Package of\nPractices  ")]},
            {"retrievedReferences": [_ref("s3://kb/en/icar-advisory.pdf"), _ref("s3://kb/en/x.pdf", "")]},
        ]
        assert source_labels(citations) == ["PAU Package of Practices", "icar-advisory.pdf", "x.pdf"]

    def test_duplicates_and_empty(self):
        ref = _ref("s3://kb/a.pdf", "Cotton IPM")
        assert source_labels([{"retrievedReferences": [ref, ref]}]) == ["Cotton IPM"]
        assert source_labels(None) == [] and source_line([], "en") == ""

    def test_line_per_language_and_cap(self):
        assert source_line(["A"], "mr") == "स्त्रोत: A"
        assert source_line([str(i) for i in range(7)], "en") == "Source: 0, 1, 2, 3, 4 …"


class TestFilterKeepsTheSourceLine:
    def test_title_is_not_filtered_and_sits_above_the_footer(self):
        out = af.filter_advice(
            "Install yellow sticky traps.", "en", "whatsapp_text",
            source_line="Source: Neonicotinoid use in cotton, soybean-04-855fe8ec.pdf",
        )
        assert out.startswith(
            "Install yellow sticky traps.\n\nSource: Neonicotinoid use in cotton, soybean-04-855fe8ec.pdf\n\n"
            + dh.REFERRAL_LINES["answer"]["en"]
        )

    def test_model_referral_before_the_source_line_is_still_dropped(self):
        out = af.filter_advice(
            "Install traps. For chemical control, contact your local KVK for the right product.",
            "en", "whatsapp_text", source_line="Source: Cotton IPM",
        )
        assert out.count("KVK") == 1 and "Install traps.\n\nSource: Cotton IPM\n\n" in out

    def test_no_source_line_on_a_refusal(self):
        out = af.filter_advice("No information.", "en", "whatsapp_text", add_referral=False, source_line="")
        assert out == "No information."


@pytest.fixture()
def kb_titles(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("kb_titles", REPO / "scripts" / "kb-titles.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MAPPING", tmp_path / "kb-titles.json")
    monkeypatch.setattr(mod, "REPO", tmp_path)
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("filename,title\nrajendran-2018-cotton-pests.pdf,Insect Pests of Cotton\n", encoding="utf-8")
    monkeypatch.setattr(mod, "MANIFEST", manifest)
    monkeypatch.setattr(mod, "pdf_suggestion", lambda data: ("Cotton Pest Advisory", "pdf title field"))
    return mod


class FakeS3:
    def __init__(self, keys, existing=None):
        self.objects = {k: b"%PDF" for k in keys}
        self.objects.update(existing or {})
        self.puts = []

    def get_paginator(self, _name):
        objects = self.objects

        class P:
            def paginate(self, Bucket, Prefix):
                yield {"Contents": [{"Key": k} for k in sorted(objects) if k.startswith(Prefix)]}

        return P()

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, **kw):
        self.puts.append(kw)


class FakeAgent:
    def __init__(self):
        self.jobs = []

    def list_data_sources(self, knowledgeBaseId):
        return {"dataSourceSummaries": [{"dataSourceId": "DS1"}]}

    def get_data_source(self, knowledgeBaseId, dataSourceId):
        return {"dataSource": {"dataSourceId": dataSourceId, "dataSourceConfiguration": {
            "s3Configuration": {"bucketArn": "arn:aws:s3:::kb-bucket", "inclusionPrefixes": ["en/"]}}}}

    def start_ingestion_job(self, knowledgeBaseId, dataSourceId):
        self.jobs.append(dataSourceId)
        return {"ingestionJob": {"ingestionJobId": "J1", "status": "STARTING"}}


class TestKbTitlesScript:
    KEYS = ["en/new-sources/rajendran-2018-cotton-pests.pdf", "en/cotton-08-e75ba3c0.pdf", "en/notes.md", "other/x.pdf"]

    def test_draft_suggests_titles_and_skips_sidecars_and_other_prefixes(self, kb_titles):
        existing = {"en/notes.md.metadata.json": json.dumps({"metadataAttributes": {"title": "Field notes"}}).encode()}
        s3, agent = FakeS3(self.KEYS, existing), FakeAgent()
        mapping = kb_titles.draft(s3, kb_titles.s3_data_sources(agent, "KB"))
        assert mapping == {
            "s3://kb-bucket/en/cotton-08-e75ba3c0.pdf": {"title": "Cotton Pest Advisory", "suggested_by": "pdf title field"},
            "s3://kb-bucket/en/new-sources/rajendran-2018-cotton-pests.pdf": {"title": "Insect Pests of Cotton", "suggested_by": "kb_manifest.csv"},
            "s3://kb-bucket/en/notes.md": {"title": "Field notes", "suggested_by": "existing metadata"},
        }
        assert s3.puts == [] and agent.jobs == []

    def test_draft_keeps_titles_already_edited(self, kb_titles):
        kb_titles.MAPPING.write_text(json.dumps({"s3://kb-bucket/en/cotton-08-e75ba3c0.pdf": {"title": "PAU Kharif 2024"}}))
        mapping = kb_titles.draft(FakeS3(self.KEYS[1:2]), kb_titles.s3_data_sources(FakeAgent(), "KB"))
        assert mapping["s3://kb-bucket/en/cotton-08-e75ba3c0.pdf"]["title"] == "PAU Kharif 2024"

    def test_apply_writes_sidecars_for_titled_documents_and_starts_one_job(self, kb_titles):
        kb_titles.MAPPING.write_text(json.dumps({
            "s3://kb-bucket/en/cotton-08-e75ba3c0.pdf": {"title": "PAU Package of Practices, Kharif 2024"},
            "s3://kb-bucket/en/notes.md": {"title": ""},
            "s3://other-bucket/y.pdf": {"title": "Elsewhere"},
        }))
        s3, agent = FakeS3([]), FakeAgent()
        assert kb_titles.apply(s3, agent, "KB", kb_titles.s3_data_sources(agent, "KB")) == 0
        assert [(p["Key"], json.loads(p["Body"])) for p in s3.puts] == [
            ("en/cotton-08-e75ba3c0.pdf.metadata.json", {"metadataAttributes": {"title": "PAU Package of Practices, Kharif 2024"}})
        ]
        assert agent.jobs == ["DS1"]

    @pytest.mark.parametrize("raw, want", [
        ("Microsoft Word - IPM Cotton 2024.docx", "IPM Cotton 2024"),
        ("  Cotton   pests\n", "Cotton pests"),
    ])
    def test_clean(self, kb_titles, raw, want):
        assert kb_titles.clean(raw) == want
