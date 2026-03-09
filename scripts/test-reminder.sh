#!/bin/bash
# Manually trigger reminder for testing (bypasses 24h wait)

set -e

PHONE_NUMBER="${1:-4917647009148}"
REMINDER_TYPE="${2:-T+24h}"  # T+24h or T+48h

echo "Testing reminder system for phone: $PHONE_NUMBER"
echo "Reminder type: $REMINDER_TYPE"
echo ""

# Get the latest nudge for this user
echo "1. Finding latest nudge..."
NUDGE=$(aws dynamodb query \
  --table-name agrinexus-data \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{":pk":{"S":"USER#'${PHONE_NUMBER}'"},":sk":{"S":"NUDGE#"}}' \
  --no-scan-index-forward \
  --limit 1 \
  --output json)

NUDGE_ID=$(echo $NUDGE | jq -r '.Items[0].SK.S' | sed 's/NUDGE#//')
STATUS=$(echo $NUDGE | jq -r '.Items[0].status.S')
ACTIVITY=$(echo $NUDGE | jq -r '.Items[0].activity.S')

if [ "$NUDGE_ID" == "null" ] || [ -z "$NUDGE_ID" ]; then
  echo "❌ No nudge found for this user"
  exit 1
fi

echo "   Nudge ID: $NUDGE_ID"
echo "   Status: $STATUS"
echo "   Activity: $ACTIVITY"
echo ""

if [ "$STATUS" == "DONE" ]; then
  echo "⚠️  Nudge already marked as DONE. Reminders won't be sent."
  echo "   Run: ./scripts/trigger-nudge-test.sh $PHONE_NUMBER"
  echo "   to create a new nudge."
  exit 0
fi

# Get user dialect
echo "2. Getting user dialect..."
PROFILE=$(aws dynamodb get-item \
  --table-name agrinexus-data \
  --key "{\"PK\":{\"S\":\"USER#${PHONE_NUMBER}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
  --output json)

DIALECT=$(echo $PROFILE | jq -r '.Item.dialect.S')
echo "   Dialect: $DIALECT"
echo ""

# Manually invoke reminder Lambda
echo "3. Triggering reminder Lambda..."
echo "   Phone: $PHONE_NUMBER"
echo "   Nudge ID: $NUDGE_ID"
echo "   Reminder Type: $REMINDER_TYPE"
echo "   Dialect: $DIALECT"
echo ""

aws lambda invoke \
  --function-name agrinexus-reminder-dev \
  --cli-binary-format raw-in-base64-out \
  --payload "{\"phone_number\":\"$PHONE_NUMBER\",\"nudge_id\":\"$NUDGE_ID\",\"reminder_type\":\"$REMINDER_TYPE\",\"dialect\":\"$DIALECT\"}" \
  /tmp/reminder-response.json > /dev/null

RESPONSE=$(cat /tmp/reminder-response.json)
echo "   Response: $RESPONSE"
echo ""

# Check if reminder was sent
if echo $RESPONSE | grep -q "Reminder sent"; then
  echo "✅ Reminder sent successfully!"
  echo ""
  echo "Check your WhatsApp for the reminder message!"
  echo ""
  echo "Expected message ($REMINDER_TYPE):"
  if [ "$REMINDER_TYPE" == "T+24h" ]; then
    case $DIALECT in
      hi) echo "याद दिलाना: कल हमने स्प्रे करने के लिए कहा था। क्या आपने कर लिया? \"हो गया\" या \"अभी नहीं\" भेजें।" ;;
      mr) echo "आठवण: काल आम्ही फवारणी करण्यास सांगितले होते। तुम्ही केले का? \"झाला\" किंवा \"नाही झाला\" पाठवा." ;;
      te) echo "గుర్తు: నిన్న మేము స్ప్రే చేయమని చెప్పాము. మీరు చేశారా? \"అయ్యింది\" లేదా \"ఇంకా లేదు\" పంపండి." ;;
      *) echo "Reminder: Yesterday we asked you to spray. Have you done it? Send \"DONE\" or \"NOT YET\"." ;;
    esac
  else
    case $DIALECT in
      hi) echo "अंतिम याद दिलाना: स्प्रे करना बाकी है। कृपया जल्द करें और \"हो गया\" भेजें।" ;;
      mr) echo "शेवटची आठवण: फवारणी बाकी आहे. कृपया लवकर करा आणि \"झाला\" पाठवा." ;;
      te) echo "చివరి గుర్తు: స్ప్రే చేయడం మిగిలి ఉంది. దయచేసి త్వరగా చేయండి మరియు \"అయ్యింది\" పంపండి." ;;
      *) echo "Final reminder: Spraying is still pending. Please do it soon and send \"DONE\"." ;;
    esac
  fi
  echo ""
  echo "Nudge status updated to: REMINDED"
elif echo $RESPONSE | grep -q "already completed"; then
  echo "ℹ️  Task already completed - no reminder sent"
else
  echo "⚠️  Unexpected response"
fi
