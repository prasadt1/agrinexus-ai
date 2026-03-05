#!/bin/bash
set -euo pipefail

# Trigger a test nudge for a specific user
# This creates a nudge directly in DynamoDB and triggers the state machine

if [[ -f "$(dirname "$0")/demo.env" ]]; then
  source "$(dirname "$0")/demo.env"
fi

PHONE="${PHONE_NUMBER:-}"
ACTIVITY="${1:-spray}"
TABLE_NAME="${TABLE_NAME:-agrinexus-data}"
REGION="${AWS_REGION:-us-east-1}"
STATE_MACHINE_ARN="${STATE_MACHINE_ARN:-}"

function usage() {
  echo "Usage: $0 [spray|fertilizer|irrigation]"
  echo "Example: $0 spray"
  echo ""
  echo "Creates a test nudge for phone number in demo.env"
  exit 1
}

if [[ -z "$PHONE" ]]; then
  echo "Error: PHONE_NUMBER not set in demo.env"
  exit 1
fi

# Remove + from phone number for DynamoDB
PHONE_CLEAN="${PHONE//+/}"

# Get user profile to check dialect
PROFILE=$(aws dynamodb get-item \
  --table-name "$TABLE_NAME" \
  --key "{\"PK\":{\"S\":\"USER#${PHONE_CLEAN}\"},\"SK\":{\"S\":\"PROFILE\"}}" \
  --region "$REGION" 2>&1)

if ! echo "$PROFILE" | grep -q "Item"; then
  echo "Error: No profile found for ${PHONE}. Complete onboarding first."
  exit 1
fi

DIALECT=$(echo "$PROFILE" | grep -o '"dialect"[^}]*' | grep -o '"S":"[^"]*"' | cut -d'"' -f4)
LOCATION=$(echo "$PROFILE" | grep -o '"location"[^}]*' | grep -o '"S":"[^"]*"' | cut -d'"' -f4)

echo "Creating test nudge for:"
echo "  Phone: ${PHONE}"
echo "  Dialect: ${DIALECT}"
echo "  Location: ${LOCATION}"
echo "  Activity: ${ACTIVITY}"
echo ""

# Create nudge directly in DynamoDB
NUDGE_ID="TEST-$(date +%s)"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 - <<PY
import boto3
import json
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='${REGION}')
table = dynamodb.Table('${TABLE_NAME}')
sfn = boto3.client('stepfunctions', region_name='${REGION}')

phone = '${PHONE_CLEAN}'
activity = '${ACTIVITY}'
dialect = '${DIALECT}'
location = '${LOCATION}'
nudge_id = '${NUDGE_ID}'

# Activity messages by dialect
messages = {
    'spray': {
        'hi': 'मौसम कीट नियंत्रण के लिए अनुकूल है। आज स्प्रे करने की सलाह दी जाती है।',
        'mr': 'हवामान किडे नियंत्रणासाठी अनुकूल आहे। आज फवारणी करण्याचा सल्ला दिला जातो।',
        'te': 'వాతావరణం పురుగుల నియంత్రణకు అనుకూలంగా ఉంది। ఈరోజు స్ప్రే చేయాలని సూచించబడింది।',
        'en': 'Weather is favorable for pest control. Spraying is recommended today.'
    },
    'fertilizer': {
        'hi': 'मिट्टी की नमी खाद डालने के लिए अच्छी है। आज खाद डालें।',
        'mr': 'मातीची ओलावा खत घालण्यासाठी चांगली आहे. आज खत घाला.',
        'te': 'నేల తేమ ఎరువుల కోసం మంచిది. ఈరోజు ఎరువులు వేయండి.',
        'en': 'Soil moisture is good for fertilizer application. Apply fertilizer today.'
    },
    'irrigation': {
        'hi': 'फसल को पानी की जरूरत है। आज सिंचाई करें।',
        'mr': 'पिकाला पाण्याची गरज आहे. आज सिंचन करा.',
        'te': 'పంటకు నీరు అవసరం. ఈరోజు నీటిపారుదల చేయండి.',
        'en': 'Crop needs water. Irrigate today.'
    }
}

message = messages.get(activity, messages['spray']).get(dialect, messages['spray']['en'])

# Create nudge in DynamoDB
table.put_item(
    Item={
        'PK': f'USER#{phone}',
        'SK': f'NUDGE#{nudge_id}',
        'nudge_id': nudge_id,
        'activity': activity,
        'message': message,
        'status': 'SENT',
        'created_at': datetime.utcnow().isoformat(),
        'GSI2PK': 'NUDGE',
        'GSI2SK': f'{phone}#{datetime.utcnow().isoformat()}'
    }
)

print(f'✓ Created nudge in DynamoDB: {nudge_id}')

# Trigger state machine
state_machine_arn = 'arn:aws:states:${REGION}:043624892076:stateMachine:agrinexus-nudge-workflow-dev'

execution_input = {
    'phone_number': phone,
    'nudge_id': nudge_id,
    'activity': activity,
    'message': message,
    'dialect': dialect
}

try:
    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=f'test-{nudge_id}',
        input=json.dumps(execution_input)
    )
    print(f'✓ Started state machine execution')
    print(f'  Execution ARN: {response["executionArn"]}')
except Exception as e:
    print(f'⚠️  State machine trigger failed: {e}')
    print(f'  (Nudge created in DynamoDB, will be picked up by reminder scheduler)')

PY

echo ""
echo "✓ Test nudge created!"
echo ""
echo "Check your WhatsApp for the nudge message."
echo "Reply with 'हो गया' (done) or 'अभी नहीं' (not yet) to test response handling."
