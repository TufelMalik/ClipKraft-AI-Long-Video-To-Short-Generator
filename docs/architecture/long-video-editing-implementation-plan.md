# Long Video Editing — Implementation Plan

Status: proposed implementation plan; no feature implementation is included in this document.

Prepared: 25 October 2026.

## 1. Objective and agreed decisions

Add these three features, in this order, to ClipKraft/OpenShorts:

1. **Cold-open builder:** suggest a compelling source excerpt, preview it, and insert it before the main video.
2. **Story-based smart cuts:** suggest removable repetition, unnecessary setup, and weak portions; apply only the user's selected cuts.
3. **Retention feedback in the editor:** connect an owned YouTube publication to its exact exported edit and show retention observations against that timeline.

The intended output is an edited **long-form video**, rather than only shorts extracted from a long source. Existing shorts must continue to work.

Agreed model: **Qwen3-0.6B**, run locally with **llama.cpp**. Start with the official **Qwen3-0.6B-GGUF Q8_0** distribution. The small parameter count is the preference; editing quality must still be evaluated on Hindi, Hinglish, and English footage.

Keep the model advisory. It must not invent spoken text, fabricate timestamps, or change a video without an explicit editor action. Suggestions and previews are reversible. No paid model/API fallback, automatic publishing, or guaranteed viral-success percentage is part of this scope.

This plan intentionally contains no implementation-duration estimates.

## 2. What already exists and what must change

The following observations come from the current repository, rather than assumptions about an empty project.

| Existing area | Current evidence | Implementation implication |
|---|---|---|
| Video ingestion and transcription | `main.py`, `app.py`, `backend/pipeline/subtitles.py`; faster-whisper in `requirements.txt` | Reuse retained source files and word timestamps. Avoid retranscription on every suggestion request. |
| Clip recut engine | `backend/pipeline/recut.py` | Reuse cut/concat and transcript-remapping concepts. Current limits are 12 segments and 180 seconds. |
| Existing editor | `dashboard/src/components/ClipEditor.jsx` | Existing undo/redo and source-segment interaction provide patterns, but are built around a clip index. |
| Editor API | `GET /api/clip/{job_id}/{clip_index}/edl`, `POST /api/clip/rerender` in `app.py` | Keep these routes backward compatible. Add long-form project routes separately. |
| Local text model adapter | `backend/services/llm_backend.py` | Already supports OpenAI-compatible endpoints, structured-output fallback, and Pydantic validation. Its current default model is not Qwen3-0.6B. |
| Captions and framing | `recut.virtual_transcript()`, existing caption regeneration, layout range mapping | Every cut and repeated teaser needs a correct output-to-source time map. |
| YouTube posting/autopilot | Posting routes in `app.py`; `cloud/autopilot.py` uses Upload-Post | A connected posting account does not establish direct access to YouTube Analytics scopes or refresh tokens. |
| Existing application analytics | `cloud/analytics.py`, `dashboard/src/lib/analytics.js` | These measure product activity. Add a separate service for audience retention data. |
| Ownership, delivery, storage | Job ownership checks, clean/served file split, retention sweep, cloud account deletion | New project files and tables must participate in these existing lifecycle rules. |

Before editing a subsystem, read its applicable architecture documentation, particularly clip selection, layouts/reframing, jobs/deploys, billing/account, and agent access.

## 3. Shared foundation: a long-form edit project

### 3.1 Project creation and editor entry

Add an **Edit full video** entry after source ingestion/transcription. The user must be able to create a long-form project without first generating short clips or running paid moment selection.

The project initially contains one segment spanning the available source. Preserve the source aspect ratio and original timing by default. Do not inherit the manual-shorts path's automatic speedup, vertical crop, or outro.

If a completed job still has its source and transcript, reuse them. For a new upload, run only the required ingestion/transcription stages. If the source has expired, report that before allowing any source-dependent render; use the existing restore path where available.

Maintain a dedicated long-form policy object. Do not raise `recut.MAX_TOTAL_SECONDS` globally, because existing shorts APIs and tests depend on the clip limit. Make project duration, segment count, file size, temporary disk use, and render concurrency bounded server settings. Select their release defaults from representative local render measurements before enabling long-form export.

### 3.2 Canonical project representation

