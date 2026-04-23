#!/bin/bash
# Delete all data for a specific user from DynamoDB
# Usage: ./scripts/delete-user-data.sh [--yes] <phone_digits>
#   Example: ./scripts/delete-user-data.sh --yes 1555123456789
#   --yes   Skip confirmation (for scripts; or set DELETE_CONFIRM=yes)

set -e

AUTO_CONFIRM="${DELETE_CONFIRM:-}"
if [[ "${1:-}" == "--yes" ]]; then
  AUTO_CONFIRM=yes
  shift
fi
PHONE_NUMBER="${1:-}"
if [[ -z "$PHONE_NUMBER" ]]; then
  echo "Usage: $0 [--yes] <phone_digits>" >&2
  echo "Example: $0 --yes 1555123456789   # E.164 digits without +" >&2
  exit 1
fi

TABLE_NAME="${TABLE_NAME:-agrinexus-data}"

echo "🗑️  Deleting all data for user: $PHONE_NUMBER"
echo "Table: $TABLE_NAME"
echo ""

# Get all items for this user
echo "📋 Fetching all items..."
ITEMS=$(aws dynamodb query \
    --table-name "$TABLE_NAME" \
    --key-condition-expression "PK = :pk" \
    --expression-attribute-values "{\":pk\":{\"S\":\"USER#$PHONE_NUMBER\"}}" \
    --projection-expression "PK,SK" \
    --output json)

COUNT=$(echo "$ITEMS" | jq '.Items | length')
echo "Found $COUNT items to delete"
echo ""

if [ "$COUNT" -eq 0 ]; then
    echo "✅ No data found for this user"
    exit 0
fi

# Confirm deletion
echo "⚠️  This will permanently delete:"
echo "   - Profile (PROFILE)"
echo "   - All messages (MSG#*)"
echo "   - All nudges (NUDGE#*)"
echo "   - All schedules (SCHEDULE#*)"
echo "   - All rate limit records (RATE_LIMIT#*)"
echo ""
if [[ "$AUTO_CONFIRM" != "yes" ]]; then
  read -p "Are you sure? (yes/no): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "❌ Deletion cancelled"
    exit 1
  fi
fi

echo ""
echo "🗑️  Deleting items..."

# Delete each item
DELETED=0
echo "$ITEMS" | jq -c '.Items[]' | while read -r item; do
    PK=$(echo "$item" | jq -r '.PK.S')
    SK=$(echo "$item" | jq -r '.SK.S')
    
    aws dynamodb delete-item \
        --table-name "$TABLE_NAME" \
        --key "{\"PK\":{\"S\":\"$PK\"},\"SK\":{\"S\":\"$SK\"}}" \
        > /dev/null
    
    DELETED=$((DELETED + 1))
    echo "   Deleted: $SK"
done

echo ""
echo "✅ Successfully deleted $COUNT items for user $PHONE_NUMBER"
echo ""
echo "🔄 To start fresh, send a new WhatsApp message to re-onboard"
