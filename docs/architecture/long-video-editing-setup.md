# Local long-form editing

The editor is implemented as a separate opt-in self-host surface. Existing shorts routes, limits,
picker model, rendering defaults, caption styles and clip undo/redo are unchanged. Cloud deployments
return `longform_cloud_storage_unavailable`: transactional cloud records, account deletion,
storage adapters, entitlement and watermark delivery need a separate integration before enablement.
No cloud migration or cloud feature availability is claimed by this implementation.

## Enable and open

Install the normal application dependencies and FFmpeg/ffprobe. For YouTube support also run
`pip install -r requirements-longform.txt`. Set `LONGFORM_EDITING_ENABLED=true` in the server environment
and restart. The **Edit full video** button appears in the main dashboard. Access is restricted to
loopback clients and loopback Host/Origin names. Run the backend on `127.0.0.1`; do not place these
routes behind a remote proxy which makes remote clients appear local. Docker/remote hosting is not
supported for this first local release.

Set `LONGFORM_LOCAL_TOKEN` to a random password for local session protection. The panel asks for it;
it is held only in React memory and attached as `X-Longform-Token`. OAuth requires this setting.
The local model and Google credentials never enter the browser. Temporary media tickets allow
normal browser range requests without embedding the session password in URLs.

Create from **Use current source** when an existing job retains its source and transcript, or
**Upload full video** without generating shorts. New uploads run only probe and transcription,
using the existing ASR backend, host slot and model-release contract in a cancellable child process.
URLs can use an existing owned ingested job; a new URL-only ingest entry is not included.

New projects retain source aspect ratio, speed 1 and no outro. Manual source ranges and protected
sections work without the local language model. Undo/redo restores complete server snapshots as
new revision numbers. The UI undo/redo navigation stack lasts for the current panel session;
the server history remains persisted. A concurrent save returns `revision_conflict`; reload the
saved project before retrying. Suggestions become stale after any revision change.

## Local Qwen

