# Quick Trigger Commands

**Date:** April 17, 2026

---

## Primary tester (this repo / video)

| | |
|--|--|
| **WhatsApp** | `+4917647009148` (what you type in the app) |
| **DynamoDB / Lambdas / scripts** | Digits only: **`4917647009148`** → partition key **`USER#4917647009148`** |
| **Onboarding story** | **Ramesh** · district **Latur** · crop **Wheat** (गेहूं) |
| **`demo_tier` in PROFILE** | After normal WhatsApp onboarding, the app sets **`public`** — this is a **product flag** (one contextual nudge by default, **no** automatic T+24h/T+48h EventBridge schedules). It does **not** mean “random public visitor”; it is still **your** number with **Ramesh / Latur / Wheat**. For the **closed-loop** steps in this file, set **`demo_tier` to `full`** via `./scripts/demo-video-nudge-triggers.sh profile` or the `update-item` below. |

Replace **`4917647009148`** everywhere if you switch handsets.

---

## Video / demo order (ignore Kiro; run this)

Use **your** WhatsApp number in E.164 **without** `+` (e.g. `4915120105731`). Default here matches the primary tester line above.

1. **Prerequisites** — run the DynamoDB `update-item` so profile is **Latur**, **Wheat**, **`demo_tier = full`** (needed for T+24h schedules; for manual T+24h invoke, `full` still matches real nudge records).
2. **TRIGGER 1** — `agrinexus-nudge-sender-dev` payload (first nudge). In WhatsApp tap **अभी नहीं** if you want the scripted deferral.
3. **Record middle** — text RAG, voice, vision (same chat; no second nudge yet).
4. **TRIGGER 2** — Query **`NUDGE_ID`** from Dynamo (section below), then invoke **`agrinexus-reminder-dev`** with `reminder_type: T+24h`. Do this **after** vision when you are ready for the “24h reminder” beat.
5. **Optional TRIGGER 3** — T+48h same pattern, different `reminder_type`.

Do **not** rely on Kiro to “script” this; copy the `aws lambda invoke` blocks from this file. If `NUDGE_ID` is empty, TRIGGER 1 did not create a row (allowlist / location / skip path) — check CloudWatch for `nudge-sender` and profile **GSI1** `LOCATION#Latur`.

**Automated (no copy-paste between steps):** from repo root, laptop beside you while recording on phone:

```bash
chmod +x scripts/demo-video-nudge-triggers.sh # once
./scripts/demo-video-nudge-triggers.sh profile   # optional: Latur + Wheat + full
./scripts/demo-video-nudge-triggers.sh guided    # first nudge → Enter → T+24h → Enter → T+48h
```

Or stepwise: `first` → (record) → `24` → (record) → `48`. Default phone is **4917647009148**; override with `PHONE=...`.

---

## Prerequisites

Before triggering nudges, ensure profile exists:

```bash
# Update profile with Latur + Wheat + full demo tier
aws dynamodb update-item \
  --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#4917647009148"},"SK":{"S":"PROFILE"}}' \
  --update-expression "SET district = :dist, crop = :crop, demo_tier = :tier, #loc = :loc" \
  --expression-attribute-names '{"#loc":"location"}' \
  --expression-attribute-values '{":dist":{"S":"Latur"},":crop":{"S":"Wheat"},":tier":{"S":"full"},":loc":{"S":"Latur"}}' \
  --region us-east-1
```

---

## TRIGGER 1: First Nudge (Latur, Wheat)

```bash
aws lambda invoke \
  --function-name agrinexus-nudge-sender-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"location":"Latur","activity":"spray","weather":{"temp":28,"humidity":65,"wind_speed":8,"conditions":"clear"}}' \
  --region us-east-1 \
  /tmp/nudge-response.json && cat /tmp/nudge-response.json | jq .
```

**Expected Output:**
```json
{
  "statusCode": 200,
  "nudges_sent": 1,
  "nudges_skipped": 0,
  "location": "Latur"
}
```

