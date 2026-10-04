#!/usr/bin/env python3
"""
Fixed text replay set: run the visitor sample questions and a few control questions
through the processor's knowledge-base path against real Bedrock, with the prompt and
filter in THIS checkout, and print what a farmer would receive.

Run it before deploying any change to the knowledge-base prompt or the advice filter.
Nothing is sent on WhatsApp and nothing is written to DynamoDB or S3; only Bedrock
RetrieveAndGenerate is called (one call per question per run).

The knowledge base, guardrail and model are read from the live processor function
(lambda:GetFunctionConfiguration), so the replay uses what the deployed stack uses.
Override any of them with KNOWLEDGE_BASE_ID, GUARDRAIL_ID, GUARDRAIL_VERSION or
BEDROCK_MODEL_ID in the environment.

Usage:
  python3 scripts/text-replay.py
  python3 scripts/text-replay.py --runs 3
  python3 scripts/text-replay.py --question "How do I control whitefly on cotton?"
  python3 scripts/text-replay.py --out docs/try/replays/2026-10-04-text.json
  python3 scripts/text-replay.py --web
    Same questions through the web chat handler (its own prompt and filter), with rate
    limits and the daily counter stubbed so nothing is written to DynamoDB.

Checks per reply (heuristics; read the stored text):
  words        words in the model's answer (the prompt asks for under 100)
  opener       the model opened with "I cannot recommend ..." (wanted only for a pesticide question)
  markdown     the model wrote ** or # markup
  kvk_lines    lines naming the KVK, in any script, in the farmer's reply (wanted: 1, the footer)
  sources      document names from retrieval metadata (wanted: at least 1 for an answer)
  filter       kinds the advice filter matched in the model's answer
  marker       NO_KB_ANSWER / NOT_FARMING replaced by the fixed refusal
  guardrail    the Bedrock guardrail stepped in and the fixed refusal was sent
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
ENV_KEYS = ("KNOWLEDGE_BASE_ID", "GUARDRAIL_ID", "GUARDRAIL_VERSION", "BEDROCK_MODEL_ID")

# (dialect, question, what a good reply looks like)
CONTROLS = [
    ("en", "Which pesticide should I spray for whitefly on cotton, and how much?", "pesticide"),
    ("en", "Who won the cricket match yesterday?", "not_farming"),
    # a timing question must never get the pesticide-policy reply (visitors have no district,
    # so the knowledge base answers it; farmers in a known district get the weather reply)
    ("en", "Can I spray today?", "answer"),
    ("mr", "कापसावरील पांढरी माशी कशी नियंत्रित करावी?", "answer"),
    ("hi", "कपास में सफेद मक्खी का नियंत्रण कैसे करें?", "answer"),
]


def _setup_env(function_name: str, region: str) -> dict:
    import boto3

    os.environ.setdefault("AWS_REGION", region)
    os.environ.setdefault("AWS_DEFAULT_REGION", region)
    live = {}
    if not all(k in os.environ for k in ENV_KEYS[:3]):
        conf = boto3.client("lambda", region_name=region).get_function_configuration(FunctionName=function_name)
        live = (conf.get("Environment") or {}).get("Variables") or {}
    used = {}
    for key in ENV_KEYS:
        if key not in os.environ and key in live:
            os.environ[key] = live[key]
        used[key] = os.environ.get(key, "")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")
    os.environ.setdefault("TABLE_NAME", "replay")
    os.environ.setdefault("TEMP_AUDIO_BUCKET", "replay-bucket")
    if "ACCOUNT_ID" not in os.environ:
        os.environ["ACCOUNT_ID"] = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    for p in (REPO / "src" / "processor", REPO / "src" / "common-layer" / "python"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return used


def farmer_reply(handler, question: str, dialect: str, result: dict) -> dict:
    """The same steps the processor's text path takes between Bedrock and the send."""
    from common import advice_filter
    from common.source_line import strip_source_lines

    text = result["text"]
    policy_reply = (
        advice_filter.is_pesticide_question(question)
        and handler.is_rag_refusal_response(text)
        and not result.get("kb_not_farming")
        and not result.get("guardrail_localized")
    )
    if policy_reply:
        text = advice_filter.pesticide_policy(dialect)
    text = strip_source_lines(handler.strip_llm_xml_citation_tags(text))
    from common.source_labels import source_line

    labels = []
    if not policy_reply and not handler.is_rag_refusal_response(text):
        labels = handler.source_labels_from_citations(result.get("citations"))
    reply = advice_filter.filter_advice(
        text, dialect, "whatsapp_text", kind="answer",
        add_referral=not handler.is_rag_refusal_response(text),
        question=question,
        source_line=source_line(labels, dialect),
    )
    return {"reply_text": reply, "source_labels": labels, "policy_reply": policy_reply}


class _AllowAllTable:
    """Stands in for DynamoDB in the web replay: every limit passes, nothing is written."""

    def get_item(self, **_k):
        return {}

    def put_item(self, **_k):
        return {}

    def update_item(self, **_k):
        return {"Attributes": {"count": 1}}


