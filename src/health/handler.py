import json
import os
from datetime import datetime, timezone


def lambda_handler(event, context):
    version = os.environ.get("APP_VERSION", "1.0.0")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "status": "ok",
                "version": version,
                "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        ),
    }

