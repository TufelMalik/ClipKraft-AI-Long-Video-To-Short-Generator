# Advanced Long-Video Editing — Next Three Features

Status: all three features implemented behind independent opt-in flags.
See `advanced-editing-validation.md` for delivery evidence and remaining verification limits.

Prepared: 25 October 2026.

Branch: `codex/advanced-editing-plan`, created from the current `codex/long-video-editing` branch at commit `5457a10a773832400f84c5d200edae9d2edb6f1f`.

## 1. Scope and priorities

Implement only these next three features. The previously implemented cold-open builder, story-based smart cuts, and YouTube retention feedback are existing dependencies, not new deliverables.

| Priority | Feature | First complete release | Intended benefit |
|---|---|---|---|
| 1 | Audio storytelling | Optional voice cleanup, music/SFX tracks, fades, and voice-driven music ducking | Clearer dialogue and deliberate emphasis without music overpowering speech |
| 2 | Visual explanations | Editable key-point, comparison, process, and callout templates grounded in the transcript | Help viewers understand important or complex points |
| 3 | Context-aware B-roll | Suggest relevant assets from a local library and place approved footage over the main video | Illustrate the spoken point while preserving its narration and context |

These priorities are engineering recommendations. There is no verified per-feature viral-success percentage. No implementation-time estimates are included.

Smart pacing, curiosity/payoff markers, and discussion prompts are outside this plan. Automatic source reordering, speed changes, AI-generated footage, voice cloning, and automatic publishing are also outside this release.

## 2. Non-negotiable implementation rules

1. Preserve all existing shorts and long-form workflows, API defaults, captions, undo/redo, authentication, storage behaviour, and published-export mappings.
2. New features are opt-in and independently gated. Opening an old project must not change its media or rendering behaviour.
3. Reuse the current long-form infrastructure. Do not build a second project store, operation queue, authentication mechanism, or parallel editor application.
4. Use **Qwen3-0.6B through local llama.cpp** for bounded text suggestions. Reuse the existing `EDIT_LLM_*` configuration; no larger model or paid fallback without a new user decision.
5. Qwen3-0.6B is a text model. Asset matching uses verified user metadata and transcript text; the model must not claim it has inspected video/image pixels.
6. AI proposals require preview and explicit approval. Invalid or unavailable suggestions must leave manual controls usable.
7. Rendering must resolve media through server-owned asset IDs. Neither the model nor the browser supplies executable commands, filter graphs, filesystem paths, or arbitrary fetch URLs.
8. The implementation agent may adjust module boundaries and routine technical choices when justified, but must retain scope, compatibility, free-tool constraints, and testable acceptance criteria.

## 3. Verified baseline and integration points

The current branch contains an implemented local long-form workflow. Read these files before modifying the related subsystem:

| Existing file | Observed behaviour | Required extension |
|---|---|---|
| `backend/pipeline/edit_project.py` | Schema v1, source-based segments, protected ranges, cold-open/smart-cut application | Add optional audio/visual composition state with strict validation |
| `backend/pipeline/timeline_map.py` | Half-open integer intervals and occurrence-aware source/output mapping at normal speed | Resolve layer anchors and detect changes after cuts/teaser replacement |
| `backend/pipeline/longform_render.py` | Clean source-aspect cut/concat; preview and export share one path; caption sidecars | Add an optional composition path while retaining the legacy path for unchanged projects |
| `backend/services/edit_project_store.py` | SQLite transactional revisions/history, private records, process workload slots | Store assets, composition snapshots, proposals, and export dependencies |
| `backend/services/edit_llm.py` | Local-only structured Qwen requests and grounded transcript suggestions | Add separately validated visual/B-roll schemas; preserve existing prompts and results |
| `backend/api/edit_projects.py` | Local/loopback guard, cloud gate, revision checks, operations, preview approval | Extend existing capabilities and route patterns with explicit feature allowlists |
| `dashboard/src/components/LongVideoEditor.jsx` | Current editor, revisions, preview, approval, exports, retention display | Add focused Audio, Visuals, and B-roll panels |
| `backend/pipeline/ffmpeg_utils.py` | Shared encoding and existing audio-normalization behaviour | Reuse without changing default behaviour for existing callers |
| `tests/test_longform.py` | Existing logic, API, storage, model, and media checks | Add composition-specific coverage and regression cases |
| `scripts/verify_longform_media.py` | Deterministic media-verification fixture | Add opt-in fixtures for new tracks and overlays |

