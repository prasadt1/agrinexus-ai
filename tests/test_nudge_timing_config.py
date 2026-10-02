"""Nudge send window, cooldown and the demo force path are wired through the stack and script."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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


def test_window_hours_are_stack_parameters():
    params = _template()["Parameters"]
    assert params["NudgeSendWindowStartHour"]["Default"] == 6
    assert params["NudgeSendWindowEndHour"]["Default"] == 19


def test_sender_receives_window_and_cooldown():
    env = _template()["Resources"]["NudgeSender"]["Properties"]["Environment"]["Variables"]
    assert env["NUDGE_WINDOW_START_HOUR"] == {"Ref": "NudgeSendWindowStartHour"}
    assert env["NUDGE_WINDOW_END_HOUR"] == {"Ref": "NudgeSendWindowEndHour"}
    assert env["NUDGE_COOLDOWN_DAYS"] == "7"


def test_poll_schedule_stays_six_hourly():
    events = _template()["Resources"]["WeatherPoller"]["Properties"]["Events"]
    assert events["ScheduledPoll"]["Properties"]["Schedule"] == "rate(6 hours)"


def test_state_machine_passes_full_input_to_sender():
    asl = json.loads((ROOT / "statemachine" / "nudge-workflow.asl.json").read_text())
    task = asl["States"]["SendNudgeToFarmers"]
    for key in ("Parameters", "InputPath", "Arguments"):
        assert key not in task, f"{key} would drop 'force' from the sender's input"


def test_demo_script_forces_the_poll():
    script = (ROOT / "scripts" / "test-complete-flow.sh").read_text()
    invoke = re.search(r"aws lambda invoke --function-name \"\$WEATHER_LAMBDA\"[^\n]*", script).group(0)
    assert '"force": true' in invoke or '"force":true' in invoke
    assert "--cli-binary-format raw-in-base64-out" in invoke
