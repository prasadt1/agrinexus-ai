"""Queue and stream failure handling declared in template.yaml."""
import json
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


def test_a_failed_message_leaves_the_queues_within_the_visitor_promise():
    """A queued message holds the sender's number and text.

    The landing page promises visitors 7 days. On a FIFO queue the clock restarts when a
    message moves to its dead-letter queue, so the two retention periods add up.
    """
    r = _resources()
    promise = int(yaml.load(TEMPLATE.read_text(), Loader=_CfnLoader)["Parameters"]["VisitorTtlDays"]["Default"])
    assert promise == 7
    checked = 0
    for name, res in r.items():
        if res["Type"] != "AWS::SQS::Queue" or "RedrivePolicy" not in res["Properties"]:
            continue
        props = res["Properties"]
        dlq = r[props["RedrivePolicy"]["deadLetterTargetArn"]["GetAtt"].split(".")[0]]["Properties"]
        assert props["FifoQueue"] is True and dlq["FifoQueue"] is True, name
        total = props["MessageRetentionPeriod"] + dlq["MessageRetentionPeriod"]
        assert total <= promise * 24 * 3600, (name, total)
        checked += 1
    assert checked == 3  # messages, beta messages, voice


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


def test_every_per_user_media_prefix_expires():
    rules = _resources()["TempAudioBucket"]["Properties"]["LifecycleConfiguration"]["Rules"]
    expiring = {r["Prefix"] for r in rules if r["Status"] == "Enabled" and r.get("ExpirationInDays")}
    assert {"images/", "voice/", "voice-output/"} <= expiring


# Actions with no resource-level permissions (AWS service reference), or where a scoped
# resource was denied in a live session-policy probe (polly with no lexicon).
WILDCARD_ONLY = {"bedrock:RetrieveAndGenerate", "polly:SynthesizeSpeech",
                 "transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob", "transcribe:DeleteTranscriptionJob"}


def test_no_wildcard_resource_for_scopable_actions():
    for fn in ("WebChatHandler", "MessageProcessor", "BetaMessageProcessor", "NudgeSender", "ResponseDetector"):
        for s in _statements(fn):
            if s["Resource"] in ("*", ["*"]):
                assert set(s["Action"]) <= WILDCARD_ONLY, (fn, s["Action"])


def test_bedrock_resources_are_the_model_kb_and_guardrail():
    for fn in ("WebChatHandler", "MessageProcessor", "BetaMessageProcessor"):
        stmts = _statements(fn)
        by_action = {a: s for s in stmts for a in s["Action"]}
        assert "bedrock:ListInferenceProfiles" not in by_action
        assert not any(a.startswith("bedrock-agent:") for a in by_action)
        assert "knowledge-base/${KnowledgeBaseId}" in json.dumps(by_action["bedrock:Retrieve"]["Resource"])
        assert "guardrail/${Gid}" in json.dumps(by_action["bedrock:ApplyGuardrail"]["Resource"])
        invoke = json.dumps(by_action["bedrock:InvokeModel"]["Resource"])
        assert "inference-profile/${BedrockModelId}" in invoke and "foundation-model/${Provider}.${Model}" in invoke


def test_scheduler_actions_limited_to_nudge_schedules():
    for fn in ("NudgeSender", "ResponseDetector", "ReminderSender"):
        for s in _statements(fn):
            if any(a.startswith("scheduler:") for a in s["Action"]):
                res = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
                assert sorted(r["Sub"].rsplit("/", 1)[-1] for r in res) == ["expiry-*", "reminder-*"], fn