Important baseline constraints:

- Long-form is currently local self-host only. Cloud routes are deliberately gated pending storage/account integration. Keep that gate; do not advertise these additions as cloud-ready.
- The renderer produces clean video plus SRT/WebVTT caption sidecars. Burned-in long-form caption styling is not currently implemented.
- Current exports hash source segments. New compositions also need asset, audio, overlay, font, and template identity in their manifest/cache keys.
- Current preview approval compares source/role sequences. That comparison alone cannot approve a music track, changed overlay text, or replaced B-roll asset.
- The existing SaaSShorts B-roll generator has external generation dependencies. Do not use it for this free/local feature.
- The existing validation report documents unresolved baseline tests and unverified live Qwen/Google integration. Treat it as historical evidence, not proof that this new work passes.

Read `long-video-editing-setup.md` and `long-video-editing-validation.md` alongside the original implementation plan. Verify current behaviour before changing it.

## 4. Shared foundation: optional composition tracks

### 4.1 Versioned project data

Introduce schema v2 only when a user first saves composition features. Read v1 projects with empty tracks and disabled audio processing. Do not eagerly rewrite old projects or apply defaults that change their export.

Illustrative additions to a project:

```json
{
  "schema_version": 2,
  "composition": {
    "version": 1,
    "voice": {"cleanup": "off", "gain_db": 0},
    "audio_tracks": [
      {
        "id": "music_1",
        "asset_id": "asset_music",
        "asset_version": 1,
        "asset_in_ms": 0,
        "anchor": {"type": "output", "start_ms": 0, "end_ms": 120000},
        "gain_db": -18,
        "duck_under_voice": true,
        "fade_in_ms": 1000,
        "fade_out_ms": 1500,
        "loop": false
      }
    ],
    "visual_layers": [
      {
        "id": "visual_1",
        "kind": "key_point",
        "template_version": 1,
        "anchor": {
          "type": "occurrence",
          "segment_id": "body_occurrence",
          "source_start_ms": 45000,
          "source_end_ms": 51000
        },
        "text": "User-approved wording",
        "position": "upper_third",
        "enabled": true
      }
    ]
  }
}
```

The values above are examples, not recommended music levels or universal display timings. Settings must be user-adjustable within validated bounds.

Layer kinds are a closed enum: key point, comparison, process, callout, and B-roll. Audio track kinds distinguish music and SFX. Reference asset versions/checksums, not mutable file names. Validate text lengths, gain/fade limits, track count, dimensions, integer times, source bounds, asset type, and supported placement presets server-side.

### 4.2 Anchoring and edits after composition

Use two explicit anchor modes:

- **Occurrence anchor:** source range plus the specific body/teaser segment occurrence. Appropriate for content-linked visuals and B-roll. A teaser repeating the same source words must not receive the same layer automatically.
- **Output anchor:** a range on a particular draft output timeline. Appropriate for manually placed music/SFX. Store the base revision used to place it.

All EDL mutations must run a composition-reconciliation step. This includes manual trims, cold-open replacement, smart-cut application, undo, and restore.

When a segment splits, maintain an explicit old-to-new occurrence lineage. Rebase an anchor only if its complete content range survives unambiguously. If a layer crosses a removed range, loses its target, or becomes ambiguous, mark it `needs_review`; never silently move it to unrelated content. Output-anchored events affected by duration changes also need review unless the user selected an explicit ripple behaviour.

Block final export with an actionable list of unresolved enabled layers. Let the user re-anchor or disable them. Restoring a revision restores the complete EDL and composition together, then checks referenced asset availability.

### 4.3 Asset library and lifecycle

Start with user-uploaded local images, clips, music, and sound effects. No stock-site account or paid API is required.

