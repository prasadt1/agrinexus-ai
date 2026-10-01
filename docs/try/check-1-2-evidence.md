# Evidence brief: AgriNexus live checks 1 and 2 (crop-confidence work)

## The checks as originally written (by the author, before deploying)

Plan, verbatim:
1. Push `012b79a` so Cursor has the Marathi fix.
2. `sam deploy` from the branch, no merge yet.
3. Re-send the pink bollworm photo. Expect a question about sugarcane versus cotton, not sugarcane advice.
4. Re-send the whitefly photo. Expect Marathi headings and the split confidence line.
5. Merge to `main` once those two pass.
"Keep the merge until after step 4, so `main` never carries behavior that failed on the real stack."

"Check 1" = step 3. "Check 2" = step 4.

## Code under test (deployed, then merged as PR #9)

`src/processor/analyzer.py`, `process_image_message`, after the vision call:
- `contradicts` = model named a specific crop (not "unknown") AND it differs from the registered profile crop.
- If real crop photo + visible problem + crop_confidence != high + profile crop exists + NOT contradicts:
  answer immediately under "crop assumed from your profile" with a one-word correction line. No buttons.
- If real + visible + (crop_confidence != high OR contradicts):
  lead with the model observation, ask "looks like X, but your profile says Y, which crop?",
  buttons = [model crop, profile crop, next supported crop]. No chemical advice yet.
- Tapping a crop re-runs vision with the crop supplied as fact (`diagnose_with_confirmed_crop`)
  and returns the four-section reply.
- Gate 1 (non-crop block) and Gate 2 (leakage template) unchanged.

The vision model (Claude Sonnet 4.5 on Bedrock, temperature 0) is NOT deterministic for photo F:
it sometimes returns inferred_crop="unknown"/low, sometimes "Sugarcane"/high.

Local Bedrock replays before deploy (same code, real model, mocked WhatsApp/S3):
- F, Cotton profile: Sugarcane/high -> contradiction question, buttons [Sugarcane, Cotton, Wheat]
- F, Wheat profile: Sugarcane/high -> contradiction question, buttons [Sugarcane, Wheat, Cotton]
- G, Cotton profile: unknown/low -> assumed Cotton, pest advice, no buttons

## Live results on WhatsApp (Marathi profile, crop=Cotton, beta Lambda, after deploy of 012b79a)

All times UTC, from CloudWatch `/aws/lambda/agrinexus-processor-beta-dev`.

### Send A — photo F, 22:20:44
Log: `Relevance gate: relevance=unclear confidence=low` -> `Assumed profile crop Cotton (crop_confidence=low, model_crop=unknown)`
Reply (verbatim):
```
तुमच्या प्रोफाइलनुसार पीक कापूस गृहीत धरले आहे.

निदान (Diagnosis): पिकाच्या भागावर गुलाबी रंगाची इल्ली दिसत आहे जी सक्रियपणे खात आहे. पिकाचा प्रकार स्पष्ट नाही.
तीव्रता (Severity): उच्च
शिफारशी (Recommendations): या इल्लीला तात्काळ काढून टाका. स्पिनोसॅड किंवा क्लोरॅन्ट्रानिलिप्रोल आधारित कीटकनाशक फवारणी करा. रोज पिकाची तपासणी करा आणि अंडी किंवा इतर इल्ल्या असल्यास त्या काढून टाका. पिकाचा प्रकार ओळखण्यासाठी संपूर्ण झाडाचा स्पष्ट फोटो पाठवा.
विश्वास (Confidence): कीडीची ओळख मॉडेलने केली आहे. पीक कापूस तुमच्या प्रोफाइलवरून गृहीत धरले आहे, फोटोतून खात्री झालेली नाही. उच्च - इल्ली स्पष्टपणे दिसत आहे आणि ती पिकाला नुकसान करत आहे. परंतु पिकाचा प्रकार ओळखण्यासाठी अधिक माहिती आवश्यक आहे.

कापूस नाही? पिकाचे नाव पाठवा.
```
Note: recommendations end with "send a clear photo of the whole plant to identify the crop",
which conflicts with the stated assumption.

### Send B — photo G (whitefly), 22:22:39
Log: `Assumed profile crop Cotton (crop_confidence=low, model_crop=unknown)`
Reply (verbatim):
```
तुमच्या प्रोफाइलनुसार पीक कापूस गृहीत धरले आहे.

निदान (Diagnosis): पानावर पांढऱ्या रंगाच्या माशा (एफिड्स) मोठ्या संख्येने दिसत आहेत, ज्या रसशोषक किडी आहेत.
तीव्रता (Severity): उच्च
शिफारशी (Recommendations): तात्काळ उपाययोजना करा: (१) निंबोळीचे पाणी (५०० ग्रॅम निंबोळी १० लिटर पाण्यात) फवारणी करा, (२) इमिडाक्लोप्रिड किंवा डायमिथोएट कीटकनाशक शिफारशीनुसार वापरा, (३) माशांचा प्रादुर्भाव जास्त असल्यास ३-४ दिवसांनी पुन्हा फवारणी करा, (४) पिकाची नियमित तपासणी करा.
विश्वास (Confidence): कीडीची ओळख मॉडेलने केली आहे. पीक कापूस तुमच्या प्रोफाइलवरून गृहीत धरले आहे, फोटोतून खात्री झालेली नाही. उच्च - पानावर पांढऱ्या रंगाच्या माशा स्पष्टपणे मोठ्या संख्येने दिसत आहेत, परंतु पिकाची ओळख पत्त्याच्या आकारावरून निश्चितपणे करता येत नाही.

कापूस नाही? पिकाचे नाव पाठवा.
```
Before 012b79a the Marathi headings were the Hindi ones (सिफ़ारिशें, गंभीरता) and the
confidence section read "विश्वास: उच्च" directly under the assumption line.
Note: model calls whiteflies "aphids" (एफिड्स).