Store a versioned source-based edit decision list (EDL). Use integer milliseconds internally; translate to seconds at the current FFmpeg/transcript boundaries.

Proposed shape; identifiers below are illustrative:

```json
{
  "schema_version": 1,
  "project_id": "project_example",
  "job_id": "job_example",
  "revision": 3,
  "source": {
    "asset_id": "source_example",
    "fingerprint": "sha256:example",
    "duration_ms": 2400000
  },
  "transcript_version": "transcript_example",
  "output": {"aspect_ratio": "source", "playback_rate": 1},
  "segments": [
    {
      "id": "segment_teaser",
      "source_start_ms": 840000,
      "source_end_ms": 848000,
      "role": "cold_open"
    },
    {
      "id": "segment_body",
      "source_start_ms": 0,
      "source_end_ms": 2400000,
      "role": "body"
    }
  ],
  "protected_ranges": [],
  "applied_suggestion_ids": [],
  "render_state": "idle"
}
```

The teaser remains in its original story position by default. Repetition is deliberate and is represented by distinct segment IDs. Removing the original occurrence is a separate user-approved edit.

Derived duration is the sum of segment durations. The server validates finite bounds, source coverage, positive lengths, configured caps, stable IDs, and media availability. Do not trust model- or browser-supplied durations.

### 3.3 One shared time-map implementation

Implement a pure module for mapping output intervals to source intervals and vice versa. Each map entry records segment ID, source bounds, and output bounds.

- A source moment can appear multiple times, especially after adding a cold open. Source-to-output mapping returns a list of occurrences.
- Removed source ranges have no output occurrence.
- Intervals crossing an edit boundary split into multiple map entries.
- Use half-open intervals consistently to prevent duplicate words at joins.
- Tie subtitle and layout remapping to the same map. Do not maintain separate arithmetic in the browser and backend.
- Store an immutable time map with each completed export revision.

Existing `virtual_transcript()` is a useful reference. For long projects, index transcript words once and slice indexed intervals, instead of repeatedly flattening the entire transcript for every segment.

### 3.4 Revisions, persistence, and background work

- Every successful edit creates a new revision. Requests include `expected_revision`; return `409 revision_conflict` for stale changes.
- Persist EDL, suggestion provenance, and export manifests server-side. Browser storage is not the authoritative project store.
- Self-host: use server-owned files under the job directory, atomic replacement, and an interprocess-safe lock. Cloud: use transactional project records and existing storage adapters. An in-memory `asyncio.Lock` alone is insufficient across multiple workers.
- Suggestions, previews, and exports run as bounded background operations with status, cancellation, and failure reporting. No long FFmpeg/model calls inside the async request handler.
- Persist operation manifests so restart behaviour is explicit: resume supported work or mark it interrupted with a retry action.
- A failed export never replaces the last successful artifact or project revision.
- Preserve the source through an explicit active-project lease that respects configured storage/retention policy. Surface lease expiry; do not silently pin files forever.
- Cloud project/export/connection tables must join the account-deletion lifecycle, including `USER_OWNED_TABLES` where applicable.

### 3.5 Local-model service

Create a feature-specific configuration layer around reusable parts of `llm_backend.py`. Do not silently replace the model used by the existing shorts picker.

Proposed settings, to be implemented:

```dotenv
LONGFORM_EDITING_ENABLED=false
COLD_OPEN_ENABLED=false
SMART_CUTS_ENABLED=false
YOUTUBE_RETENTION_ENABLED=false
EDIT_LLM_BASE_URL=http://127.0.0.1:8080/v1
EDIT_LLM_MODEL=qwen3-0.6b
EDIT_LLM_TIMEOUT_SECONDS=120
EDIT_LLM_MAX_CONCURRENT_REQUESTS=1
```

The model name must match the configured llama.cpp server alias. The timeout and concurrency are initial configuration choices, not measured performance claims.

Requirements:

