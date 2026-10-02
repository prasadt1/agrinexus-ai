"""Every Lambda, the shared layer and CI use one supported Python runtime."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPRECATED = {"python3.8", "python3.9", "python3.10", "python3.11"}


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
    return yaml.load((ROOT / "template.yaml").read_text(), Loader=_CfnLoader)


def _global_runtime():
    return _template()["Globals"]["Function"]["Runtime"]


def test_global_runtime_is_supported():
    assert _global_runtime() not in DEPRECATED


def test_no_function_overrides_runtime():
    for name, res in _template()["Resources"].items():
        if res["Type"] in ("AWS::Serverless::Function", "AWS::Lambda::Function"):
            assert res["Properties"].get("Runtime", _global_runtime()) == _global_runtime(), name


def test_layer_matches_function_runtime():
    layer = _template()["Resources"]["CommonLayer"]["Properties"]
    assert layer["CompatibleRuntimes"] == [_global_runtime()]


def test_ci_tests_on_the_lambda_python():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    versions = [
        step["with"]["python-version"]
        for job in wf["jobs"].values()
        for step in job["steps"]
        if "setup-python" in step.get("uses", "")
    ]
    assert versions == [_global_runtime().removeprefix("python")]