Asset metadata includes ID, project/library owner, media type, immutable content checksum, duration, dimensions, codec, audio presence, tags, description, language, source label, and user-entered usage/license notes. Unknown rights are not labelled free merely because a file can be downloaded.

- Accept a deliberately small raster/video/audio format allowlist. Reject active HTML/SVG uploads in the first release.
- Probe actual file content, validate dimensions/duration/size, bound decoded image pixels, and create lightweight thumbnails/proxies.
- Store uploaded assets outside public static roots. Serve them through the existing protected/ticketed pattern, adapted for asset access.
- Never accept a client filesystem path or arbitrary URL as an asset import.
- Replacing an asset creates a new version; existing previews/exports retain their original dependency identity.
- Block destructive deletion while assets are referenced by active drafts/history, or require a deliberate detach workflow. Shared assets need reference-aware cleanup.
- Apply bounded storage policies and show expiration/missing-asset states. Preserve export manifests after media expiry.

### 4.4 Preview, approval, and export identity

Create a canonical composition hash covering EDL, transcript version, audio controls, asset checksums/versions, layer text/layout, font files, template versions, and renderer version. Keep `edl_hash` for backward compatibility and add `composition_hash`.

An approved preview must match project ID, expected revision, selected proposal IDs, and the complete proposed composition hash. Changing a music gain, template text, asset crop, or placement invalidates that approval. The backend verifies these values; frontend disabled buttons alone are insufficient.

Preview and export compile the same canonical composition. A bounded preview may render a window, but must preserve global-time anchors, track phase, fade state, and ducking pre-roll. Store its covered ranges. If reliable window equivalence is not implemented yet, retain full-composition previews rather than approximate the result silently.

### 4.5 Render architecture and no-op compatibility

Keep the current renderer for v1/empty-composition projects. Use a new optional compositor only when enabled layers or audio processing are present.

Deterministic stage order:

1. Resolve and validate source EDL, asset dependencies, and layer anchors.
2. Build source-aspect base video and dialogue timeline.
3. Apply B-roll video replacements/overlays while keeping main narration by default.
4. Composite explanation layers in deterministic z-order.
5. Build dialogue/music/SFX mix, apply fades/ducking, and finish audio once.
6. Encode and validate final media; emit mapped caption sidecars and an immutable manifest.

Avoid repeated lossy video encodes where practical; bound intermediate storage and peak memory. Use existing subprocess cancellation, admission slots, deadlines, and cleanup. Failures preserve the previous successful export.

The current audio helper may already normalize segment audio. Audit its call sites before adding a final mix stage. Use an explicit compositor-only raw/intermediate encoding option so normalization is not accidentally applied per segment and again after mixing; preserve old helper defaults.

## 5. Priority 1 — Audio storytelling

### User flow

Open Audio → compare original voice with optional cleanup → add local music/SFX → set placement, level, fades, and ducking → preview the relevant sections → apply/save → export.

Show separate controls for dialogue and background tracks. Provide mute/solo and a bypass comparison. Muting for audition must not change export settings unless explicitly saved.

### Implementation

1. Probe the source audio layout and map the chosen dialogue stream consistently across EDL cuts. Handle mono, stereo, and no-audio input explicitly.
2. Offer conservative optional noise reduction using FFmpeg `afftdn`; default it off. Allow gain adjustment without equating gain with noise cleanup.
3. Load each music/SFX asset using an in-point, timeline anchor, gain envelope, fade controls, and explicit looping policy. Do not stretch a short music clip or repeat an SFX by default.
4. Use the clean dialogue bus as the detector for `sidechaincompress` or a deterministic speech-derived gain envelope. Duck the music bus; never feed the mixed soundtrack back into its own detector.
5. Mix through `amix` with explicit duration, sample-rate/channel conversion, and gain semantics. Avoid implicit normalization that changes dialogue level when tracks enter/leave.
6. Evaluate integrated loudness and true peak on the final encoded output. Keep finishing settings project-specific; do not change shared shorts loudness constants.
7. For music loops, validate loop boundaries and provide short fades where needed. For intentional silence, allow track gaps without filling them automatically.
8. Expose a few editable presets for restrained background, emphasis, and no music. Presets contain transparent audio settings, not unsupported emotion detection.

