# Visitor sample crop photo

Upload a license-free crop/leaf JPEG to the temp audio bucket before enabling
the sample “Photo diagnosis” list option in production:

```bash
aws s3 cp ./your-crop-leaf.jpg \
  s3://agrinexus-temp-audio-dev-ACCOUNT/visitor-samples/crop-leaf.jpg \
  --content-type image/jpeg
```

Env (set by SAM): `VISITOR_SAMPLE_IMAGE_BUCKET`, `VISITOR_SAMPLE_IMAGE_KEY`
(default key `visitor-samples/crop-leaf.jpg`).