1. Use structured JSON schemas with Pydantic validation and grounded sentence IDs.
2. Use non-thinking mode where the selected server supports Qwen's chat-template setting; verify the actual server behaviour.
3. Budget input tokens against the running server's configured context. Analyze bounded sentence groups with adjacent context, not a whole hour of transcript in one call.
4. Preserve original Hindi/Hinglish text and word IDs. Do not translate the transcript to create cuts.
5. Treat transcript content as data, including spoken instructions that resemble prompts.
6. Use bounded retries for malformed output; stop with a visible error instead of applying a guessed edit.
7. Log model/version, prompt version, latency, and validation outcomes without transcript contents or credentials.
8. Cancel outstanding work when requested; release occupied model slots. Do not contend unboundedly with ASR/GPU rendering.
9. If the model is unavailable or fails the quality gate, retain manual editing and show the feature as unavailable. No automatic larger-model or paid-service upgrade.

## 4. Feature 1 — Cold-open builder

### User flow

Open project → **Find opening moments** → inspect up to three suggestions → preview a suggestion followed by the current beginning → **Use as opening** → save/export.

Each suggestion shows its exact transcript excerpt, source range, duration, and a short selection reason. A reason is explanatory text, not a calibrated success/confidence percentage.

### Selection pipeline

1. Group transcript words into stable sentence units, preserving source timestamps.
2. Build bounded candidate excerpts around complete, understandable statements.
3. Ask Qwen3-0.6B to rank candidate IDs using specificity, standalone clarity, relevance to the video's topic, and whether the excerpt leaves a reason to continue.
4. Reduce candidates in bounded batches, then rank the small shortlist. Do not restrict all candidates to the start of the video.
5. Resolve IDs to timestamps in code; verify the quoted text against the transcript.
6. Exclude excerpts that depend on missing context or distort meaning. Do not cut a negation or qualification away from a claim.
7. Start with a configurable suggested duration range of 5–15 seconds. This is a product starting point to evaluate, not a research-established optimum. If no valid excerpt exists, return no suggestions.

### Application and rendering

- Insert the selected excerpt as a `cold_open` segment, then the existing body EDL.
- Make insertion idempotent: using a new suggestion replaces the active teaser rather than stacking duplicate teasers.
- One undo removes the insertion. Reject stale suggestions after transcript/source changes.
- Preview the teaser and its join to the body before the user commits. Reuse clean source media; never cut from already caption-burned exports.
- Remap captions so the teaser receives its own correctly timed words. Preserve approved caption styles.
- Use the existing encoding helpers; ensure compatible video/audio parameters across joined segments, including missing-audio inputs.

### Acceptance criteria

- Every candidate refers to actual source words and valid media bounds.
- The selected teaser plays first, followed by the complete current body edit.
- Replacing/removing a teaser and undo/redo produce the expected EDL without duplicate application.
- Preview and final render use the same EDL revision and transcript map.
- No suggestion request modifies video files or saves an edit by itself.

## 5. Feature 2 — Story-based smart cuts

### MVP boundary

Start with **suggested deletions that preserve story order**. Automatic narrative rearrangement, voice generation, and reconstructed sentences are outside this version. Qwen3-0.6B has not demonstrated reliable full-story rewriting on this project's footage.

### User flow

Open **Smart cuts** → analyze current body → review cards and highlighted transcript ranges → compare before/after around a cut → accept/reject individually → **Apply selected cuts** → undo or export.

Cards show the exact excerpt, category, reason, and time saved. Add **Keep this section** to protect a range. A protected range is always enforced by code.

### Suggestion pipeline

1. Analyze current body occurrences, excluding the teaser and already removed material.
2. Identify candidate repetition and long setup using transcript structure. Ask the model for `start_sentence_id`, `end_sentence_id`, `category`, and `reason`.
3. Repetition candidates must identify the retained occurrence as supporting evidence. Repeated wording can be emphasis, so never auto-delete it.
4. Supply context on both sides of each candidate. Check whether removal leaves broken references, contradicts later statements, or removes a premise required for the payoff.
5. Validate IDs, bounds, sentence completeness, current-EDL coverage, protected ranges, and teaser overlap. Uncertain/context-dependent suggestions remain review-only or are discarded.
6. Keep silence/VAD observations distinct from semantic judgments. Silence does not prove a section is weak.
7. Return a bounded, deduplicated suggestion list. Do not target an arbitrary percentage of footage to remove.

### Applying cuts