Qwen is not required for this feature's first release. Manual mood selection and deterministic audio processing provide a complete useful workflow. Automatic music composition, stem separation, and invented emotional timing are deferred.

### Edge cases

- No dialogue: disable voice-driven ducking with a clear reason; allow manual soundtrack placement.
- Source already includes background music: ordinary denoising cannot isolate it. Do not promise voice-only cleanup.
- Music shorter than the selected range: require trim/loop choice.
- Multiple tracks: cap simultaneous tracks and total decode load; reject invalid clipping/gain settings.
- Preview starts mid-track: preserve asset phase and detector history so audition matches export.

### Acceptance criteria

- Disabled audio features retain the existing audio path and defaults.
- Speech remains understandable over the selected music; gain reduction is observable during speech and release behaves predictably.
- Export duration and captions stay aligned with the original EDL.
- No unexplained silence, abrupt truncated fades, or clipping introduced in reviewed fixtures.
- Each saved audio change participates in revision history, preview identity, and undo/redo.

## 6. Priority 2 — Visual explanations

### First-release templates

| Template | Required user-visible content | Validation |
|---|---|---|
| Key point | Short title and one supporting line | Length/layout bounds; grounded source sentence IDs for AI text |
| Comparison | Two labelled sides with matching fields | No invented numerical comparison or missing units |
| Process | A small ordered list of steps | Preserve approved order; explicit limit on number/length of steps |
| Callout | Highlight box/arrow and label | Normalized coordinates inside frame; manual static placement first |

Provide manual authoring for all templates. AI assistance is optional and drafts editable text; it does not place unchecked facts into the video.

### Suggestion and rendering pipeline

1. User selects a transcript passage or asks for suggestions from a bounded section.
2. Qwen3-0.6B returns template type, existing sentence IDs, draft wording, and a brief reason in a strict schema.
3. Resolve sentence IDs server-side. Validate that numerical values, names, and quoted claims are present in the source; flag paraphrases for review. On uncertain grounding, return no suggestion or a manual draft.
4. Render fixed template geometry with Pillow and local font files, then composite with FFmpeg. Validate font shaping for Hindi/Devanagari using the actual installed text-layout support; do not assume basic font presence guarantees correct shaping.
5. Use bounded opacity/translation transitions with deterministic timing. Avoid unrequested flashing or continuous decorative motion.
6. Support source-aspect landscape/portrait rendering with normalized safe regions. Default explanation layers away from the lower caption band.
7. Expose timing, text, placement preset, size, and theme controls. Preview the exact rasterized output so browser typography cannot hide render differences.
8. Persist the chosen template/font versions in export dependencies.

Current long-form captions are sidecars and native player placement can vary. Reserve caption space, test simultaneous visibility, and provide manual repositioning. Do not claim collision-free placement against every external player's subtitles or pre-burned source captions.

### Tracked callout extension within this feature

After static templates pass, optionally add user-initialized OpenCV tracking. The user selects the object/region on a frame; the tracker produces bounded keyframes. On tracking loss, stop/fade and mark the range for review rather than follow a different object. Scene cuts invalidate tracking. Cache tracking against source checksum, occurrence, and range.

Tracking is an enhancement, not a prerequisite for shipping the four static templates. It must remain independently gated and must not require a larger vision model.

### Acceptance criteria

- All four templates can be manually created, edited, previewed, applied, removed, and restored.
- AI proposals resolve to actual transcript passages and remain editable before approval.
- Hindi/Hinglish/English text renders without broken glyphs, overflow, or cropped lines in tested aspect ratios.
- Display timing and positioning agree between preview and export.
- Template text does not silently change when the model, font, or source transcript changes later.

## 7. Priority 3 — Context-aware B-roll

### First-release boundary

Use a local asset library of user-owned or appropriately licensed clips, screenshots, and images. Matching is text-based using tags/descriptions, with manual visual approval. Do not download random search results or route through the paid SaaSShorts generation pipeline.