Use the official [Qwen3-0.6B GGUF Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF)
with [llama.cpp](https://github.com/ggml-org/llama.cpp). For a llama-server build:

```text
llama-server -hf Qwen/Qwen3-0.6B-GGUF:Q8_0 --alias qwen3-0.6b --host 127.0.0.1 --port 8080 --ctx-size 8192 --jinja --chat-template-kwargs "{\"enable_thinking\":false}"
```

Check your installed binary's `--help` for its flag spelling. Configure `EDIT_LLM_BASE_URL`,
`EDIT_LLM_MODEL` and `EDIT_LLM_CONTEXT_TOKENS` to match the server. The adapter sends
`chat_template_kwargs.enable_thinking=false` and `/no_think`, requests JSON-schema output, validates
Pydantic schemas, and retries malformed JSON once. Unsupported structured mode fails visibly;
there is no paid or larger-model fallback and no change to `LLM_*` shorts settings.

Input is budgeted conservatively by UTF-8 bytes, with output/instruction reserve. Oversized
individual units are omitted rather than truncated. Punctuation-terminated sentence IDs ground
all candidate ranges; Hindi/Hinglish text is preserved. Cold opens consider the entire transcript
in bounded batches and reduce a shortlist. Smart cuts analyze current body occurrences with
adjacent context; protected sections, teaser overlaps and deleted repetition evidence are rejected
in code. A model judgment cannot guarantee that removing a complete sentence preserves meaning.

Enable `COLD_OPEN_ENABLED` / `SMART_CUTS_ENABLED` independently only after reviewing your footage.
Analyze → select → preview → play/review → **Approve and apply selected**. The server requires an
immutable completed preview of the same revision, feature and selected IDs plus explicit approval.
The browser cannot prove editorial attention; the approval action is the user's attestation.
Replacing a teaser preserves its original body occurrence and never stacks multiple teasers.
Preview current edit supplies the before comparison. Approved cuts apply as one undoable revision.

## Rendering, storage and recovery

`LONGFORM_EXPORT_ENABLED` is a separate default-off gate. The initial configurable ceilings are
2 hours, 256 segments, 4 GiB source, 8 GiB temporary parts and a 30-minute render deadline. They are
engineering safety ceilings, **not measured production capacity or recommended release caps**.
Preview uses the full proposed EDL, including joins, through the same renderer as export. No crops,
speed changes, crossfades or reconstructed audio are added. Captioned source pixels are preserved.
New captions use the shared output map and are delivered as selectable WebVTT and downloadable SRT;
burned-in caption styling for long-form exports is not implemented. Existing shorts styling is untouched.

SQLite records live in `.longform/<output-directory-name>/projects.sqlite3` beside the media root,
outside `/videos`. Transactions serialize saves and host-wide workload admission. One long-form
workload runs per host; a busy submission returns 429 instead of growing an unbounded queue.
This also serializes local-model requests. Rendering uses private temporary directories, clean
source media and existing encoding helpers. Cancellation kills the child, removes temporary files,
and releases the slot. Completed export manifests retain revision, fingerprint, EDL hash and time map.
Failed exports never replace a successful artifact. Browser playback uses expiring scoped media tickets.

Active source leases are bounded by the configured lease time **and existing job retention**.
They protect active long-form files from the existing sweeps until expiry, then ordinary retention
and disk caps apply. The project view exposes lease expiry. Manifests survive media expiry; playback
returns `artifact_expired`, while source-dependent operations return `source_missing`. Local metadata
is not automatically deleted with media. Back up/protect the private directory and encryption key;
apply an owner-only ACL on Windows. Use a distinct output-directory basename per independent store.

Operation manifests expose status, cancellation and redacted errors. Shutdown cancels live work;
dead-worker operations become `interrupted` when queried. Retry explicitly; work is not silently
resumed. Polling and mutations preserve revision checks across multiple workers. Disabling flags
blocks new work while retaining readable projects and exports. Disable local-model features
individually when unavailable; local editing and exporting continue.

## YouTube connection and reports

Enable YouTube Analytics and Data APIs in a Google project. Configure a web OAuth client with the
**exact** `YOUTUBE_REDIRECT_URI` (loopback `/api/youtube-analytics/callback`), client ID and secret.
Generate `YOUTUBE_CREDENTIAL_KEY` using `Fernet.generate_key()` from cryptography; keep it separate
from the database. Set `LONGFORM_LOCAL_TOKEN` and `YOUTUBE_RETENTION_ENABLED=true`. Add the intended
Google account as a test user when the consent application is in testing. Public distribution and
Google verification remain external setup requirements.

**Connect YouTube read access** opens Google consent for `yt-analytics.readonly` and
`youtube.readonly`. One-time state, expiry, S256 PKCE, granted scopes and channel IDs are checked.
Refresh/access tokens are encrypted server-side. A publication must belong to the connected channel
and match a completed export's duration; the user must separately confirm exact unmodified identity.
Duration alone is not proof. Externally edited publications need a new matching export; custom alignment
is not provided. No publishing permissions are requested.

Refresh retention on demand for a selected publication and date range. Reports use the official
[audience-retention report](https://developers.google.com/youtube/analytics/channel_reports#video-audience-retention-reports)
and [elapsedVideoTimeRatio](https://developers.google.com/youtube/analytics/dimensions#elapsedVideoTimeRatio)
exclusive interval endpoints. Sparse intervals retain their actual 1% source interval, rather than
bridging missing data. A two-hour publication has 72-second buckets. Ratios above 100% are preserved;
missing metrics remain absent. No exact 30-second metric or causal/viral prediction is manufactured.
The accessible table seeks the original export and shows source occurrence IDs. Dips/peaks are
labelled heuristic markers based on a fixed .15 watch-ratio prominence and nearby buckets.

Cache identity includes the publication's connection, video and immutable export, with query dates
stored in the report. A refresh replaces that publication's cached date range. Cached reads expire
after `YOUTUBE_CACHE_TTL_SECONDS` (capped at 30 days). Stale raw reports are pruned on editor requests.
Disconnect attempts Google revocation and deletes local credentials, links, OAuth state and reports
even if remote revocation fails; retry revocation in the Google account if necessary. There is no
background monitoring. Review [Google's developer policies](https://developers.google.com/youtube/terms/developer-policies)
before distribution; operator backups and offline server data erasure require operational handling.

## Verification and known release gates

`tests/test_longform.py` covers EDL bounds, duplicated time maps, Hindi captions, overlapping cuts,
protection, stale revisions, concurrent saves, failed-save rollback, preview approval, cancellation,
resource admission, OAuth state/PKCE/scope checks, foreign publications, immutable export links,
report schema/missing data/values above 1, local-only model configuration and malformed/unknown IDs.
FFmpeg integration verifies visible color order, audio presence, duration, source aspect ratio,
caption timestamps, missing-audio inputs and cleanup.

Run `python -X utf8 -m pytest tests/ --basetemp .cache/pytest-run -q`, then `npm run lint` and
`npm run build` in `dashboard`. Windows sandboxed Python needs local socket access for asyncio.
The full baseline has Windows-specific failures (stdio path moved, font availability, POSIX flock,
and static-file restoration) documented in the validation report. They are not long-form regressions.

No llama.cpp binary/model artifact or configured Google OAuth connection was available during
implementation. Actual Qwen non-thinking behavior, reviewed English/Hindi/Hinglish editorial quality,
real authorized retention, representative hour-scale speech/caption playback and peak CPU/GPU/RSS/disk
capacity remain release gates. Synthetic and mocked tests do not establish these results. All new
feature flags stay off by default. Cloud delivery, styled burned captions, a durable UI history
navigator, source restore uploads into an existing project and manual publication alignment remain limitations.
