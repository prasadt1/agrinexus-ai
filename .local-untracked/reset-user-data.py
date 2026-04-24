#!/usr/bin/env python3
"""
Reset User Data Script
Deletes all data for a specific user from DynamoDB
"""
import boto3
import sys
import argparse
from typing import List, Dict, Any

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('agrinexus-data')


def get_user_items(phone_number: str) -> List[Dict[str, Any]]:
    """Get all items for a user"""
    items = []
    response = table.query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={
            ':pk': f'USER#{phone_number}'
        }
    )
    items.extend(response.get('Items', []))
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={
                ':pk': f'USER#{phone_number}'
            },
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response.get('Items', []))
    
    return items


def categorize_items(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize items by type"""
    categories = {
        'PROFILE': [],
        'MSG': [],
        'NUDGE': [],
        'OTHER': []
    }
    
    for item in items:
        sk = item.get('SK', '')
        if sk == 'PROFILE':
            categories['PROFILE'].append(item)
        elif sk.startswith('MSG#'):
            categories['MSG'].append(item)
        elif sk.startswith('NUDGE#'):
            categories['NUDGE'].append(item)
        else:
            categories['OTHER'].append(item)
    
    return categories


def delete_items(items: List[Dict[str, Any]], dry_run: bool = True) -> int:
    """Delete items from DynamoDB"""
    deleted = 0
    
    for item in items:
        pk = item['PK']
        sk = item['SK']
        
        if dry_run:
            print(f"  [DRY RUN] Would delete: {pk} | {sk}")
        else:
            try:
                table.delete_item(Key={'PK': pk, 'SK': sk})
                print(f"  ✓ Deleted: {pk} | {sk}")
                deleted += 1
            except Exception as e:
                print(f"  ✗ Error deleting {pk} | {sk}: {e}")
    
    return deleted


def reset_user_data(phone_number: str, keep_profile: bool = False, dry_run: bool = True):
    """Reset all data for a user"""
    print(f"\n{'='*60}")
    print(f"Reset User Data: {phone_number}")
    print(f"{'='*60}\n")
    
    # Get all items
    print("📊 Fetching user data...")
    items = get_user_items(phone_number)
    
    if not items:
        print(f"❌ No data found for user {phone_number}")
        return
    
    # Categorize items
    categories = categorize_items(items)
    
    # Show summary
    print(f"\n📋 Data Summary:")
    print(f"  Profile: {len(categories['PROFILE'])} item(s)")
    print(f"  Messages: {len(categories['MSG'])} item(s)")
    print(f"  Nudges: {len(categories['NUDGE'])} item(s)")
    print(f"  Other: {len(categories['OTHER'])} item(s)")
    print(f"  Total: {len(items)} item(s)")
    
    # Determine what to delete
    to_delete = []
    
    if keep_profile:
        print(f"\n⚠️  Keeping PROFILE (as requested)")
        to_delete.extend(categories['MSG'])
        to_delete.extend(categories['NUDGE'])
        to_delete.extend(categories['OTHER'])
    else:
        print(f"\n⚠️  Deleting ALL data including PROFILE")
        to_delete = items
    
    print(f"\n🗑️  Items to delete: {len(to_delete)}")
    
    if dry_run:
        print(f"\n{'='*60}")
        print("DRY RUN MODE - No actual deletions will occur")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print("⚠️  LIVE MODE - Deletions will be permanent!")
        print(f"{'='*60}\n")
        
        # Confirm
        confirm = input(f"Type 'DELETE {phone_number}' to confirm: ")
        if confirm != f"DELETE {phone_number}":
            print("❌ Confirmation failed. Aborting.")
            return
    
    # Delete items
    print(f"\n🗑️  Deleting items...")
    deleted = delete_items(to_delete, dry_run=dry_run)
    
    # Summary
    print(f"\n{'='*60}")
    if dry_run:
        print(f"✅ DRY RUN Complete")
        print(f"   Would delete: {len(to_delete)} item(s)")
    else:
        print(f"✅ Reset Complete")
        print(f"   Deleted: {deleted} item(s)")
        if keep_profile:
            print(f"   Profile: Kept")
        else:
            print(f"   Profile: Deleted")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Reset user data in DynamoDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (safe, shows what would be deleted)
  python3 scripts/reset-user-data.py 4917647009148
  
  # Delete all data including profile
  python3 scripts/reset-user-data.py 4917647009148 --execute
  
  # Delete messages/nudges but keep profile
  python3 scripts/reset-user-data.py 4917647009148 --execute --keep-profile
        """
    )
    
    parser.add_argument(
        'phone_number',
        help='Phone number to reset (e.g., 4917647009148)'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually delete data (default is dry run)'
    )
    
    parser.add_argument(
        '--keep-profile',
        action='store_true',
        help='Keep user profile, only delete messages and nudges'
    )
    
    parser.add_argument(
        '--table',
        default='agrinexus-data',
        help='DynamoDB table name (default: agrinexus-data)'
    )
    
    args = parser.parse_args()
    
    # Update table name if specified
    global table
    if args.table != 'agrinexus-data':
        table = dynamodb.Table(args.table)
    
    # Run reset
    reset_user_data(
        phone_number=args.phone_number,
        keep_profile=args.keep_profile,
        dry_run=not args.execute
    )


if __name__ == '__main__':
    main()
