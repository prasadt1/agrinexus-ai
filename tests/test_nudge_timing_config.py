"""Nudge send window is wired through the stack."""
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


def test_sender_receives_window():
    env = _template()["Resources"]["NudgeSender"]["Properties"]["Environment"]["Variables"]
    assert env["NUDGE_WINDOW_START_HOUR"] == {"Ref": "NudgeSendWindowStartHour"}
    assert env["NUDGE_WINDOW_END_HOUR"] == {"Ref": "NudgeSendWindowEndHour"}


def test_poll_schedule_stays_six_hourly():
    events = _template()["Resources"]["WeatherPoller"]["Properties"]["Events"]
    assert events["ScheduledPoll"]["Properties"]["Schedule"] == "rate(6 hours)"