**Expected in WhatsApp (~10 seconds):**
```
Latur: गेहूं में स्प्रे के लिए मौसम अनुकूल है। हवा 8.0 km/h है। कृपया स्प्रे करें।

Buttons: [Done ✅] [Not Yet ⏸️]
```

**Action:** Click `Not Yet ⏸️`

---

## TRIGGER 2: T+24h Reminder

First, get the nudge ID:

```bash
NUDGE_ID=$(aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#4917647009148"},":sk":{"S":"NUDGE#"}}' \
  --region us-east-1 \
  --query 'Items[0].SK.S' \
  --output text | sed 's/NUDGE#//')

echo "Nudge ID: $NUDGE_ID"
```

Then trigger the reminder:

```bash
aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --cli-binary-format raw-in-base64-out \
  --payload "{\"phone_number\":\"4917647009148\",\"nudge_id\":\"$NUDGE_ID\",\"reminder_type\":\"T+24h\",\"dialect\":\"hi\",\"district\":\"Latur\",\"crop\":\"Wheat\"}" \
  --region us-east-1 \
  /tmp/reminder-response.json && cat /tmp/reminder-response.json | jq .
```

**Expected Output:**
```json
{
  "statusCode": 200,
  "message": "Reminder sent successfully"
}
```

**Expected in WhatsApp (~5 seconds):**
```
Latur: गेहूं में अभी तक स्प्रे नहीं किया? मौसम अनुकूल है। कृपया आज स्प्रे करें।

Buttons: [Done ✅] [Not Yet ⏸️]
```

**Action:** Click `Done ✅`

---

## TRIGGER 3: T+48h Reminder (Optional)

```bash
aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --cli-binary-format raw-in-base64-out \
  --payload "{\"phone_number\":\"4917647009148\",\"nudge_id\":\"$NUDGE_ID\",\"reminder_type\":\"T+48h\",\"dialect\":\"hi\",\"district\":\"Latur\",\"crop\":\"Wheat\"}" \
  --region us-east-1 \
  /tmp/reminder-response.json && cat /tmp/reminder-response.json | jq .
```

**Expected in WhatsApp:**
```
Latur: गेहूं में स्प्रे करने की अंतिम याद दिलाना। कृपया जल्द करें।

Buttons: [Done ✅] [Not Yet ⏸️]
```

---

## Verification Commands

### Check Profile
```bash
aws dynamodb get-item \
  --table-name agrinexus-data \
  --key '{"PK":{"S":"USER#4917647009148"},"SK":{"S":"PROFILE"}}' \
  --region us-east-1 \
  --query 'Item.{district:district.S,crop:crop.S,demo_tier:demo_tier.S,location:location.S}'
```

### Check Nudge Status
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#4917647009148"},":sk":{"S":"NUDGE#"}}' \
  --region us-east-1 \
  --query 'Items[*].{nudge_id:SK.S,status:status.S,activity:activity.S,district:district.S,crop:crop.S}'
```

### Check All User Data
```bash
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"USER#4917647009148"}}' \
  --region us-east-1 \
  --query 'Items[*].{PK:PK.S,SK:SK.S}'
```

### Reset All Data
```bash
# Get all items
aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk":{"S":"USER#4917647009148"}}' \
  --region us-east-1 \
  --output json | jq -r '.Items[] | "\(.PK.S) \(.SK.S)"' > /tmp/delete_items.txt

# Delete all items
while IFS=' ' read -r pk sk; do
  aws dynamodb delete-item \
    --table-name agrinexus-data \
    --key "{\"PK\":{\"S\":\"$pk\"},\"SK\":{\"S\":\"$sk\"}}" \
    --region us-east-1
  echo "Deleted: $pk $sk"
done < /tmp/delete_items.txt
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `trigger 1` | First nudge (Latur, Wheat, 8 km/h wind) |
| `trigger 2` | T+24h reminder (includes crop name) |
| `trigger 3` | T+48h final reminder (includes crop name) |

---

**Ready?** Just say "1" or "trigger 1" to send the first nudge! 🚀