def load_web_handler():
    """The web chat handler from this checkout, with DynamoDB and CloudWatch stubbed."""
    import importlib.util

    web_dir = REPO / "src" / "web-chat"
    spec = importlib.util.spec_from_file_location("webchat_replay_handler", web_dir / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.table = _AllowAllTable()
    mod.cloudwatch = MagicMock()
    return mod


def web_reply(web, question: str, dialect: str, captured: dict) -> dict:
    """Run the web lambda_handler; query_bedrock is wrapped so the raw model result is kept."""
    event = {
        "httpMethod": "POST",
        "headers": {"Content-Type": "application/json"},
        "requestContext": {"identity": {"sourceIp": "replay"}},
        "body": json.dumps({"message": question, "language": dialect, "client_id": "replay-client-0000"}),
    }
    resp = web.lambda_handler(event, None)
    body = json.loads(resp["body"])
    if resp["statusCode"] != 200:
        raise RuntimeError(f"web handler returned {resp['statusCode']}: {body}")
    return {"reply_text": body["reply"], "source_labels": body.get("citations", []),
            "policy_reply": captured.get("policy", False)}


def checks(model_text: str, reply: dict, result: dict) -> dict:
    from common import advice_filter

    kinds = sorted({k for line in model_text.split("\n") for seg in advice_filter._segments(line) for k in advice_filter.classify(seg)})
    return {
        "words": len(model_text.split()),
        "opener": bool(advice_filter._REFUSAL_OPENER_RE.match(model_text)),
        "markdown": "**" in model_text or bool(re.search(r"^#{1,6}\s", model_text, re.M)),
        "kvk_lines": sum(1 for line in reply["reply_text"].split("\n") if advice_filter.names_kvk(line)),
        "sources": reply["source_labels"],
        "citations": len(result.get("citations") or []),
        "filter": kinds,
        "marker": bool(result.get("kb_no_answer") or result.get("kb_not_farming")),
        "guardrail": bool(result.get("guardrail_localized")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=1, help="calls per question (default 1)")
    ap.add_argument("--question", help="replay only this question (English unless --dialect)")
    ap.add_argument("--dialect", default="en", choices=("en", "hi", "mr", "te"))
    ap.add_argument("--function", default="agrinexus-processor-dev", help="live processor function to read settings from")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--out", default="/tmp/agrinexus-text-replay.json")
    ap.add_argument("--web", action="store_true", help="replay through the web chat handler instead of WhatsApp")
    args = ap.parse_args()

    used = _setup_env(args.function, args.region)
    import handler  # noqa: E402
    from common import advice_filter, visitor  # noqa: E402

    advice_filter._cloudwatch = MagicMock()
    web = None
    if args.web:
        web = load_web_handler()
        raw_query = web.query_bedrock
        captured: dict = {}

        def keep_result(q, d="en"):
            captured["result"] = raw_query(q, d)
            return captured["result"]

        web.query_bedrock = keep_result

    if args.question:
        questions = [(args.dialect, args.question, "answer")]
    else:
        questions = [("en", q, "answer") for _id, _title, q in visitor.SAMPLE_QUESTIONS] + CONTROLS

    print(f"channel {'web' if args.web else 'whatsapp'}  knowledge base {used['KNOWLEDGE_BASE_ID'] or '?'}  guardrail {'set' if used['GUARDRAIL_ID'] else 'none'}  "
          f"model {used['BEDROCK_MODEL_ID'] or 'handler default'}")
    results = []
    for dialect, question, expect in questions:
        for run in range(args.runs):
            started = time.time()
            try:
                if web is not None:
                    reply = web_reply(web, question, dialect, captured)
                    result = captured["result"]
                    reply["policy_reply"] = (
                        advice_filter.is_pesticide_question(question)
                        and web.is_rag_refusal_response(result["text"])
                    )
                else:
                    result = handler.query_bedrock(question, dialect)
                    reply = farmer_reply(handler, question, dialect, result)
            except Exception as e:  # keep going: one failed call should not hide the rest
                print(f"\n=== [{dialect}] {question}\nERROR {type(e).__name__}: {e}")
                results.append({"dialect": dialect, "question": question, "run": run, "error": f"{type(e).__name__}: {e}"})
                continue
            model_text = result["text"]
            c = checks(model_text, reply, result)
            print(f"\n=== [{dialect}] {question}   (expect: {expect}, {time.time() - started:.1f}s)")
            print(f"words={c['words']} opener={c['opener']} markdown={c['markdown']} kvk_lines={c['kvk_lines']} "
                  f"citations={c['citations']} sources={c['sources']} filter={c['filter']} marker={c['marker']} "
                  f"guardrail={c['guardrail']} policy={reply['policy_reply']}")
            print("--- farmer reply")
            print(reply["reply_text"])
            results.append({
                "dialect": dialect, "question": question, "expect": expect, "run": run,
                "model_text": model_text, "reply_text": reply["reply_text"], "checks": c,
                "policy_reply": reply["policy_reply"],
            })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"settings": {k: bool(v) if k == "GUARDRAIL_ID" else v for k, v in used.items()},
                               "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(results)} result(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
