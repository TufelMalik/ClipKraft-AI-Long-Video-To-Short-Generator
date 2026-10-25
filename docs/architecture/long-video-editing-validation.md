# Long-form implementation validation — 25 October 2026

## Implemented scope

Local self-host editor with transcription-only upload, existing-source reuse, revision-checked
EDLs, persistent snapshots, source leases, occurrence/time maps, clean preview/export and mapped
caption sidecars. Cold opens have grounded candidate ranking, joined preview, explicit approval,
replace/remove and undo. Smart cuts have sentence-grounded occurrence-specific proposals,
protected ranges, retained repetition evidence, overlap subtraction, approval and batch undo.
YouTube has direct encrypted OAuth, PKCE/state/scope validation, owned-publication verification,
immutable export links, report normalization, heuristic observations and an accessible seek table.

All flags default off. Cloud availability is explicitly gated: this delivery does not include
cloud transactional tables/migrations, R2 artifact delivery, account erasure integration or
long-form watermark/metering. Existing cloud/shorts behavior is retained.

## Automated results

- Focused new-feature/recut/LLM/source/watermark/cleanup regression run: **102 passed, 5 skipped**.
- Final full suite with UTF-8: **1,239 passed, 26 skipped, 4 failed, 3 errors**.
- An untouched `git archive HEAD` snapshot reproduced all seven remaining failures/errors in
  the affected modules: static restoration, missing platform font, two POSIX-only ASR flock
  expectations on Windows, and three stdio tests looking for the old root `mcp_stdio.py` path.
- Without `-X utf8`, two additional baseline subtitle tests fail on Windows default text decoding.
- Frontend `npm run lint` and `npm run build`: **passed**. Existing build notices remain for
  unset OpenPanel placeholders, stale Browserslist data and large chunks.
- `git diff --check` passes.

No baseline regression failures were silently skipped or claimed fixed. Small pre-existing lint
issues were corrected: unused state setter/read, commented empty catches, JSX component argument
recognition and excluding the generated vendor analytics bundle from source lint.

## Media and browser evidence

- Deterministic six-second red/green/blue + audio fixture: teaser/body decoded pixel order,
  source aspect ratio, audio stream presence, joined duration, Hindi caption text/timestamps,
  silent input and temporary-file cleanup pass.
- `scripts/verify_longform_media.py` generated a source with a visible frame/time counter,
  prepended source seconds 180–182 and exported **192 seconds**, exceeding the unchanged
  shorts ceiling of 180 seconds. Full FFmpeg video/audio decode passed. Opening and ending
  frames were visually inspected: source counters 3:01 and 3:09 at the expected positions.
- Synthetic render/full decode/stills took approximately 7 seconds on this test host; output
  was approximately 6.8 MB. This is a small 320×180/10fps test pattern, not a capacity claim.
  Peak process/GPU/RSS and representative high-resolution disk use were not measured.
- Browser fixture against real new APIs: project load, full preview, protected-range save,
  undo, redo and export pass. Export labels retain the rendered revision. Missing Qwen yields
  `model_unavailable` while manual editing/export remain enabled. Google configuration is
  intentionally absent; no real Google account was connected during testing.
- API tests additionally verify preview approval requirements, stale/repeated applications,
  source verification, bounded workload admission, cancellation and transcription-only upload.

Generated evidence is local and ignored under `.cache/longform-media/`: playable MP4, SRT,
opening/body/middle/ending PNGs, join WAV and `verification.json`. Test logs and the untouched
baseline snapshot also remain ignored under `.cache/`.

## Remaining release gates and limitations

No local llama.cpp executable/GGUF was found in the project environment. Live inference,
non-thinking compatibility and editorial usefulness on reviewed English/Hindi/Hinglish footage
remain unverified. Tests with schema-valid mocked advice establish grounding and mutation behavior,
not editorial quality. Suggestions stay default-off and never apply automatically.

Google client configuration, consent verification where applicable, a channel-owned publication
and an authorized real retention report remain external dependencies. Report/OAuth behavior has
mocked coverage; real quota, consent and account/channel behavior need a connected-account test.

Long-form captions are selectable VTT/downloadable SRT, not styled burned captions. New URL-only
ingestion, cloud deployment, manual publication alignment, persistent UI undo-stack navigation,
restore-upload into an existing project and automatic operation resumption are not included.
Shutdown cancels work; dead-worker operations require retry. Media expiry preserves manifests.
Frame-duration discrepancies above 250ms fail export instead of declaring an inaccurate timeline.

See [setup and operational details](long-video-editing-setup.md) for configuration, credentials,
flags, resource ceilings, retention, rollback and known platform constraints.