### Send C — photo F again, 22:28:16
Log: vision complete -> `Sending button message ... ऊसाच्या देठावर गुलाबी रंगाची इल्ली दिसत आहे...`
Reply (from screenshot):
```
ऊसाच्या देठावर गुलाबी रंगाची इल्ली दिसत आहे, जी ऊस पोखरणारी इल्ली असू शकते.

हे ऊस सारखे दिसते, पण तुमच्या प्रोफाइलमध्ये कापूस आहे. हे कोणते पीक आहे?
[ऊस] [कापूस] [गहू]
```
No chemical advice in this message.

### Send D — tap कापूस on Send C, 22:30:19
Reply (verbatim):
```
निदान (Diagnosis): कापसाच्या बोंडावर गुलाबी इल्ली (पिंक बॉलवर्म) दिसत आहे. इल्ली बोंडाच्या आतील भागात प्रवेश करून नुकसान करत आहे.
तीव्रता (Severity): उच्च
शिफारशी (Recommendations): तात्काळ प्रभावित बोंडे तोडून नष्ट करा. क्विनालफॉस 25% EC (2 मिली/लिटर पाणी) किंवा प्रोफेनोफॉस 50% EC (2 मिली/लिटर पाणी) यांची फवारणी करा. फेरोमोन सापळे (8-10 प्रति एकर) लावा. पिकाचे नियमित निरीक्षण करा आणि संक्रमित बोंडे काढून टाका.
विश्वास (Confidence): उच्च - कापसाचे बोंड आणि गुलाबी इल्ली स्पष्टपणे दिसत आहे. ही गुलाबी इल्ली कापसाची प्रमुख किड आहे.
```

## Sequence of events that matters for the verdict
- 22:06 UTC: 012b79a deployed.
- 22:20 Send A, 22:22 Send B.
- 22:25 UTC: PR #9 merged to main (CI green), on the basis of A and B.
- 22:28 Send C, 22:30 Send D (after the merge).

## Unrelated finding (not part of checks 1/2)
22:22:28 a text message from the same Marathi user got the English Bedrock knowledge-base
default "Sorry, I am unable to assist you with this request." This is not a Guardrail block,
so the localized-refusal code does not rewrite it.

## Question
Using the checks exactly as written, did check 1 pass? Did check 2 pass?
Was the merge at 22:25 justified at the time it was made?
Note any caveats that should change what happens next.

## Outcome (independent review, 2 Oct 2026)

- Check 1: partially at merge time; passed on Send C, three minutes after the merge.
  Send A took the assume branch. One live observation of the contradiction branch.
- Check 2: passed on Send B (Marathi headings, split confidence line).
- The 22:25 merge was not justified when made; Sends C and D justify it after the fact.
  Rule going forward: no merge until a log line shows the specific branch ran.
- The brief matched the code. The first vision call does not pass `confirmed_crop`,
  which is why the assume path could ask for a whole-plant photo.
- The contradiction branch is a backstop, not a demo beat: do not script a video
  segment that depends on it firing.

## Replay results after the review (local, real Bedrock, `scripts/vision-replay.py`)

Prompt changes on `feature/reinvent-visitor-path` (not deployed at time of writing):
`5060707`, `6089fdc` (no crop-identification photo request), `c34821a` (whitefly vs aphid),
`09b9753` (name the product when the pest is identified confidently).

Raw results: `docs/try/replays/`.

Confirmed-crop path before `09b9753`, 3 runs each (Marathi, Cotton):
- F: product named 3/3 (spinosad / emamectin, or quinalphos / profenofos with rates).
- G: whitefly 3/3, imidacloprid or thiamethoxam with rates 3/3.

After `09b9753`, 10 first-pass + 3 confirmed runs per photo:

| | First pass | Confirmed crop |
|---|---|---|
| F branch | assume 10/10, inferred crop unknown 10/10 | — |
| F product named | 0/10 | 3/3 |
| F photo request | 0/10 | 0/3 |
| G pest | whitefly 10/10 | whitefly 3/3 |
| G product named | 10/10 (imidacloprid / thiamethoxam, rates, sticky traps, neem) | 3/3 |
| G photo request | 0/10 | 0/3 |

Open problem on F first pass: with the crop unknown the model will not call the larvae
pink bollworm, so it names no product and refers the farmer to the agriculture officer.
In 8 of 10 runs it also suggested "लिंबूपाणी (5 मिली/लिटर)", which reads as lemon water;
it most likely means neem (लिंब), but a farmer would read lemon. The confirmed-crop path,
which knows the crop is cotton, does not have this problem.

Contradiction branch frequency is not measurable at this sample size: 0/10 here,
1/5 and 0/5 in earlier ad hoc runs, 1/2 live. Not recorded as a behaviour change.
