# Visitor sample crop photo

The "Photo diagnosis" option on the re:Invent visitor list sends this photo to the
visitor, then the bot's diagnosis of it (REQ-VISITOR-004).

## Current photo (chosen 4 October 2026)

- **File:** [`sample-photo/F-usda-ars-pink-bollworm-cotton-boll-k10075-6.jpg`](sample-photo/F-usda-ars-pink-bollworm-cotton-boll-k10075-6.jpg)
- **Subject:** pink bollworm larvae (*Pectinophora gossypiella*) in an opened, damaged cotton boll.
- **Source:** USDA Agricultural Research Service, image K10075-6, https://www.ars.usda.gov/oc/images/photos/dec20/k10075-6/
- **Credit:** Photo courtesy of USDA ARS / Peggy Greb.
- **Terms:** US public domain. ARS asks for credit and does not allow any implication that ARS endorses a product (https://www.ars.usda.gov/oc/images/copyright/). The WhatsApp caption carries "(USDA ARS)". Do not describe AgriNexus AI as endorsed by or affiliated with ARS.
- **Provenance record:** [`sample-photo/F-provenance.pdf`](sample-photo/F-provenance.pdf), recorded 1 October 2026.
- **Crop setting:** `VisitorSampleImageCrop=Cotton` (the default). The crop is passed to the model as fact, so it must match the photo.

## Upload

```bash
aws s3 cp docs/try/sample-photo/F-usda-ars-pink-bollworm-cotton-boll-k10075-6.jpg \
  s3://agrinexus-temp-audio-dev-ACCOUNT/visitor-samples/crop-leaf.jpg \
  --content-type image/jpeg
```

Env (set by SAM): `VISITOR_SAMPLE_IMAGE_BUCKET`, `VISITOR_SAMPLE_IMAGE_KEY`
(default key `visitor-samples/crop-leaf.jpg`). The bucket's lifecycle rules expire only
`voice/`, `voice-output/` and `images/`, so the sample does not expire.

## Rejected

- A photo named "cotton-bollworm-test" (source unknown) was live from 3 to 4 October.
  It showed bean-like leaves, not cotton, while the bot was told the crop was cotton.
- CSIRO silverleaf whitefly on a watermelon leaf (CC BY 3.0): the lobed leaf would be
  labeled cotton by the crop setting, and the license needs attribution.
- Generic Pexels and Unsplash damaged-leaf photos: not field crops.

## Changing the photo

Pick a photo with a recorded source and license, set `VisitorSampleImageCrop` to the
crop actually in it, update this file and the caption credit in
`common/visitor.py`, upload, then pick "Photo diagnosis" as a visitor and read the reply
against the photo.
