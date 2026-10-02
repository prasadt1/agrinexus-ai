"""Queue and stream failure handling declared in template.yaml."""
from pathlib import Path

import yaml

TEMPLATE = Path(__file__).resolve().parents[1] / "template.yaml"


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


def _resources():
    return yaml.load(TEMPLATE.read_text(), Loader=_CfnLoader)["Resources"]


def test_voice_queue_has_dlq_with_same_receive_count():
    r = _resources()
    expected = r["MessageQueue"]["Properties"]["RedrivePolicy"]["maxReceiveCount"]
    redrive = r["VoiceQueue"]["Properties"]["RedrivePolicy"]
    assert redrive["maxReceiveCount"] == expected
    dlq_name = redrive["deadLetterTargetArn"]["GetAtt"].split(".")[0]
    dlq = r[dlq_name]["Properties"]
    assert dlq["FifoQueue"] is True
    assert dlq["MessageRetentionPeriod"] == 1209600


def test_voice_dlq_is_drained_by_dlq_handler():
    r = _resources()
    dlq_name = r["VoiceQueue"]["Properties"]["RedrivePolicy"]["deadLetterTargetArn"]["GetAtt"].split(".")[0]
    events = r["DLQHandler"]["Properties"]["Events"].values()
    queues = [e["Properties"]["Queue"]["GetAtt"] for e in events if e["Type"] == "SQS"]
    assert f"{dlq_name}.Arn" in queues


def test_response_detector_stream_has_bounded_retries_and_failure_destination():
    r = _resources()
    esm = r["ResponseDetectorEventSourceMapping"]["Properties"]
    assert 0 <= esm["MaximumRetryAttempts"] <= 3
    assert esm["BisectBatchOnFunctionError"] is True
    assert "ReportBatchItemFailures" in esm["FunctionResponseTypes"]
    dest = esm["DestinationConfig"]["OnFailure"]["Destination"]["GetAtt"].split(".")[0]
    assert r[dest]["Type"] == "AWS::SQS::Queue"
    policies = r["ResponseDetector"]["Properties"]["Policies"]
    assert any(
        isinstance(p, dict) and "SQSSendMessagePolicy" in p
        and p["SQSSendMessagePolicy"]["QueueName"] == {"GetAtt": f"{dest}.QueueName"}
        for p in policies
    )


def _statements(fn):
    out = []
    for p in _resources()[fn]["Properties"]["Policies"]:
        if isinstance(p, dict) and "Statement" in p:
            out += p["Statement"]
    return out


def test_reminder_can_delete_only_nudge_schedules():
    stmts = [s for s in _statements("ReminderSender") if "scheduler:DeleteSchedule" in s["Action"]]
    assert stmts
    for s in stmts:
        resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
        assert resources and all(isinstance(r, dict) and "Sub" in r for r in resources)
        assert sorted(r["Sub"].rsplit("/", 1)[-1] for r in resources) == ["expiry-*", "reminder-*"]