- Anchor each suggestion to the analyzed project revision and segment occurrence ID. Removing one source occurrence must not accidentally remove its cold-open occurrence.
- Convert accepted deletions into a new retained-segment EDL using deterministic interval subtraction.
- Merge overlapping approved deletions, resolve touching edges consistently, and reject a batch that removes all footage or violates media bounds.
- Snap to complete words/sentences and validate again after snapping. Preserve sensible speech handles; provide manual adjustment when a join sounds abrupt.
- Apply a selected batch as one revision and one undo action. Reanalyze after subsequent material edits; stale cards cannot be applied silently.
- Do not introduce new speed changes or crossfades in the first version. Any later transition must be represented in the time map.

### Acceptance criteria

- No footage disappears until the user explicitly applies selected cuts.
- Applying overlapping cuts creates a valid, ordered EDL with correct output duration.
- Protected ranges, negations, and separately selected teaser occurrences are preserved.
- Before/after previews and transcript highlights match the proposed deletion.
- Undo restores the exact prior revision, including captions and the teaser selection.

## 6. Feature 3 — Retention feedback in the editor

### 6.1 Google connection and publication linking

Implement a separate direct Google OAuth connection for YouTube read access. Do not assume the current Google login, MCP OAuth, or Upload-Post connection exposes the necessary credentials.

- Enable YouTube Analytics API and YouTube Data API in the configured Google project.
- Request read-only scopes required by current official documentation: `yt-analytics.readonly` and `youtube.readonly`. Verify granted scopes on callback.
- Use state validation, PKCE where applicable, exact redirect allowlists, and server-side refresh handling.
- Cloud credentials must be encrypted at rest. For self-host, require an authenticated local session/loopback setup and protected server-side credential storage. Never put refresh tokens in browser storage or project JSON.
- A Google OAuth client still requires installation configuration. Public distribution may require Google's consent-screen verification; this is an external release dependency, not a coding task completed by this plan.
- Disconnect revokes/deletes credentials and removes cached data according to the applicable API policy.

Allow the user to paste a YouTube video ID/URL. Validate the ID, obtain video metadata, and verify the publication belongs to the connected channel. A URL parser must not make arbitrary outbound URL requests.

Link the publication to an **immutable completed export** containing export ID, project revision, duration, EDL hash, time map, and file fingerprint. Persist that manifest beyond temporary media expiry. A project may have multiple publication links to different exports.

For a manually uploaded video, require confirmation that it is the selected export. Duration similarity is a useful check, not proof of identity. If the publication was edited externally, mark timeline mapping unverified and require an explicit alignment/new export link.

### 6.2 Fetching and normalizing retention

Use a server-side request shaped as follows:

```text
GET https://youtubeanalytics.googleapis.com/v2/reports
ids=channel==MINE
startDate=<selected start date>
endDate=<selected end date>
dimensions=elapsedVideoTimeRatio
metrics=audienceWatchRatio,relativeRetentionPerformance
filters=video==<one verified video ID>
```

Validate response headers and optional metric availability. Fetch summary metrics such as views and average view duration through a separate supported report; do not assume arbitrary metric combinations work with the retention dimension.

Official documentation specifies **100 equally spaced intervals**, with ratios from `0.01` to `1.0`. The ratio is the exclusive end of each interval:

```text
bucket_end_ms = elapsedVideoTimeRatio * published_duration_ms
bucket_start_ms = previous_bucket_end_ms
```

A two-hour publication therefore has approximately 72-second retention intervals. The application must not claim frame-accurate drop detection or exact 30-second retention from such data. Show the nearest available interval or an explicitly labelled estimate; omit the 30-second metric when resolution is unsuitable.

`audienceWatchRatio` can exceed 1 because portions can be watched repeatedly. Do not clamp it to 100% or label it as an exact count of unique viewers remaining. Relative retention is a comparison metric, not a viral probability.

Store the raw response, normalized buckets, query date range, fetch time, video duration, publication/export identity, and metric definitions. Distinguish unavailable metrics from zero values.

Cache by connection/channel/video/date-range/export identity. Start with on-demand refresh and a configurable cache TTL; no background monitoring is required for this feature. Handle `401`, revoked access, `403`, rate limits, empty reports, and network failures separately. Respect current Google data refresh/deletion requirements.

### 6.3 Timeline mapping and observations