### User flow

Import/tag assets → select a spoken passage → **Suggest visuals** → review up to three candidates with matching reasons → choose clip/image and crop/in-point → preview with the original narration → apply.

Allow manual search and placement even when the model is unavailable. A no-match result is valid.

### Retrieval and placement pipeline

1. Index asset tags, descriptions, source labels, and optional manually reviewed transcripts of asset audio. Video speech metadata does not establish what its frames depict.
2. Use a deterministic local text search to retrieve a small shortlist. SQLite FTS5 is a possible implementation after probing availability; provide a basic token-search fallback. Keep a reviewed bilingual tag/alias vocabulary for Hindi/Hinglish matching.
3. Give Qwen3-0.6B only the selected passage and shortlisted metadata. Request ranked asset IDs, matching rationale, and whether the metadata is sufficient.
4. Validate returned IDs and availability. Never let the model return or choose arbitrary paths, URLs, or unsupported factual claims about the asset.
5. User selects the visual and source in-point. Derive the target range from selected transcript words and the occurrence map. The preview must show the proposed visual in context.
6. Default to video-only B-roll with the original main narration continuing. Replacement audio is off and requires a separate explicit track choice.
7. Provide full-frame cover and contained-inset modes. Use explicit fit/contain/crop settings; show the crop in preview. Do not auto-crop an important screenshot region based on text-only guesses.
8. For video assets too short for the target, offer a shorter placement or another asset. Loop/freeze is a user-selected option, never an invisible default.
9. Images may hold for the approved duration. Optional gentle motion is a separately visible setting.
10. Preserve main-video duration. In this release, B-roll covers existing time rather than inserting extra runtime.

### Overlaps and source changes

Allow one full-frame B-roll cover per video time span in the first version; reject conflicting covers with a clear range indication. Explanation layers can appear above B-roll according to the shared z-order, with a preview warning for occupied regions.

If later story cuts remove or split the target passage, mark the B-roll placement for review through the common anchor reconciler. Never retarget an illustration to unrelated dialogue. Replacing an asset invalidates its pending preview approval while preserving old export manifests.

### Acceptance criteria

- Manual and metadata-assisted selection both work entirely with local assets.
- Every selected ID belongs to the accessible library and is fingerprint-verified at render time.
- Main narration and total duration remain unchanged by default B-roll placement.
- Asset in-points, cropping, still duration, and optional loop/freeze choices match preview and export.
- No-match, missing-asset, wrong-format, and changed-source cases have actionable outcomes.

## 8. API and module plan

Proposed modules; choose equivalent small modules if existing code makes a different boundary cleaner:

| File | Responsibility |
|---|---|
| `backend/pipeline/composition.py` | Schema v2, track validation, canonical hashing, old-project defaults |
| `backend/pipeline/layer_anchors.py` | Occurrence/output anchors and reconciliation after EDL changes |
| `backend/pipeline/audio_mix.py` | Dialogue/music/SFX graph, fades, ducking, final-output measurement |
| `backend/pipeline/visual_templates.py` | Deterministic template layout, text shaping, render assets |
| `backend/pipeline/broll.py` | Placement, fit/crop, asset-time mapping and cover validation |
| `backend/pipeline/longform_compositor.py` | Optional track compositor and dependency-aware manifests |
| `backend/services/edit_assets.py` | Private ingestion, metadata, checksums, proxies, reference-aware cleanup |
| `backend/services/broll_search.py` | Local metadata search and optional grounded reranking |
| `backend/services/edit_llm.py` | Add dedicated visual/B-roll response schemas without modifying old ones |
| `backend/api/edit_assets.py` | Asset routes using the existing guard/admission/access patterns |
| `dashboard/src/components/longform/AudioPanel.jsx` | Audio controls and audition |
| `dashboard/src/components/longform/VisualsPanel.jsx` | Templates, grounded text review and positioning |
| `dashboard/src/components/longform/BrollPanel.jsx` | Library, matching and approved placement |

Extend the existing capabilities endpoint to return supported features, audio filters, template IDs, upload limits, and text-shaping capability. Capabilities reflect server configuration and installed support, not just frontend flags.

