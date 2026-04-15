#!/usr/bin/env python3
import argparse
import os
from datetime import datetime, timezone

import boto3


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_phone(phone: str) -> str:
    # Expect WhatsApp "from" format: digits only, country code included (e.g., 4915...)
    return "".join(ch for ch in phone if ch.isdigit())


def key(phone: str) -> dict:
    return {"PK": "ALLOWLIST", "SK": f"USER#{phone}"}


def main() -> int:
    p = argparse.ArgumentParser(description="Manage AgriNexus WhatsApp allowlist in DynamoDB")
    p.add_argument("--table", default=os.environ.get("TABLE_NAME"), help="DynamoDB table name (or set TABLE_NAME)")
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Approve a phone number for full WhatsApp features")
    add.add_argument("phone", help="Phone number digits (WhatsApp from number)")

    rm = sub.add_parser("remove", help="Remove a phone number from allowlist")
    rm.add_argument("phone", help="Phone number digits (WhatsApp from number)")

    chk = sub.add_parser("check", help="Check allowlist status")
    chk.add_argument("phone", help="Phone number digits (WhatsApp from number)")

    args = p.parse_args()
    if not args.table:
        raise SystemExit("Missing table name. Pass --table or set TABLE_NAME.")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(args.table)
    phone = normalize_phone(args.phone)

    if args.cmd == "add":
        table.put_item(
            Item={
                **key(phone),
                "approved": True,
                "approved_at": now_iso(),
            }
        )
        print(f"Approved: {phone}")
        return 0

    if args.cmd == "remove":
        table.delete_item(Key=key(phone))
        print(f"Removed: {phone}")
        return 0

    if args.cmd == "check":
        r = table.get_item(Key=key(phone))
        item = r.get("Item")
        print("APPROVED" if item else "NOT_APPROVED")
        if item:
            print(item)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

