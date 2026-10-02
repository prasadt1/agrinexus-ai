#!/usr/bin/env python3
"""Delete reminder-*/expiry-* schedules whose one-time at() time has passed.

Schedules created before ActionAfterCompletion=DELETE stay after firing.
Dry run by default; pass --apply to delete.
"""
import argparse
import re
from datetime import datetime

import boto3

AT_RE = re.compile(r"^at\((\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\)$")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    scheduler = boto3.client("scheduler", region_name=args.region)
    now = datetime.utcnow()
    stale, kept = [], 0
    for prefix in ("reminder-", "expiry-"):
        for page in scheduler.get_paginator("list_schedules").paginate(NamePrefix=prefix):
            for s in page["Schedules"]:
                detail = scheduler.get_schedule(Name=s["Name"], GroupName=s.get("GroupName", "default"))
                m = AT_RE.match(detail.get("ScheduleExpression", ""))
                if m and datetime.fromisoformat(m.group(1)) < now:
                    stale.append((s["Name"], s.get("GroupName", "default")))
                else:
                    kept += 1

    print(f"{len(stale)} stale, {kept} kept")
    for name, group in stale:
        if args.apply:
            scheduler.delete_schedule(Name=name, GroupName=group)
        print(("deleted " if args.apply else "would delete ") + name)


if __name__ == "__main__":
    main()