Suggested new API routes:

```text
POST   /api/edit-assets                               Upload and validate local asset
GET    /api/edit-assets                               List/search permitted asset metadata
PATCH  /api/edit-assets/{asset_id}                    Update tags/description with version check
DELETE /api/edit-assets/{asset_id}                    Delete only after reference checks
POST   /api/edit-assets/{asset_id}/access             Issue scoped preview-media access
GET    /api/edit-assets/{asset_id}/{media_kind}       Serve allowed media using scoped access
POST   /api/edit-projects/{id}/visuals/analyze        Generate grounded template proposals
POST   /api/edit-projects/{id}/broll/analyze          Retrieve/rank local asset candidates
POST   /api/edit-projects/{id}/composition/preview    Preview proposed composition snapshot
POST   /api/edit-projects/{id}/composition/apply      Apply preview-approved composition
```

Reuse current project GET, restore, export, operation status, and cancellation endpoints. Extend PATCH with explicitly validated composition fields if needed for manual drafts; never use unchecked dictionary merging.

Mutation requests include `expected_revision`. Analysis records include project/transcript revision, relevant asset metadata versions, and prompt version. Apply requests reference the immutable draft/preview identity and explicit approval. Register specific routes safely alongside the existing `/{feature}/analyze` and `/{feature}/apply` handlers; avoid route shadowing and accidental acceptance of unknown feature names.

Proposed flags, default false:

```dotenv
LONGFORM_AUDIO_ENABLED=false
LONGFORM_VISUALS_ENABLED=false
LONGFORM_BROLL_ENABLED=false
LONGFORM_TRACKED_CALLOUTS_ENABLED=false
```

Keep existing `LONGFORM_EDITING_ENABLED`, export, local model, and self-host/cloud gates intact. Disabling a feature blocks new changes but preserves saved records. If an enabled saved layer cannot be rendered with current capabilities, report it; do not silently omit it from export.

## 9. Free/open-source tooling

| Dependency | Usage | Decision |
|---|---|---|
| Existing FFmpeg/ffprobe | Audio processing, composition, media validation | Required; detected locally with `afftdn`, `sidechaincompress`, `amix`, `afade`, `loudnorm`, `ebur128`, and `overlay` support |
| Existing Pillow | Static templates, image validation, thumbnails | Required; verify Hindi shaping support and bundled font licenses |
| Existing faster-whisper | Source word timestamps; optional asset-audio transcription | Reuse; avoid repeated transcription |
| Existing Qwen3-0.6B + llama.cpp adapter | Optional visual text suggestions and B-roll metadata ranking | Required only for AI assistance; no model upgrade or paid fallback |
| SQLite / optional FTS5 | Existing store and local asset metadata search | Reuse; check FTS5 availability |
| OpenCV | Optional manually initialized callout tracking | Add/pin only for tracking; validate compatibility with existing vision dependencies |
| PySceneDetect | Optional cut boundaries for tracked-callout invalidation | Reuse installed version if needed; do not infer semantic relevance from scene cuts |

Music/SFX/B-roll media are separate from software licenses. Start with user-supplied assets and recorded usage notes; do not bundle media whose redistribution permission is unknown. Local compute/storage costs remain even when software is free.

## 10. Tests and acceptance gates

### Regression protection

- Compare representative existing shorts and v1 long-form paths before/after; no-op projects use the old render path and defaults.
- Preserve cold-open preview/apply, protected smart cuts, undo/redo, source leases, private media tickets, operations, and YouTube publication linkage.
- Old manifests remain readable; new composition edits never rewrite an already published export's identity or time map.
- Existing feature flags remain off by default; cloud remains gated.
- Reproduce known baseline test failures separately. Do not mask them or call the full suite green when it is not.

### Unit/API coverage

