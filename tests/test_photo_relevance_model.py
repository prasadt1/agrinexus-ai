"""The photo relevance check runs on a live model and treats crop pests as farm photos."""
import importlib
import io
import json
from pathlib import Path

import pytest
import yaml

from src.processor import analyzer

TEMPLATE = Path(__file__).resolve().parents[1] / "template.yaml"
PROCESSORS = ("MessageProcessor", "BetaMessageProcessor")
IMG = b"\xff\xd8\xff\xe0" + b"0" * 64


class _CfnLoader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {suffix: value}


_CfnLoader.add_multi_constructor("!", _tag)


def _template():
    return yaml.load(TEMPLATE.read_text(), Loader=_CfnLoader)


class _Bedrock:
    def __init__(self):
        self.calls = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        body = {"content": [{"type": "text", "text": '{"relevance":"agri_photo","reason":"other","confidence":"high"}'}]}
        return {"body": io.BytesIO(json.dumps(body).encode())}


@pytest.fixture
def reload_analyzer(monkeypatch):
    def _reload(model_id=None):
        if model_id is None:
            monkeypatch.delenv("VISION_RELEVANCE_MODEL_ID", raising=False)
        else:
            monkeypatch.setenv("VISION_RELEVANCE_MODEL_ID", model_id)
        return importlib.reload(analyzer)

    yield _reload
    monkeypatch.delenv("VISION_RELEVANCE_MODEL_ID", raising=False)
    importlib.reload(analyzer)


def test_default_model_is_not_end_of_life(reload_analyzer):
    mod = reload_analyzer()
    assert "claude-3-haiku" not in mod.RELEVANCE_MODEL_ID
    assert mod.RELEVANCE_MODEL_ID == "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_configured_model_is_used(reload_analyzer, monkeypatch):
    mod = reload_analyzer("us.anthropic.example-model-v1:0")
    fake = _Bedrock()
    monkeypatch.setattr(mod, "bedrock", fake)
    mod.classify_image_relevance(IMG, "en")
    assert fake.calls[0]["modelId"] == "us.anthropic.example-model-v1:0"


def _prompt_lines(monkeypatch):
    fake = _Bedrock()
    monkeypatch.setattr(analyzer, "bedrock", fake)
    analyzer.classify_image_relevance(IMG, "en")
    content = json.loads(fake.calls[0]["body"])["messages"][0]["content"]
    text = next(c["text"] for c in content if c["type"] == "text")
    return {line.split(":")[0].lstrip("- "): line for line in text.splitlines() if line.startswith("- ")}


def test_prompt_counts_crop_pests_as_farm_photos(monkeypatch):
    lines = _prompt_lines(monkeypatch)
    for word in ("insect", "larva", "caterpillar", "pest", "boll"):
        assert word in lines["agri_photo"]


def test_prompt_excludes_crop_pests_from_animals(monkeypatch):
    assert "not crop pests" in _prompt_lines(monkeypatch)["not_agri"]


def test_template_parameter_defaults_to_live_haiku():
    param = _template()["Parameters"]["RelevanceModelId"]
    assert param["Default"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"


@pytest.mark.parametrize("name", PROCESSORS)
def test_processors_receive_relevance_model(name):
    env = _template()["Resources"][name]["Properties"]["Environment"]["Variables"]
    assert env["VISION_RELEVANCE_MODEL_ID"] == {"Ref": "RelevanceModelId"}


def _invoke_resources(name):
    for stmt in _template()["Resources"][name]["Properties"]["Policies"]:
        if not isinstance(stmt, dict) or "Statement" not in stmt:
            continue
        for s in stmt["Statement"]:
            if "bedrock:InvokeModel" in s["Action"]:
                return s["Resource"]
    raise AssertionError(f"{name} has no InvokeModel statement")


@pytest.mark.parametrize("name", PROCESSORS)
def test_processors_may_invoke_relevance_profile_and_its_models(name):
    resources = json.dumps(_invoke_resources(name))
    assert "inference-profile/${RelevanceModelId}" in resources
    assert '"Ref": "RelevanceModelId"' in resources
    assert "claude-3-haiku" not in resources
