"""Composition routes registered before the editor's legacy feature catch-all."""
import asyncio
import copy
import time
from pathlib import Path

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from edit_project import EditError, flag, uid
import composition
import edit_assets
import longform_render


def register(router, store, enabled, read, revision, failure, submit, verify_source, host):
    def gates(before, after):
        a, b = before.get('composition', composition.empty()), after['composition']
        if any(a[k] != b[k] for k in ('voice', 'audio_tracks', 'loudness_lufs')):
            enabled('LONGFORM_AUDIO_ENABLED')
        if a['visual_layers'] != b['visual_layers']:
            enabled('LONGFORM_VISUALS_ENABLED')

    def validate_proposals(project):
        for layer in project['composition']['visual_layers']:
            if layer.get('proposal_id'):
                proposal = store().get('visual_proposal', layer['proposal_id'])
                if proposal['project_id'] != project['project_id'] or proposal['revision'] != project['revision'] or proposal['transcript_version'] != project['transcript_version']:
                    # Saved layers are frozen content, not re-applied AI suggestions.
                    old = read('project', project['project_id']).get('composition', {}).get('visual_layers', [])
                    if not any(x.get('proposal_id') == layer['proposal_id'] for x in old):
                        raise EditError('analysis_stale')

    @router.post('/api/edit-projects/{id}/visuals/analyze')
    async def analyze_visuals(id: str, request: Request):
        enabled('LONGFORM_VISUALS_ENABLED')
        p, body = read('project', id), await request.json()
        revision(p, body)
        async def work(_):
            await verify_source(p)
            import edit_llm
            suggestions = await edit_llm.visual_suggestions(p, read('transcript', id), body.get('segment_id'), body.get('sentence_ids'))
            for item in suggestions:
                store().put('visual_proposal', item['id'], item)
            return {'suggestions': suggestions}
        return await submit(id, 'visuals-analyze', work)

    @router.post('/api/edit-assets')
    async def upload(file: UploadFile = File(...)):
        enabled()
        if not any(flag('LONGFORM_' + name + '_ENABLED') for name in ('AUDIO', 'VISUALS', 'BROLL')):
            raise HTTPException(404, 'feature_disabled')
        try:
            return edit_assets.public(await edit_assets.ingest(store(), file))
        except EditError as e:
            failure(e)

    @router.get('/api/edit-assets')
    async def assets():
        return [{**edit_assets.public(a), 'available': (store().root / 'assets' / a['filename']).is_file()} for a in store().all('asset')]

    @router.patch('/api/edit-assets/{id}')
    async def metadata(id: str, request: Request):
        enabled()
        try:
            return edit_assets.public(edit_assets.metadata(store(), id, await request.json()))
        except EditError as e:
            failure(e)

    @router.delete('/api/edit-assets/{id}')
    async def delete(id: str):
        enabled()
        try:
            with store().slot('longform-work', 30):
                edit_assets.delete(store(), id)
            return {'deleted': True}
        except EditError as e:
            failure(e)

    @router.post('/api/edit-assets/{id}/access')
    async def access(id: str):
        read('asset', id)
        result = {}
        for kind in ('media', 'thumbnail'):
            token = uid()
            path = f'/api/edit-assets/{id}/{kind}'
            store().put('media_ticket', token, {'path': path, 'expires': time.time() + 900})
            result[kind] = path + '?ticket=' + token
        return result

    @router.get('/api/edit-assets/{id}/{kind}')
    async def media(id: str, kind: str):
        record = read('asset', id)
        if kind not in ('media', 'thumbnail'):
            raise HTTPException(404)
        filename = record['filename'] if kind == 'media' else record.get('thumbnail')
        if not filename or not (store().root / 'assets' / filename).is_file():
            raise HTTPException(410, 'asset_missing')
        return FileResponse(store().root / 'assets' / filename, headers={'X-Content-Type-Options': 'nosniff'})

    @router.post('/api/edit-projects/{id}/composition/preview')
    async def preview(id: str, request: Request):
        enabled()
        p, body = read('project', id), await request.json()
        revision(p, body)
        try:
            proposed = composition.draft(p, body.get('composition'))
            gates(p, proposed)
            validate_proposals(proposed)
        except EditError as e:
            failure(e)
        async def work(op_id):
            source = await verify_source(p)
            deps = await asyncio.to_thread(edit_assets.dependencies, store(), proposed)
            value = composition.identity(proposed, deps)
            manifest = await longform_render.render(proposed, source, read('transcript', id), Path(host.OUTPUT_DIR) / p['job_id'], op_id, asset_store=store())
            manifest.update(preview=True, kind='composition', composition_hash=value,
                            covered_ranges=[{'start_ms': 0, 'end_ms': p['duration_ms']}])
            store().put('composition_draft', op_id, {'project': proposed, 'hash': value,
                'base_hash': composition.identity(p), 'dependencies': deps, 'audition_only': body.get('audition_only') is True})
            store().put('export', op_id, manifest)
            return manifest
        return await submit(id, 'composition-preview', work)

    @router.post('/api/edit-projects/{id}/composition/apply')
    async def apply(id: str, request: Request):
        enabled()
        p, body = read('project', id), await request.json()
        revision(p, body)
        try:
            # Applying accepts only an immutable preview ID/hash, never a new payload.
            if set(body) - {'expected_revision', 'preview_id', 'composition_hash', 'approved'} or body.get('approved') is not True:
                raise EditError('preview_approval_required')
            d = store().get('composition_draft', body.get('preview_id', ''))
            if d.get('audition_only'):
                raise EditError('audition_cannot_be_applied')
            proposed = copy.deepcopy(d['project'])
            if proposed['project_id'] != id or proposed['revision'] != p['revision'] or d['base_hash'] != composition.identity(p):
                raise EditError('analysis_stale')
            gates(p, proposed)
            deps = await asyncio.to_thread(edit_assets.dependencies, store(), proposed)
            if body.get('composition_hash') != d['hash'] or composition.identity(proposed, deps) != d['hash']:
                raise EditError('preview_approval_required')
            await verify_source(p)
            return store().mutate(id, p['revision'], lambda _: proposed)
        except EditError as e:
            failure(e)
