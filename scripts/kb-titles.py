#!/usr/bin/env python3
"""
Give the knowledge-base documents readable titles, so a farmer's source line reads
"ICAR-CICR Cotton Pest and Disease Advisory 2024" instead of "cotton-08-e75ba3c0.pdf".

Bedrock returns a document's metadata attributes with each citation when the file has a
sidecar "<file>.metadata.json" next to it in the data source bucket. The handlers show the
"title" attribute when it is there (common/source_labels.py) and the file name otherwise.

Step 1, draft (read-only on AWS):
  python3 scripts/kb-titles.py
    Lists every document in the knowledge base's S3 data source, suggests a title for each
    one that has none yet (data/fao-pdfs/en/new-sources/kb_manifest.csv by file name, then
    the PDF's own Title field, then the first line of its first page), and writes
    data/fao-pdfs/kb-titles.json. Read the file and fix the titles by hand. A title left
    empty is skipped.

Step 2, apply (writes to S3, starts an ingestion job):
  python3 scripts/kb-titles.py --apply
    Uploads "<file>.metadata.json" with {"metadataAttributes": {"title": ...}} for every
    non-empty title and starts one ingestion job on the data source. Titles appear in
    answers once the job has finished (a few minutes; check it in the Bedrock console).

The knowledge base ID is read from the live processor function, like scripts/text-replay.py.
Override with KNOWLEDGE_BASE_ID. Needs bedrock-agent, s3 and lambda read access; --apply
also needs s3:PutObject on the bucket and bedrock:StartIngestionJob.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAPPING = REPO / "data" / "fao-pdfs" / "kb-titles.json"
MANIFEST = REPO / "data" / "fao-pdfs" / "en" / "new-sources" / "kb_manifest.csv"
DOC_SUFFIXES = (".pdf", ".txt", ".md", ".html", ".htm", ".doc", ".docx", ".csv")
MAX_TITLE = 120


def knowledge_base_id(region: str, function_name: str) -> str:
    if os.environ.get("KNOWLEDGE_BASE_ID"):
        return os.environ["KNOWLEDGE_BASE_ID"]
    import boto3

    conf = boto3.client("lambda", region_name=region).get_function_configuration(FunctionName=function_name)
    return ((conf.get("Environment") or {}).get("Variables") or {})["KNOWLEDGE_BASE_ID"]


def s3_data_sources(agent, kb_id: str) -> list:
    """(data source id, bucket, prefixes) for each S3 data source of the knowledge base."""
    out = []
    for summary in agent.list_data_sources(knowledgeBaseId=kb_id).get("dataSourceSummaries", []):
        ds = agent.get_data_source(knowledgeBaseId=kb_id, dataSourceId=summary["dataSourceId"])["dataSource"]
        s3conf = (ds.get("dataSourceConfiguration") or {}).get("s3Configuration")
        if not s3conf:
            continue
        bucket = s3conf["bucketArn"].split(":::")[-1]
        out.append((ds["dataSourceId"], bucket, s3conf.get("inclusionPrefixes") or [""]))
    return out


def list_documents(s3, bucket: str, prefixes: list) -> list:
    keys = []
    for prefix in prefixes:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(DOC_SUFFIXES) and not key.endswith(".metadata.json"):
                    keys.append(key)
    return sorted(dict.fromkeys(keys))


def manifest_titles() -> dict:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8") as f:
        return {row["filename"].strip(): row["title"].strip() for row in csv.DictReader(f) if row.get("title")}


def clean(title: str) -> str:
    title = re.sub(r"^\s*microsoft (?:word|powerpoint) - ", "", title or "", flags=re.IGNORECASE)
    title = re.sub(r"\.(?:docx?|pptx?|pdf)$", "", title.strip(), flags=re.IGNORECASE)
    title = " ".join(title.split())
    return title[:MAX_TITLE]


def pdf_suggestion(data: bytes) -> tuple:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf not installed"
    try:
        reader = PdfReader(io.BytesIO(data))
        meta = clean(str((reader.metadata or {}).get("/Title") or ""))
        if len(meta) >= 8 and not re.fullmatch(r"[\w\-]+", meta):
            return meta, "pdf title field"
        text = reader.pages[0].extract_text() or "" if reader.pages else ""
        for line in text.splitlines():
            line = clean(line)
            if len(line) >= 8 and re.search(r"[A-Za-z]{3}", line):
                return line, "first line of page 1"
    except Exception as e:  # a broken PDF should not stop the listing
        return "", f"unreadable: {type(e).__name__}"
    return "", "no title found"


def current_title(s3, bucket: str, key: str) -> str:
    try:
        body = s3.get_object(Bucket=bucket, Key=key + ".metadata.json")["Body"].read()
        return str(json.loads(body).get("metadataAttributes", {}).get("title") or "")
    except Exception:
        return ""


def draft(s3, sources: list) -> dict:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8")) if MAPPING.exists() else {}
    from_manifest = manifest_titles()
    for _ds_id, bucket, prefixes in sources:
        for key in list_documents(s3, bucket, prefixes):
            uri = f"s3://{bucket}/{key}"
            if uri in mapping and mapping[uri].get("title"):
                continue
            title, how = current_title(s3, bucket, key), "existing metadata"
            if not title:
                title, how = from_manifest.get(key.rsplit("/", 1)[-1], ""), "kb_manifest.csv"
            if not title and key.lower().endswith(".pdf"):
                title, how = pdf_suggestion(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
            mapping[uri] = {"title": title, "suggested_by": how if title else how or "nothing"}
            print(f"{key}\n    {title or '(no title)'}   [{mapping[uri]['suggested_by']}]")
    MAPPING.parent.mkdir(parents=True, exist_ok=True)
    MAPPING.write_text(json.dumps(dict(sorted(mapping.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    empty = sum(1 for v in mapping.values() if not v.get("title"))
    print(f"\nWrote {len(mapping)} document(s) to {MAPPING.relative_to(REPO)}; {empty} without a title.")
    print("Check every title by hand, then run with --apply.")
    return mapping


def apply(s3, agent, kb_id: str, sources: list) -> int:
    if not MAPPING.exists():
        print(f"{MAPPING.relative_to(REPO)} not found. Run without --apply first.")
        return 1
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    written = 0
    touched = set()
    for ds_id, bucket, _prefixes in sources:
        for uri, entry in mapping.items():
            title = clean(entry.get("title") or "")
            if not title or not uri.startswith(f"s3://{bucket}/"):
                continue
            key = uri[len(f"s3://{bucket}/"):]
            body = json.dumps({"metadataAttributes": {"title": title}}, ensure_ascii=False).encode("utf-8")
            s3.put_object(Bucket=bucket, Key=key + ".metadata.json", Body=body, ContentType="application/json")
            written += 1
            touched.add(ds_id)
    for ds_id in sorted(touched):
        job = agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)["ingestionJob"]
        print(f"Ingestion job {job['ingestionJobId']} started on data source {ds_id} ({job.get('status')}).")
    print(f"Wrote {written} metadata file(s).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="upload the metadata files and start ingestion")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--function", default="agrinexus-processor-dev")
    args = ap.parse_args()

    import boto3

    kb_id = knowledge_base_id(args.region, args.function)
    agent = boto3.client("bedrock-agent", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)
    sources = s3_data_sources(agent, kb_id)
    if not sources:
        print(f"Knowledge base {kb_id} has no S3 data source.")
        return 1
    print(f"Knowledge base {kb_id}: " + ", ".join(f"s3://{b}/{p}" for _d, b, ps in sources for p in ps) + "\n")
    if args.apply:
        return apply(s3, agent, kb_id, sources)
    draft(s3, sources)
    return 0


if __name__ == "__main__":
    sys.exit(main())