Display the publication's immutable output timeline as the primary graph. Selecting a bucket seeks the matching exported video/range and highlights its source occurrences through the stored time map.

If the user has made a newer edit, keep the graph labelled with its original export revision. Source mapping may highlight corresponding ranges in the new draft, but must not imply the draft has measured retention. Removed material and repeated teaser occurrences need explicit treatment.

For the first detector:

1. Keep raw buckets available; apply any smoothing only as a labelled display/detection layer.
2. Compute local drops and peaks against adjacent buckets and a configurable local baseline.
3. Require sufficient valid data and a configurable minimum prominence. These are heuristic review markers, not YouTube's proprietary Studio moment labels.
4. Attach the bucket range, measured ratios, and a neutral note such as “Retention is lower than nearby intervals; review this section.”
5. Never assert that an edit, joke, B-roll, or topic caused a drop from correlation alone.
6. Never auto-delete a dip. A marker can open a manual review or a new smart-cut analysis.

YouTube notes retention data typically takes 1–2 days to process. Empty results must show **Data not available yet** or another applicable state, rather than a flat zero graph. Do not impose Studio's highlighted-moment thresholds as undocumented API eligibility rules.

### Acceptance criteria

- Only a properly authorized channel/publication can be linked or queried.
- Bucket times use the published duration and exact linked export revision.
- Repeated source moments map to the correct output occurrence.
- Missing/sparse data, delayed data, values above 100%, and expired OAuth tokens render correctly.
- Editing a new revision never reassigns historical analytics to it.
- Analytics failures cannot prevent local editing or exporting.

## 7. Proposed modules and API contracts

Names below are proposed files, not claims that these files already exist.

| Location | Responsibility |
|---|---|
| `backend/pipeline/edit_project.py` | Project/EDL schemas, versioning, validation, and long-form policy |
| `backend/pipeline/timeline_map.py` | Pure interval and occurrence mapping; transcript/layout remapping |
| `backend/pipeline/cold_open.py` | Candidate construction, ranking validation, teaser application |
| `backend/pipeline/smart_cuts.py` | Sentence analysis, candidate validation, deterministic interval subtraction |
| `backend/pipeline/longform_render.py` | Preview/export orchestration using existing FFmpeg helpers |
| `backend/services/edit_llm.py` | Isolated Qwen3-0.6B configuration, token budgeting, structured requests |
| `backend/services/edit_project_store.py` | Self-host/cloud persistence adapter, revisions, atomic updates |
| `backend/services/youtube_retention.py` | Authorized report fetching, cache, normalized buckets |
| `backend/services/retention_observations.py` | Heuristic bucket-level markers, separate from API data |
| `backend/api/edit_projects.py` | Project, suggestion, preview, operation, and export routes |
| `backend/api/youtube_analytics.py` | Connection, publication-link, report, and disconnect routes |
| `dashboard/src/components/LongVideoEditor.jsx` | Dedicated project editor, reusing existing editor patterns |
| `dashboard/src/components/ColdOpenPanel.jsx` | Suggestion cards, joined preview, replace/remove teaser |
| `dashboard/src/components/SmartCutsPanel.jsx` | Review cards, protected sections, before/after preview |
| `dashboard/src/components/RetentionPanel.jsx` | Export-specific graph, empty/error states, marker navigation |
| `cloud/models.py` and an Alembic migration | Cloud projects, connections, exports, operations, and publication links |

Mount new routers from `app.py` and reuse its auth/ownership/storage helpers through small shared adapters. Avoid adding another large set of unrelated handlers to `app.py`.

### API outline

