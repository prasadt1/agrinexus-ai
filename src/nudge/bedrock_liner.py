"""
Optional Bedrock one-liner for nudge context hints (scouting + KVK/dealer, no products/doses).
"""

import json
import os
from typing import Optional

import boto3

LANGUAGE_NAMES = {
    "hi": "Hindi (Devanagari script only).",
    "mr": "Marathi (Devanagari script only).",
    "te": "Telugu script only.",
    "en": "English.",
}


def invoke_nudge_focus_line(
    dialect: str,
    crop: str,
    district: str,
    wind_speed: float,
) -> Optional[str]:
    if os.environ.get("NUDGE_BEDROCK_LINER", "").lower() not in ("1", "true", "yes"):
        return None
    model_id = os.environ.get(
        "NUDGE_LINER_MODEL_ID",
        "anthropic.claude-3-haiku-20240307-v1:0",
    )
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    client = boto3.client("bedrock-runtime", region_name=region)
    lang = LANGUAGE_NAMES.get(dialect, LANGUAGE_NAMES["en"])
    system = f"""You write exactly ONE short sentence for Indian smallholder farmers (extension style).
Rules:
- Language: {lang}
- Mention only field scouting or monitoring (pests, disease signs, crop stage) — no product names, no chemical names, no doses, no brands.
- You may suggest consulting a local KVK or licensed dealer for choices.
- One sentence only. No bullet points. No emojis."""

    user_msg = (
        f"District: {district}. Main crop: {crop}. "
        f"Wind speed now ~{wind_speed:.1f} km/h (suitable spray window). "
        f"Give one seasonal scouting line for this week."
    )
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 160,
            "temperature": 0.35,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
    )
    resp = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    raw = resp["body"].read()
    data = json.loads(raw)
    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    line = " ".join(parts).strip().replace("\n", " ")
    if not line:
        return None
    if len(line) > 400:
        line = line[:397] + "..."
    return line
