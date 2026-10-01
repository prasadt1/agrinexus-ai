# Visitor sample crop photo

Upload a license-free crop/leaf JPEG to the temp audio bucket before enabling
the sample “Photo diagnosis” list option in production.

Commercial-use candidates (Pexels / Unsplash, with provenance PDFs) live in
[`sample-photo-candidates/`](sample-photo-candidates/). Pick the winner after
sending A/B/C through the live bot, then:

```bash
aws s3 cp ./docs/try/sample-photo-candidates/WINNER.jpg \
  s3://agrinexus-temp-audio-dev-ACCOUNT/visitor-samples/crop-leaf.jpg \
  --content-type image/jpeg
```

Env (set by SAM): `VISITOR_SAMPLE_IMAGE_BUCKET`, `VISITOR_SAMPLE_IMAGE_KEY`
(default key `visitor-samples/crop-leaf.jpg`).
