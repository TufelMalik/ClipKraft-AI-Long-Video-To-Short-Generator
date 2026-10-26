import os
import sys
import json
import time
import subprocess
import asyncio
from typing import List, Dict, Any, Optional

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_CURR_DIR))
_PIPELINE_DIR = os.path.join(os.path.dirname(_CURR_DIR), "pipeline")
for _p in [_REPO_ROOT, _PIPELINE_DIR, _CURR_DIR]:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_OUTRO = r"C:\Youtube Channels\Videos\Temp Videos\OUTRO_D_3.5s.mp4"

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def _render_manual_clips_job(job_id: str, src_video: str, clips_config: List[Dict[str, Any]],
                         output_dir: str, speed: float = 1.20, outro_path: str = DEFAULT_OUTRO,
                         jobs_dict: dict = None, output_format: str = 'vertical'):
    """
    Runs only in the isolated rendering process, on its main thread.
    """
    from manual_clip_pipeline import process_single_clip, parse_time_str
    job = jobs_dict.get(job_id) if jobs_dict else None
    
    def log(msg: str):
        safe_print(f"[{job_id}] {msg}")
        if job and 'logs' in job:
            job['logs'].append(msg)

    log(f"🚀 Starting Manual Clip & Edit Job {job_id} with {len(clips_config)} clips...")
    if job:
        job['status'] = 'processing'

    os.makedirs(output_dir, exist_ok=True)
    temp_work_dir = os.path.join(output_dir, "temp_work")
    os.makedirs(temp_work_dir, exist_ok=True)

    generated_clips = []
    all_segments = []
    main_language = "en"

    for idx, c in enumerate(clips_config, 1):
        clip_id = str(idx)
        c["id"] = clip_id
        hook_text = c.get("hook", f"CLIP #{idx}")
        start_s = parse_time_str(c.get("start", 0))
        end_s = parse_time_str(c.get("end", 0))

        if end_s <= start_s:
            log(f"⚠️ Skipping clip {idx}: Invalid time range ({start_s}s -> {end_s}s)")
            continue

        gen_id = int(time.time())
        clean_filename = f"manual_clip_{clip_id}.mp4"
        subtitled_filename = f"subtitled_{gen_id}_manual_clip_{clip_id}.mp4"
        thumb_filename = f"manual_clip_{clip_id}.jpg"

        clean_video_path = os.path.join(output_dir, clean_filename)
        subtitled_video_path = os.path.join(output_dir, subtitled_filename)
        final_thumb_path = os.path.join(output_dir, thumb_filename)

        log(f"▶️ Processing Clip {idx}/{len(clips_config)}: '{hook_text}'")

        try:
            words, full_text, language = process_single_clip(
                src_video=src_video,
                clip_data=c,
                work_dir=temp_work_dir,
                clean_out_video=clean_video_path,
                subtitled_out_video=subtitled_video_path,
                speed=speed,
                outro_path=outro_path,
                log_fn=log,
                output_format=output_format,
            )
            if language:
                main_language = language

            # Generate thumbnail preview frame at 1.5s from subtitled video
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", "1.5",
                "-i", subtitled_video_path,
                "-vframes", "1",
                "-q:v", "2",
                final_thumb_path
            ], check=False)

            dur_content = (end_s - start_s) / speed
            dur_total = dur_content + (3.5 if os.path.exists(outro_path) else 0.0)

            # Build transcript segment for this clip (scaled by speed so it syncs with video!)
            clip_segment = {
                "id": idx - 1,
                "start": round(start_s, 3),
                "end": round(start_s + dur_content, 3),
                "text": full_text,
                "words": [
                    {
                        "word": (" " + w["word"]) if not w.get("raw_word", "").startswith(" ") else w["raw_word"],
                        "start": round(start_s + (w["start"] / speed), 3),
                        "end": round(start_s + (w["end"] / speed), 3),
                        "probability": w.get("probability", 0.95)
                    }
                    for w in words
                ]
            }
            all_segments.append(clip_segment)

            clip_entry = {
                "start": round(start_s, 3),
                "end": round(start_s + dur_content, 3),
                "original_start": round(start_s, 3),
                "original_end": round(end_s, 3),
                "speed": speed,
                "output_format": output_format,
                "hook": hook_text,
                "title": hook_text,
                "video_title_for_youtube_short": hook_text,
                "video_description_for_instagram": f"{hook_text} #shorts #viral",
                "video_description_for_tiktok": f"{hook_text} #shorts #viral",
                "why": f"Manual clip ({speed}x speed, karaoke captions & outro)",
                "score": 95,
                "predicted_score": 95,
                "viral_hook_text": hook_text,
                "video_url": f"/videos/{job_id}/{subtitled_filename}",
                "thumbnail_url": f"/videos/{job_id}/{thumb_filename}",
                "duration": round(dur_total, 2)
            }
            generated_clips.append(clip_entry)

            # Update ready_files in job dict so frontend picks it up live!
            if job:
                if 'ready_files' not in job:
                    job['ready_files'] = {}
                job['ready_files'][idx - 1] = subtitled_filename
                job['result'] = {'clips': list(generated_clips), 'cost_analysis': None}

        except Exception as e:
            log(f"❌ Error rendering clip {idx}: {e}")
            import traceback
            log(traceback.format_exc())

    # Write {job_id}_metadata.json with complete transcript object
    metadata_path = os.path.join(output_dir, f"{job_id}_metadata.json")
    metadata_data = {
        "job_id": job_id,
        "shorts": generated_clips,
        "transcript": {
            "text": " ".join(s["text"] for s in all_segments),
            "language": main_language,
            "segments": all_segments
        },
        "cost_analysis": {
            "total_clips": len(generated_clips),
            "mode": "manual_edit",
            "total_cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0
        }
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_data, f, indent=2)

    if job:
        job['status'] = 'completed' if generated_clips else 'failed'
        job['transcript'] = metadata_data["transcript"]
        job['result'] = {'clips': generated_clips, 'cost_analysis': metadata_data["cost_analysis"]}

    log(f"🎉 Completed Manual Clip Job! Generated {len(generated_clips)} shorts.")


