"""Isolated, opt-in self-host long-form API. Cloud is explicitly gated pending storage integration."""
import asyncio
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from edit_project import EditError, apply_suggestions, digest, flag, new_project, uid, validate
from edit_project_store import Store, process_alive
from timeline_map import timeline, remap_transcript
import edit_llm
import longform_render
import youtube_retention as youtube


def build_router(host):
    tasks = set()
    store_instance = None

    def store():
        nonlocal store_instance
        if store_instance is None:
            store_instance = Store(host.OUTPUT_DIR)
        return store_instance

    def lease(p):
        path = source(p)
        lifetime = min(int(os.getenv('LONGFORM_SOURCE_LEASE_SECONDS', '7200')), 86400)
        retention = getattr(host, 'JOB_RETENTION_SECONDS', 86400)
        if Path(path).resolve().is_relative_to(Path(host.OUTPUT_DIR).resolve()):
            retention = min(retention, getattr(host, 'SOURCE_RETENTION_SECONDS', retention))
        policy_end = os.path.getmtime(path) + retention
        expires = min(time.time() + lifetime, policy_end)
        store().put('lease', p['job_id'], {'expires': expires})
        return expires

    async def guard(request: Request):
        if host.BILLING_ENABLED:
            raise HTTPException(503, 'longform_cloud_storage_unavailable')
        client = request.client.host if request.client else ''
        if client not in ('127.0.0.1', '::1', 'testclient') or request.url.hostname not in ('127.0.0.1', 'localhost', '::1', 'testserver'):
            raise HTTPException(403, 'longform_loopback_required')
        origin = request.headers.get('origin')
        if origin and urlparse(origin).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise HTTPException(403, 'invalid_origin')
        if store_instance is not None:
            store_instance.prune()
        # OAuth callback uses one-time state rather than a browser header.
        token = os.getenv('LONGFORM_LOCAL_TOKEN')
        if re.fullmatch(r'/api/edit-exports/[a-f0-9]{32}/(?:video|captions|track)', request.url.path) and request.query_params.get('ticket'):
            try:
                ticket = store().get('media_ticket', request.query_params['ticket'])
                if ticket['expires'] > time.time() and ticket['path'] == request.url.path:
                    return
            except EditError:
                pass
        if token and request.url.path not in ('/api/youtube-analytics/callback', '/api/edit-projects/capabilities') and not hmac.compare_digest(request.headers.get('x-longform-token', ''), token):
            raise HTTPException(401, 'longform_token_required')

    @asynccontextmanager
    async def lifespan(_app):
        yield
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*list(tasks), return_exceptions=True)

    router = APIRouter(dependencies=[Depends(guard)], lifespan=lifespan)

    def enabled(feature=None):
        if not flag('LONGFORM_EDITING_ENABLED') or feature and not flag(feature):
            raise HTTPException(404, 'feature_disabled')

    def read(kind, id):
        try:
            return store().get(kind, id)
        except EditError as e:
            raise HTTPException(404, str(e))

    def failure(e):
        code = str(e)
        raise HTTPException(409 if code in ('revision_conflict', 'analysis_stale') else 400, code)

    def source(p):
        path = host._locate_source(p['job_id'])
        if not path or not Path(path).is_file():
            raise EditError('source_missing')
        return path

    async def verify_source(p):
        path = source(p)
        if await asyncio.to_thread(longform_render.fingerprint, path) != p['source']['fingerprint']:
            raise EditError('source_changed')
        return path

    def revision(p, body):
        if type(body.get('expected_revision')) is not int or p['revision'] != body['expected_revision']:
            raise HTTPException(409, 'revision_conflict')

    def suggestions(p, body, kind):
        ids = body.get('suggestion_ids', [])
        if not isinstance(ids, list) or not 0 < len(ids) <= 24 or any(not isinstance(id, str) or len(id) > 100 for id in ids) or len(ids) != len(set(ids)):
            raise EditError('select_suggestions')
        result = [store().get('suggestion', id) for id in ids]
        if any(s['project_id'] != p['project_id'] or s['kind'] != kind for s in result):
            raise EditError('not_found')
        return result

    async def submit(project_id, kind, work):
        enabled()
        admission = store().slot('longform-work', 7500)
        try:
            admission.__enter__()
        except EditError as e:
            raise HTTPException(429, str(e))
        op_id = uid()
        op = {'id': op_id, 'project_id': project_id, 'kind': kind, 'state': 'queued',
              'created_at': time.time(), 'pid': os.getpid(), 'cancel_requested': False}
        try:
            store().put('operation', op_id, op)
        except BaseException:
            admission.__exit__(None, None, None)
            raise

        async def run():
            inner = watcher = None
            try:
                # One host-wide long-form workload. Refuse a busy slot; never build an unbounded queue.
                op['state'] = 'running'
                store().put('operation', op_id, op)

                async def watch():
                    while True:
                        await asyncio.sleep(.5)
                        if store().get('operation', op_id)['cancel_requested']:
                            raise asyncio.CancelledError()

                inner = asyncio.create_task(work(op_id))
                watcher = asyncio.create_task(watch())
                done, _ = await asyncio.wait((inner, watcher), timeout=7200, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    raise EditError('operation_timeout')
                if watcher in done:
                    raise asyncio.CancelledError()
                result = await inner
                op.update(state='completed', result=result)
            except asyncio.CancelledError:
                op.update(state='cancelled', error='operation_cancelled')
            except Exception as e:
                # No transcript, HTTP response bodies, filesystem paths or credentials in stored errors.
                op.update(state='failed', error=str(e) if isinstance(e, EditError) else 'operation_failed')
            finally:
                for task in (inner, watcher):
                    if task and not task.done():
                        task.cancel()
                for task in (inner, watcher):
                    if task:
                        try:
                            await task
                        except BaseException:
                            pass
                op['finished_at'] = time.time()
                try:
                    store().put('operation', op_id, op)
                finally:
                    admission.__exit__(None, None, None)

        task = asyncio.create_task(run())
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        from fastapi.responses import JSONResponse
        return JSONResponse({'operation_id': op_id}, status_code=202)

    @router.get('/api/edit-projects/capabilities')
    async def capabilities(request: Request):
        token = os.getenv('LONGFORM_LOCAL_TOKEN', '')
        return {'enabled': flag('LONGFORM_EDITING_ENABLED'), 'cold_open': flag('COLD_OPEN_ENABLED'),
                'smart_cuts': flag('SMART_CUTS_ENABLED'), 'retention': flag('YOUTUBE_RETENTION_ENABLED'),
                'export': flag('LONGFORM_EXPORT_ENABLED'), 'local_only': True,
                'requires_token': bool(token), 'authenticated': not token or hmac.compare_digest(request.headers.get('x-longform-token', ''), token)}

    @router.get('/api/edit-projects')
    async def projects():
        return [{'project_id': p['project_id'], 'job_id': p['job_id'], 'revision': p['revision']}
                for p in store().all('project')]

    async def create(job_id):
        path = host._locate_source(job_id)
        if not path:
            raise EditError('source_missing')
        info = await longform_render.probe(path)
        transcript = None
        directory = Path(host.OUTPUT_DIR) / job_id
        for candidate in [directory / 'source_transcript.json', directory / '.transcript_checkpoint.json', *directory.glob('*_metadata.json')]:
            if candidate.is_file():
                data = await asyncio.to_thread(lambda: json.loads(candidate.read_text(encoding='utf-8-sig')))
                transcript = data.get('transcript', data)
                if 'segments' in transcript:
                    break
        if not transcript or 'segments' not in transcript:
            raise EditError('transcript_missing')
        p = new_project(job_id, round(float(info['format']['duration']) * 1000),
                        await asyncio.to_thread(longform_render.fingerprint, path), transcript)
        store().put('transcript', p['project_id'], transcript)
        lease(p)
        return store().put('project', p['project_id'], p)

    @router.post('/api/edit-projects')
    async def create_project(request: Request):
        enabled()
        body = await request.json()
        job_id = body.get('job_id', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', job_id):
            raise HTTPException(400, 'invalid_job_id')
        await host._ensure_job_files(job_id, request)
        if job_id not in host.jobs:
            raise HTTPException(404, 'job_not_found')
        async def work(_):
            return await create(job_id)
        return await submit(None, 'create', work)

    @router.post('/api/edit-sources')
    async def ingest(request: Request, file: UploadFile = File(...)):
        enabled()
        extension = Path(file.filename or '').suffix.lower()
        if extension not in ('.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'):
            raise HTTPException(400, 'unsupported_video_file')
        job_id = uid()
        directory = Path(host.OUTPUT_DIR) / job_id
        directory.mkdir(parents=True)
        path = Path(host.UPLOAD_DIR) / (job_id + '_source' + extension)
        size = 0
        try:
            with path.open('wb') as stream:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > int(os.getenv('LONGFORM_MAX_SOURCE_MB', '4096')) * 1024 * 1024:
                        raise HTTPException(413, 'source_size_limit')
                    await asyncio.to_thread(stream.write, chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            directory.rmdir()
            raise

        async def work(_):
            store().put('lease', job_id, {'expires': min(time.time() + 7200, path.stat().st_mtime + getattr(host, 'JOB_RETENTION_SECONDS', 86400))})
            try:
                info = await longform_render.probe(path)
                duration = float(info['format']['duration'])
                if not 0 < duration <= int(os.getenv('LONGFORM_MAX_DURATION_SECONDS', '7200')):
                    raise EditError('duration_limit')
                transcript_path = directory / 'source_transcript.json'
                # ASR in a cancellable child, with the same host slots and release contract as main.
                worker = Path(__file__).resolve().parents[1] / 'services' / 'longform_transcribe.py'
                await longform_render.command([sys.executable, worker, path.resolve(), transcript_path.resolve()], 3600)
                host.jobs[job_id] = {'status': 'completed', 'logs': [], 'result': {'clips': []}, 'created_at': time.time()}
                return await create(job_id)
            except BaseException:
                path.unlink(missing_ok=True)
                import shutil
                shutil.rmtree(directory, ignore_errors=True)
                raise
        try:
            return await submit(None, 'ingest', work)
        except BaseException:
            path.unlink(missing_ok=True)
            import shutil
            shutil.rmtree(directory, ignore_errors=True)
            raise

    @router.get('/api/edit-projects/{id}')
    async def get_project(id: str):
        p = read('project', id)
        available = bool(host._locate_source(p['job_id']))
        expires = lease(p) if available else None
        exports = [e for e in store().all('export') if e['project_id'] == id and not e.get('preview')]
        return {**p, 'source_available': available, 'source_lease_expires_at': expires, 'source_retention': 'Existing job retention and disk limits apply; re-upload if expired.',
                'time_map': timeline(p['segments']), 'transcript': remap_transcript(read('transcript', id), timeline(p['segments'])),
                'exports': exports, 'publications': [x for x in store().all('publication') if x['project_id'] == id]}

    @router.patch('/api/edit-projects/{id}')
    async def patch_project(id: str, request: Request):
        enabled()
        body = await request.json()
        def change(p):
            for key in ('segments', 'protected_ranges'):
                if key in body:
                    p[key] = body[key]
            return p
        try:
            return store().mutate(id, body.get('expected_revision'), change)
        except EditError as e:
            failure(e)

    @router.post('/api/edit-projects/{id}/restore')
    async def restore(id: str, request: Request):
        enabled()
        body = await request.json()
        previous = read('history', f"{id}:{body.get('target_revision')}")
        try:
            return store().mutate(id, body.get('expected_revision'), lambda _: previous)
        except EditError as e:
            failure(e)

    @router.post('/api/edit-projects/{id}/{feature}/analyze')
    async def analyze(id: str, feature: str, request: Request):
        kind = feature.replace('-', '_')
        if kind not in ('cold_open', 'smart_cuts'):
            raise HTTPException(404)
        enabled('COLD_OPEN_ENABLED' if kind == 'cold_open' else 'SMART_CUTS_ENABLED')
        p = read('project', id)
        revision(p, await request.json())
        async def work(_):
            await verify_source(p)
            result = await edit_llm.analyze(p, read('transcript', id), kind)
            for s in result:
                s['project_id'] = id
                store().put('suggestion', s['id'], s)
            return {'revision': p['revision'], 'suggestions': result}
        return await submit(id, 'analyze', work)

    @router.post('/api/edit-projects/{id}/preview')
    async def preview(id: str, request: Request):
        enabled()
        body = await request.json()
        p = read('project', id)
        revision(p, body)
        kind = body.get('kind')
        try:
            selected = suggestions(p, body, kind) if kind in ('cold_open', 'smart_cuts') else []
            proposed = apply_suggestions(p, selected, kind) if selected else p
        except EditError as e:
            failure(e)
        # Full proposed EDL: exact same joins and map as the final export.
        async def work(op_id):
            path = await verify_source(p)
            lease(p)
            manifest = await longform_render.render(proposed, path, read('transcript', id), Path(host.OUTPUT_DIR) / p['job_id'], op_id)
            manifest.update(preview=True, suggestion_ids=body.get('suggestion_ids', []), kind=kind)
            store().put('export', op_id, manifest)
            return manifest
        return await submit(id, 'preview', work)

    @router.post('/api/edit-projects/{id}/{feature}/apply')
    async def apply(id: str, feature: str, request: Request):
        kind = feature.replace('-', '_')
        if kind not in ('cold_open', 'smart_cuts'):
            raise HTTPException(404)
        enabled('COLD_OPEN_ENABLED' if kind == 'cold_open' else 'SMART_CUTS_ENABLED')
        p = read('project', id)
        body = await request.json()
        revision(p, body)
        try:
            selected = suggestions(p, body, kind)
            proposed = apply_suggestions(p, selected, kind)
            preview = store().get('export', body.get('preview_id', ''))
            if not preview.get('preview') or preview['project_id'] != id or preview['revision'] != p['revision'] or preview['kind'] != kind or set(preview['suggestion_ids']) != set(body['suggestion_ids']) or body.get('approved') is not True:
                raise EditError('preview_approval_required')
            # IDs are allocated at application; compare immutable source/role sequence instead.
            shape = lambda ss: [(s['source_start_ms'], s['source_end_ms'], s['role']) for s in ss]
            if shape(preview['time_map']) != shape(proposed['segments']):
                raise EditError('analysis_stale')
            proposed['segments'] = [{key: segment[key] for key in ('id', 'role', 'source_start_ms', 'source_end_ms')}
                                    for segment in preview['time_map']]
            await verify_source(p)
            return store().mutate(id, p['revision'], lambda _: proposed)
        except EditError as e:
            failure(e)

    @router.post('/api/edit-projects/{id}/exports')
    async def export(id: str, request: Request):
        enabled('LONGFORM_EXPORT_ENABLED')
        p = read('project', id)
        revision(p, await request.json())
        async def work(op_id):
            path = await verify_source(p)
            lease(p)
            manifest = await longform_render.render(p, path, read('transcript', id), Path(host.OUTPUT_DIR) / p['job_id'], op_id)
            store().put('export', op_id, manifest)
            return manifest
        return await submit(id, 'export', work)

    @router.get('/api/edit-operations/{id}')
    async def operation(id: str):
        op = read('operation', id)
        if op['state'] in ('queued', 'running'):
            alive = process_alive(op['pid'])
            if not alive or time.time() - op['created_at'] > 7500:
                op.update(state='interrupted', error='operation_interrupted_retry')
                store().put('operation', id, op)
        return op

    @router.get('/api/edit-operations')
    async def operations():
        return sorted(store().all('operation'), key=lambda x: x['created_at'], reverse=True)[:30]

    @router.post('/api/edit-operations/{id}/cancel')
    async def cancel(id: str):
        op = read('operation', id)
        if op['state'] in ('running', 'queued'):
            op['cancel_requested'] = True
            store().put('operation', id, op)
        return {'state': op['state']}

    @router.get('/api/edit-exports/{id}/{asset}')
    async def artifact(id: str, asset: str):
        e = read('export', id)
        p = read('project', e['project_id'])
        key = 'filename' if asset == 'video' else 'captions_filename' if asset in ('captions', 'track') else None
        if not key:
            raise HTTPException(404)
        path = Path(host.OUTPUT_DIR) / p['job_id'] / e[key]
        if not path.is_file():
            raise HTTPException(410, 'artifact_expired')
        if asset == 'track':
            from fastapi.responses import Response
            value = path.read_text(encoding='utf-8-sig')
            value = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', value)
            return Response('WEBVTT\n\n' + value, media_type='text/vtt')
        return FileResponse(path, media_type='video/mp4' if asset == 'video' else 'application/x-subrip', filename=path.name)

    @router.post('/api/edit-exports/{id}/access')
    async def media_access(id: str):
        read('export', id)
        result = {}
        for asset in ('video', 'captions', 'track'):
            ticket = uid()
            path = f'/api/edit-exports/{id}/{asset}'
            store().put('media_ticket', ticket, {'path': path, 'expires': time.time() + 3600})
            result[asset] = path + '?ticket=' + ticket
        return result

    def youtube_enabled():
        enabled('YOUTUBE_RETENTION_ENABLED')

    @router.post('/api/youtube-analytics/connect')
    async def connect():
        youtube_enabled()
        try:
            return youtube.connect(store())
        except EditError as e:
            failure(e)

    @router.get('/api/youtube-analytics/callback')
    async def callback(state: str, code: str):
        youtube_enabled()
        try:
            await youtube.callback(store(), state, code)
        except EditError as e:
            failure(e)
        return HTMLResponse('<p>YouTube connected. Close this tab and return to the editor.</p>', headers={'Cache-Control': 'no-store'})

    @router.delete('/api/youtube-analytics/connection')
    async def disconnect():
        try:
            await youtube.disconnect(store())
        except EditError as e:
            failure(e)
        return {'disconnected': True}

    @router.post('/api/edit-projects/{id}/publications')
    async def publication(id: str, request: Request):
        youtube_enabled()
        p = read('project', id)
        body = await request.json()
        e = read('export', body.get('export_id', ''))
        async def work(_):
            return await youtube.publication(store(), p, e, body.get('video', ''), body.get('confirmed_exact_export'))
        return await submit(id, 'publication', work)

    @router.post('/api/edit-projects/{id}/retention/refresh')
    async def refresh(id: str, request: Request):
        youtube_enabled()
        read('project', id)
        body = await request.json()
        link = read('publication', body.get('publication_id', ''))
        if link['project_id'] != id:
            raise HTTPException(404)
        e = read('export', link['export_id'])
        async def work(_):
            return await youtube.report(store(), link, e, body['start_date'], body['end_date'])
        return await submit(id, 'retention', work)

    @router.get('/api/edit-projects/{id}/retention')
    async def retention(id: str, publication_id: str):
        link = read('publication', publication_id)
        if link['project_id'] != id:
            raise HTTPException(404)
        try:
            report = store().get('report', publication_id)
        except EditError:
            return {'state': 'report_pending', 'buckets': []}
        age = time.time() - report['fetched_at']
        if age > min(int(os.getenv('YOUTUBE_CACHE_TTL_SECONDS', '86400')), 30 * 86400):
            store().delete('report', publication_id)
            return {'state': 'refresh_required', 'buckets': []}
        return report

    return router