```text
POST   /api/edit-projects                         Create from an owned ingested source/job
GET    /api/edit-projects/{id}                    Project, revision, capabilities, source status
PATCH  /api/edit-projects/{id}                    Revision-checked manual EDL/protected-range update
POST   /api/edit-projects/{id}/cold-open/analyze   Start advisory candidate generation
POST   /api/edit-projects/{id}/cold-open/apply     Apply/replace a selected teaser with revision check
POST   /api/edit-projects/{id}/smart-cuts/analyze  Start advisory body analysis
POST   /api/edit-projects/{id}/smart-cuts/apply    Apply selected suggestion IDs with revision check
POST   /api/edit-projects/{id}/preview             Queue a bounded EDL preview
POST   /api/edit-projects/{id}/exports             Queue immutable full export
GET    /api/edit-operations/{id}                  Owner-scoped progress/result/error
POST   /api/edit-operations/{id}/cancel           Request cancellation
POST   /api/youtube-analytics/connect             Start OAuth; session-authenticated action
GET    /api/youtube-analytics/callback            Validate state/code and persist granted connection
DELETE /api/youtube-analytics/connection           Revoke/delete connection and associated cache
POST   /api/edit-projects/{id}/publications        Verify and link video ID to completed export ID
GET    /api/edit-projects/{id}/retention           Cached report for an authorized publication link
POST   /api/edit-projects/{id}/retention/refresh   Queue authorized report refresh
```

Background submissions return `202` with an operation ID. Mutations include `expected_revision`; analysis responses include the analyzed revision. Application accepts stored suggestion IDs, not arbitrary model-returned timestamps. Resolve project, export, operation, and publication ownership independently.

Expose machine-readable states including `source_missing`, `model_unavailable`, `invalid_model_output`, `revision_conflict`, `analysis_stale`, `connection_required`, `reconnect_required`, `report_pending`, and `publication_mismatch`.

## 8. Free/open-source dependency choices

| Component | Choice | Cost/license boundary |
|---|---|---|
| Local language model | Official Qwen3-0.6B GGUF Q8_0 | Apache-2.0 model distribution; validate editing quality locally |
| Inference runtime | llama.cpp | MIT; local server, no mandatory paid inference service |
| Transcript | Existing faster-whisper | MIT; reuse existing configuration |
| Video operations | Existing FFmpeg/ffprobe | Open source; comply with the selected build's license |
| Validation and HTTP | Existing Pydantic/httpx | Reuse installed dependencies after checking pinned compatibility |
| Credential encryption | `cryptography` if no suitable repository adapter exists | Open source; add a pinned dependency only when needed |
| Retention data | Google YouTube Analytics/Data APIs | Proprietary services; read access within their current terms/quotas, no paid analytics vendor required |
| Retention chart | React + SVG with keyboard-accessible data/table view | No charting SaaS dependency |

Software availability does not eliminate local CPU/GPU, memory, disk, or electricity costs. The plan does not require paid stock footage, Gemini, Upload-Post, or generative-video services for these three features.

## 9. Verification and quality gates

### Pure logic and API tests

- EDL validation: non-finite values, out-of-bounds times, empty output, long-form policy versus unchanged shorts limits.
- Time maps: teaser duplication, deleted intervals, boundaries, multi-segment buckets, correct subtitle ordering, and layout-range remapping.
- Smart cuts: overlap merging, occurrence-specific deletion, protected ranges, stale proposals, complete rollback.
- Model handling: malformed JSON, unknown sentence IDs, injected instructions in transcript, timeout, unavailable model, no paid fallback.
- API/persistence: unauthorized IDs, stale revisions, duplicate submissions, simultaneous saves, restart recovery, cancelled operations, partial write protection.
- OAuth/report handling: invalid state, insufficient scopes, foreign channel, refresh failures, zero versus unavailable data, schema changes, and cache isolation.
- Retention mapping: a two-hour video with 72-second buckets, ratios above 1, a modified draft, mismatched publication duration, repeated teaser occurrences.
- Account/file lifecycle: disconnect, account deletion, source lease expiry, restore, export manifest persistence, clean versus served artifacts.

### Media integration checks

Use a small deterministic fixture with spoken words and a visible time counter, plus a project-owned long-duration fixture for the full export gate.

Verify the teaser/body join, frame order, audio continuity, caption sync at beginning/middle/end, preview-versus-export agreement, original aspect ratio, cancellation cleanup, and failure recovery. Inspect playable output as well as ffprobe metadata. Measure memory/disk/concurrency on the intended host before choosing long-form release caps.

Add targeted tests under `tests/`, following current imports and fixture conventions. Run the relevant Python suite and existing recut/LLM regression tests. For frontend code, run `npm run build` and `npm run lint` in `dashboard`, plus interaction checks for preview, undo/redo, stale suggestions, and retention seeking.

### Qwen3-0.6B editorial evaluation

