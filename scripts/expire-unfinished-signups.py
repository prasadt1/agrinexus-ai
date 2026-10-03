#!/usr/bin/env python3
"""Give old unfinished farmer sign-ups the expiry that new ones get.

Until 3 October 2026 a profile whose sign-up was started and never finished had no expiry
and stayed in the table for good. New ones expire after VisitorTtlDays (7). This sets the
same expiry, counted from now, on the old ones. Finished profiles and visitor profiles
are not touched.

Dry run by default; pass --apply to set the expiry.

    python3 scripts/expire-unfinished-signups.py
    python3 scripts/expire-unfinished-signups.py --apply
"""
import argparse
import time

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError


def find_unfinished(table) -> list:
    """Keys of PROFILE rows with onboarding_complete false and no ttl."""
    kwargs = {
        "FilterExpression": (
            Attr("SK").eq("PROFILE") & Attr("onboarding_complete").eq(False) & Attr("ttl").not_exists()
        ),
        "ProjectionExpression": "PK, SK",
    }
    keys = []
    while True:
        page = table.scan(**kwargs)
        keys += [{"PK": item["PK"], "SK": item["SK"]} for item in page.get("Items", [])]
        if "LastEvaluatedKey" not in page:
            return keys
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def set_expiry(table, key: dict, expires_at: int) -> bool:
    """Set ttl unless the sign-up was finished, or got an expiry, since the scan."""
    try:
        table.update_item(
            Key=key,
            UpdateExpression="SET #ttl = :ttl",
            ConditionExpression="attribute_not_exists(#ttl) AND onboarding_complete = :unfinished",
            ExpressionAttributeNames={"#ttl": "ttl"},
            ExpressionAttributeValues={":ttl": expires_at, ":unfinished": False},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def masked(pk: str) -> str:
    """USER#4915112345678 -> USER#491***"""
    prefix, _, number = pk.partition("#")
    return f"{prefix}#{number[:3]}***"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="set the expiry (default: only list)")
    ap.add_argument("--table", default="agrinexus-data")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--days", type=int, default=7, help="days from now until the row expires")
    args = ap.parse_args()

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    keys = find_unfinished(table)
    expires_at = int(time.time()) + args.days * 24 * 60 * 60
    print(f"{len(keys)} unfinished sign-up(s) without an expiry")
    for key in keys:
        if not args.apply:
            print(f"would expire {masked(key['PK'])}")
        elif set_expiry(table, key, expires_at):
            print(f"expires in {args.days} days: {masked(key['PK'])}")
        else:
            print(f"left alone (finished or already expiring): {masked(key['PK'])}")


if __name__ == "__main__":
    main()