_STATE_PREFIX = "__OPENSHORTS_MANUAL_STATE__"
_STATE_FIELDS = ("status", "result", "ready_files", "transcript", "error")


def _atomic_json(path, data):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False)
    os.replace(temporary, path)


class _EventJob(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if key in _STATE_FIELDS:
            state = {name: self[name] for name in _STATE_FIELDS if name in self}
            print(_STATE_PREFIX + json.dumps(state, ensure_ascii=False), flush=True)


def run_manual_clips_job(job_id: str, src_video: str, clips_config: List[Dict[str, Any]],
                         output_dir: str, speed: float = 1.20, outro_path: str = DEFAULT_OUTRO,
                         jobs_dict: dict = None, output_format: str = 'vertical'):
    """Supervise native ML rendering out of process; never import it in the API.

    Windows native access violations bypass Python exceptions. Keeping Torch,
    MediaPipe, OpenCV and Whisper in a child keeps the API and polling alive.
    """
    os.makedirs(output_dir, exist_ok=True)
    request_path = os.path.abspath(os.path.join(output_dir, "manual_request.json"))
    state_path = os.path.abspath(os.path.join(output_dir, "manual_status.json"))
    job = jobs_dict.get(job_id) if jobs_dict is not None else None
    if job is None:
        job = {"status": "queued", "logs": [], "user_id": None}
    job.setdefault("logs", [])

    def persist():
        snapshot = {name: job[name] for name in _STATE_FIELDS if name in job}
        snapshot.update(job_id=job_id, user_id=job.get("user_id"),
                        logs=list(job["logs"]), supervisor_pid=os.getpid())
        _atomic_json(state_path, snapshot)

    def log(message):
        safe_print(f"[{job_id}] {message}")
        job["logs"].append(message)
        persist()

    process = None
    try:
        request = dict(job_id=job_id, src_video=os.path.abspath(src_video),
            clips_config=clips_config, output_dir=os.path.abspath(output_dir),
            speed=speed, outro_path=outro_path, output_format=output_format)
        _atomic_json(request_path, request)
        job["status"] = "processing"
        persist()
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        process = subprocess.Popen([sys.executable, "-X", "faulthandler", "-u",
            os.path.abspath(__file__), "--job", request_path], cwd=_REPO_ROOT,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        for raw in process.stdout:
            line = raw.rstrip()
            if line.startswith(_STATE_PREFIX):
                patch = json.loads(line[len(_STATE_PREFIX):])
                job.update({key: patch[key] for key in _STATE_FIELDS if key in patch})
                persist()
            elif line:
                prefix = f"[{job_id}] "
                log(line[len(prefix):] if line.startswith(prefix) else line)
        returncode = process.wait()
        if returncode != 0:
            code = returncode & 0xffffffff
            raise RuntimeError(f"Manual rendering process exited with code 0x{code:08X}. "
                               "The server is still running; see the job logs for the last rendering step.")
        if job.get("status") != "completed":
            raise RuntimeError("Manual rendering did not produce a completed job. See the rendering logs.")
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        log(str(exc))
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                process.wait()
            process.stdout.close()
        persist()


def load_manual_job_state(job_id, output_dir):
    """Recover terminal results/failures after a backend restart."""
    try:
        with open(os.path.join(output_dir, "manual_status.json"), encoding="utf-8") as stream:
            state = json.load(stream)
        if not isinstance(state, dict) or state.get("job_id") != job_id:
            return None
        if state.get("status") not in ("queued", "processing", "completed", "failed"):
            return None
        if not isinstance(state.get("logs"), list):
            return None
        if state.get("status") in ("processing", "queued") and state.get("supervisor_pid") != os.getpid():
            state["status"] = "failed"
            state["error"] = "Manual rendering was interrupted by a server restart. Please retry the job."
            state.setdefault("logs", []).append(state["error"])
        state["output_dir"] = output_dir
        return state
    except (OSError, ValueError, TypeError):
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    with open(args.job, encoding="utf-8") as stream:
        config = json.load(stream)
    child_job = _EventJob(status="queued", logs=[])
    _render_manual_clips_job(**config, jobs_dict={config["job_id"]: child_job})
    raise SystemExit(0 if child_job.get("status") == "completed" else 1)
