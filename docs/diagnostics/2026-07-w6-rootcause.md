# Root Cause Analysis – Phase 11 W6 (2026-07-22)

## Summary
After implementing the schema gate (`_validate_draft_schema`) and achieving 111/111 passing tests, the "리닌샵" chain (ID 64) failed at publishing Step 3 (techpawz) due to empty `featureimage`. Investigation reveals the failure originated from missing chart image generation, not from schema validation.

## Evidence from Drafts (pre‑publish)

| Step | H2 count (`## `) | Image markers (`<!--todo:image-->` or `<!--todo:chart-->`) |
|------|------------------|------------------------------------------------------------|
| 1 (rotcha) | 5 | 1 (`<!--todo:chart-->`) |
| 2 (informationhot) | 5 | 1 (`<!--todo:image-->`) |
| 3 (techpawz) | 6* | 1 (`<!--todo:image-->`, added after initial failure) |

\* Step 3 originally had 0 H2 and 0 image markers; after the first schema‑gate failure we added an image marker to satisfy the gate.

All three drafts passed the schema gate after the manual addition to Step 3.

## Published Output Analysis

### Step 1 (rotcha.kr)
- HTTP Status: **200**
- `<h2>` tags in HTML: **6** (draft had 5)
- `<img>` tags in HTML: **1**

### Step 2 (informationhot.kr)
- HTTP Status: **200**
- `<h2>` tags in HTML: **5** (matches draft)
- `<img>` tags in HTML: **1**

### Step 3 (techpawz.com)
- HTTP Status: **Failed** (deployment aborted due to empty `featureimage`)

## Root Cause Chain

1. **Schema Gate**: Correctly blocked Step 3 initially because it lacked any `<!--todo:image-->` or `<!--todo:chart-->` marker.
2. **Manual Fix**: Adding `<!--todo:image-->` to Step 3 draft allowed the sensors to pass.
3. **Image Generation Failure**: Even with a marker, the image pipeline did not produce a usable `featureimage` for Step 3.
   - Log shows: `[Hugo] image_keyword 없음, 썸네일 생성 스킵: 리린샵-20260722-s3`
   - This indicates `image_keyword` field was empty, so the system skipped image download and left `featureimage` blank.
4. **Missing Image Keyword**: The chart marker in Step 1 (`<!--todo:chart-->`) successfully triggered chart generation and produced an image, while the generic `<!--todo:image-->` in Step 2 and Step 3 relied on an `image_keyword` derived from the AI meta‑data. For Step 3 the AI did not supply an `image_keyword`, causing the image fetch to be skipped.

## Contributing Factors
- The schema gate validates presence of a marker but does **not** verify that the marker leads to a resolvable `image_keyword` or that an image will actually be fetched.
- The image pipeline distinguishes between `chart` markers (which trigger local chart generation) and generic `image` markers (which require an `image_keyword` from the LLM output).
- For Step 3, the LLM output likely contained `<!--todo:image-->` but without an accompanying `image_keyword` in the metadata, resulting in a silent skip.

## Conclusion
The immediate cause of the publishing failure is **missing `image_keyword` for the image marker in Step 3**, leading to an empty `featureimage` and aborting the Hugo deployment. The schema gate performed its intended function (blocking lack of markers) but does not guarantee downstream image availability.

## Recommended Fix (out‑of‑scope for W6)
Enhance the schema gate or the drafting stage to ensure that any `<!--todo:image-->` marker is accompanied by a non‑empty `image_keyword` (or that a `<!--todo:chart-->` marker results in a generated chart image). This could be a validation of the `meta` dict returned by `draft_single_post` before returning the draft markdown.