- v1/v2 read compatibility, schema rejection, complete revision restore, composition hash stability and invalidation.
- Duplicate teaser occurrences, split segments, removed targets, stale output anchors, and unresolved-layer export rejection.
- Asset type/size checks, private path handling, asset-reference deletion, changed checksums, stale metadata proposals, and access tickets.
- Preview tampering: text, gain, crop, asset version, font/template, or track range changed after approval.
- Missing Qwen, malformed schemas, hallucinated sentence/asset IDs, context overflow, and manual fallback.
- Concurrent mutations, interruption, cancellation, resource limits, orphan-temp cleanup, and preservation of previous exports.

### Real media fixtures

1. **Audio:** dialogue plus a steady music bed; speech gaps; no-audio source; multiple SFX; music shorter than target; source containing existing music. Inspect the ducking envelope, decoded loudness/true peak, joins, and A/V sync.
2. **Visuals:** Hindi/English/Hinglish text, long words, comparisons with units, landscape and portrait clips, existing burned captions, and selectable sidecar captions. Inspect rendered frames at each layer boundary.
3. **B-roll:** clips with different frame rates/resolutions, portrait over landscape, screenshot inset, still image, silent clip, short asset, and an asset containing audio that must remain muted.
4. **Combined:** teaser + smart cut + music + explanation + B-roll; undo the cut and replace the teaser; ensure dependent layers resolve or become review-required correctly.
5. **Long duration:** representative user-owned footage at intended output resolution; measure memory, temporary disk usage, cancellation responsiveness, and export completion. Tiny synthetic fixtures alone do not establish capacity.

Preview/export parity checks compare the same intervals, including fade-in/out, mid-track music phase, overlay timing, crop, narration, and captions. For audio loudness, inspect decoded output after the final codec step rather than only the pre-encode filter result.

Run targeted Python tests, existing long-form/recut/LLM regressions, then required repository checks. Run dashboard build/lint and browser interaction checks for the new panels. Record exact commands, results, remaining baseline failures, and inspected media in a validation document when implementation is delivered.

## 11. Delivery order and completion criteria

| Phase | Deliverable | Exit gate |
|---|---|---|
| A | Optional composition schema, anchors, asset store, full-composition preview identity | Old exports unchanged; new tracks persist/restore safely; stale approval rejected |
| B | Audio storytelling | Local soundtrack placement, cleanup bypass, fades, ducking, and validated mixed export |
| C | Visual explanations | All four manual templates plus optional grounded AI proposals; correct multilingual render |
| D | Context-aware B-roll | Local search/ranking, narration-preserving placement, crop/in-point controls, working export |
| E | Cross-feature verification and documentation | Combined media checks and regression gates pass or remaining baseline failures are explicitly evidenced |

Publish each verified capability behind its own flag. A missing local model must not block deterministic audio, manual visuals, or manual B-roll. Leave tracked callouts disabled until their separate tracking-loss and scene-cut tests pass.

Completion means usable editor controls, validated backend behaviour, a playable composed export, preserved existing functionality, setup documentation, and recorded verification. Placeholder panels, mocked generation, or renderer-only demonstrations do not complete a feature.

Rollback disables new changes and restores a compatible deployment with backed-up data. Before a schema-v2 release, define downgrade behaviour: older code must not overwrite unknown composition fields or render a v2 project as if its tracks never existed. Keep immutable exports available even when editing capabilities are disabled.

## 12. Research and verification notes

- [Qwen3-0.6B official model card](https://huggingface.co/Qwen/Qwen3-0.6B): selected text model, Apache-2.0 distribution. Editorial suitability remains a local evaluation requirement.
- [Pillow official project](https://python-pillow.org/): free/open-source image processing used for deterministic visual assets.
- [PySceneDetect official documentation](https://www.scenedetect.com/): shot-change detection; optional tracking-boundary aid.
- FFmpeg capabilities listed above were checked against the installed executable using `ffmpeg -hide_banner -filters`. Online filter documentation could not be fetched in this session. Verify exact filter options with the installed build's `ffmpeg -h filter=<name>` before implementing graphs.
- Existing implementation evidence: `long-video-editing-setup.md`, `long-video-editing-validation.md`, and the inspected source files at the base commit named above.

These references support tool capabilities. The plan's feature priority, UI flows, and implementation boundaries are proposed engineering decisions; they do not assert a measured engagement uplift.
