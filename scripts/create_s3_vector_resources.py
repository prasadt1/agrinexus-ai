#!/usr/bin/env python3
"""
Create Amazon S3 Vectors bucket + index for Bedrock Knowledge Bases (Titan Embed v2, 1024 dims).
Requires: pip install boto3, AWS credentials, region (default us-east-1).

Usage:
  export AWS_REGION=us-east-1
  python3 scripts/create_s3_vector_resources.py --bucket-name agrinexus-vectors --index-name agrinexus-fao-index

Then create a Knowledge Base in the Bedrock console using the printed index ARN, or use
scripts/rebuild-kb-s3-vectors.sh after setting INDEX_ARN and KB_ROLE_ARN.
"""
import argparse
import boto3
import sys


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bucket-name", default="agrinexus-vectors", help="Vector bucket name (globally unique)")
    p.add_argument("--index-name", default="agrinexus-fao-index")
    p.add_argument("--region", default=None)
    args = p.parse_args()
    region = args.region or boto3.session.Session().region_name or "us-east-1"

    try:
        client = boto3.client("s3vectors", region_name=region)
    except Exception as e:
        print(f"Could not create s3vectors client: {e}", file=sys.stderr)
        print("Upgrade boto3: pip install -U boto3 botocore", file=sys.stderr)
        return 1

    print(f"Region: {region}")
    try:
        br = client.create_vector_bucket(vectorBucketName=args.bucket_name)
        print(f"Vector bucket ARN: {br['vectorBucketArn']}")
    except Exception as e:
        err = str(e).lower()
        if "already" in err or "exists" in err or "duplicate" in err:
            print(f"Vector bucket {args.bucket_name!r} may already exist: {e}")
        else:
            raise

    try:
        ir = client.create_index(
            vectorBucketName=args.bucket_name,
            indexName=args.index_name,
            dimension=1024,
            distanceMetric="cosine",
            dataType="float32",
            metadataConfiguration={
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT"]
            },
        )
        print(f"Index ARN: {ir['indexArn']}")
    except Exception as e:
        err = str(e).lower()
        if "already" in err or "exists" in err or "duplicate" in err:
            print(f"Index may already exist: {e}")
        else:
            raise

    print("\nNext: create a Bedrock Knowledge Base with storage type S3 Vectors using the index ARN above.")
    print("See REBUILD-KB-WITH-S3-VECTORS.md and scripts/rebuild-kb-s3-vectors.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
