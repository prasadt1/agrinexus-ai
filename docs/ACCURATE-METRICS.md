# Accurate Metrics (README backing)

This note exists to back the headline metrics referenced in `README.md` with concrete counts derived from the repo.

**Last updated:** April 24, 2026

---

## SAM resources (Infrastructure-as-Code)

Counted from `template-week2.yaml` as **non-`String`** entries under `Resources`.

**Total:** **31** resources

Breakdown:

- **10** `AWS::Serverless::Function`
- **8** `AWS::CloudWatch::Alarm`
- **3** `AWS::SQS::Queue`
- **2** `AWS::Serverless::Api`
- **1** `AWS::WAFv2::WebACL`
- **1** `AWS::WAFv2::WebACLAssociation`
- **1** `AWS::Serverless::StateMachine`
- **1** `AWS::Lambda::EventSourceMapping`
- **1** `AWS::Serverless::LayerVersion`
- **1** `AWS::SNS::Topic`
- **1** `AWS::S3::Bucket`
- **1** `AWS::IAM::Role`

> Note: The template also contains **8** `Type: String` entries under `Resources` (parameters/strings used by SAM); these are **not** deployed AWS resources.

---

## Test-to-code ratio (how to interpret “64%”)

Depending on what you count as “source”, the ratio varies:

- **Handlers-only** (Lambda handler-heavy view) tends to be higher
- **All source code** (including shared helpers, non-handler modules) tends to be lower

The README’s **64%** is a **reasonable headline** between those bounds. If you need a fully reproducible calculation script, add one locally (don’t run it in CI).

