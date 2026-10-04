#!/usr/bin/env python3
"""
Spray-timing check against the live weather API: what a farmer in each district would be
told right now for "can I spray today?" and "can I spray tomorrow?", in all four languages.

Run it before deploying a change to common/spray_timing.py, and whenever the weather matters
for a demo. Read-only on AWS (reads the OpenWeatherMap key from Secrets Manager); nothing is
sent on WhatsApp and nothing is written.

Usage:
  python3 scripts/spray-timing-check.py
  python3 scripts/spray-timing-check.py --district Latur --dialect hi
  python3 scripts/spray-timing-check.py --raw        # also print the parsed conditions
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "common-layer" / "python"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--district", choices=("Latur", "Jalna", "Nagpur"))
    ap.add_argument("--dialect", choices=("en", "hi", "mr", "te"))
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--raw", action="store_true", help="print the parsed weather conditions too")
    args = ap.parse_args()

    os.environ.setdefault("AWS_REGION", args.region)
    os.environ.setdefault("AWS_DEFAULT_REGION", args.region)
    os.environ.setdefault("WEATHER_API_KEY_SECRET", "agrinexus/weather/api-key")

    from common import spray_timing

    if not spray_timing._api_key():
        print("No weather API key: check AWS credentials and the secret agrinexus/weather/api-key.")
        return 1

    districts = [args.district] if args.district else list(spray_timing.DISTRICT_COORDS)
    dialects = [args.dialect] if args.dialect else ["hi", "mr", "te", "en"]
    failures = 0
    for district in districts:
        now = spray_timing.current_conditions(district)
        tomorrow = spray_timing.tomorrow_conditions(district)
        print(f"\n=== {district}")
        if args.raw or now is None or tomorrow is None:
            print(f"now:      {now}")
            print(f"tomorrow: {tomorrow}")
        if now is None:
            print("!! current weather unavailable (the reply will say so)")
            failures += 1
        if tomorrow is None:
            print("!! forecast unavailable (the reply will say so)")
            failures += 1
        for dialect in dialects:
            print(f"--- [{dialect}] today:    {spray_timing.spray_timing_reply(district, dialect, 'today', now)}")
            print(f"--- [{dialect}] tomorrow: {spray_timing.spray_timing_reply(district, dialect, 'tomorrow', tomorrow)}")
    print()
    print("All lookups returned data." if not failures else f"{failures} lookup(s) returned nothing; see above.")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