Build a reviewed evaluation set from project-owned Hindi, Hinglish, and English videos with stable sentence annotations. Include negations, repeated emphasis, incomplete claims, delayed payoff, sarcasm, and poor-ASR examples.

Measure valid-schema rate, grounded-range rate, useful-teaser selection, inappropriate-removal suggestions, and human acceptance/rejection. Record the model artifact, server version, prompt version, context configuration, and results. These are engineering quality measurements, not viral-success predictions.

All applied ranges must pass deterministic grounding checks. Meaning-changing failures in the reviewed evaluation set block default enablement. If the 0.6B model remains unsuitable, ship manual controls and keep automated suggestions disabled; do not silently violate the chosen model preference.

## 10. Delivery sequence and completion gates

| Order | Deliverable | Gate to continue |
|---|---|---|
| Foundation | Long-form source entry, project store, time map, bounded background renderer, isolated local-model adapter | An unedited full video exports correctly; existing shorts remain unchanged |
| Feature 1 | Candidate analysis, joined preview, insert/replace/remove cold open | Grounded candidates, correct teaser/caption mapping, undo, and model failure handling pass |
| Feature 2 | Reviewed deletion suggestions, protected ranges, occurrence-aware application | Meaning-preservation evaluation, overlap handling, previews, and rollback pass |
| Feature 3 | Direct OAuth, immutable publication link, retention fetch and graph | Authorized real report and all delayed/mismatched-data cases pass |
| Release | Feature flags, setup docs, resource caps, lifecycle checks | Required tests/build/lint and representative long-form media verification pass |

Deliver the feature work in that order. The shared foundation is necessary for all three; it does not replace the agreed priorities. Feature 3 should not block release of verified local editing features if Google configuration or verification is still pending.

Use independent feature flags. Rollback disables new entry points and new operations while preserving projects, completed exports, and readable data. Do not delete artifacts as a rollback mechanism.

## 11. Measuring outcomes after release

Collect minimal product events: analysis completed/failed, suggestion previewed, accepted/rejected, cut undone, export completed/failed, publication linked, and retention refreshed. Use IDs and timings rather than raw transcript text or tokens.

For editorial outcomes, compare published videos with similar format, audience, length, and observation age. Track available opening-retention intervals, average view duration, average percentage viewed, and comments per 1,000 views through supported reports. Keep unavailable metrics absent.

Analyze one feature/change at a time where practical. Matched before/after uploads are observational and can still differ in topic, packaging, traffic, and audience; do not call them a randomized causal experiment. Define sampling and minimum detectable improvement from actual baseline variability before claiming a success rate. Do not use views alone as proof that an edit caused virality.

## 12. Evidence and official references

References checked on 25 October 2026. Recheck API scopes, report compatibility, and platform data policies during implementation.

- [YouTube: Measure key moments for audience retention](https://support.google.com/youtube/answer/9314415?hl=en) — intro measurement, dips/spikes, reviewing compelling moments, and processing delay.
- [YouTube Analytics channel reports: audience retention](https://developers.google.com/youtube/analytics/channel_reports#video-audience-retention-reports) — supported retention dimension, metrics, and single-video filter.
- [YouTube Analytics dimensions](https://developers.google.com/youtube/analytics/dimensions#elapsedVideoTimeRatio) — 100 equally spaced intervals and exclusive interval endpoints.
- [YouTube Analytics metrics](https://developers.google.com/youtube/analytics/metrics#audienceWatchRatio) — retention ratio semantics and comparison metric definitions.
- [YouTube Analytics reports.query](https://developers.google.com/youtube/analytics/reference/reports/query) — request format and read-only authorization requirements.
- [YouTube API developer policies](https://developers.google.com/youtube/terms/developer-policies) — verify storage, refresh, revocation, and deletion requirements before release.
- [Official Qwen3-0.6B model](https://huggingface.co/Qwen/Qwen3-0.6B) — chosen small model and license.
- [Official Qwen3-0.6B GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF) — Q8_0 distribution and local runtime instructions.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) — local inference runtime.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — existing transcription dependency.

The project architecture and delivery order above are engineering proposals. The cited documentation establishes platform behaviour and available tooling; it does not establish a per-feature viral-success percentage.
