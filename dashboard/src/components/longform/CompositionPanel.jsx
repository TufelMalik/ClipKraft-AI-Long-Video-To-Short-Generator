import { useState } from 'react';
import AudioPanel from './AudioPanel';

const empty = () => ({ version: 1, voice: { cleanup: 'off', gain_db: 0 }, audio_tracks: [], visual_layers: [], loudness_lufs: -16 });

export default function CompositionPanel({ project, caps, request, wait, action, busy, showMedia, watched, applied }) {
  const [value, setValue] = useState(() => structuredClone(project.composition || empty()));
  const [assets, setAssets] = useState([]);
  const [preview, setPreview] = useState(null);
  const [audition, setAudition] = useState({ muted: [], solo: '', bypass: false });
  const [loaded, setLoaded] = useState(false);
  const change = next => { setValue(next); setPreview(null); };
  const refresh = async () => { setAssets(await request('/api/edit-assets', undefined, 'GET')); setLoaded(true); };
  const render = async (auditionOnly = false) => {
    setPreview(null);
    const draft = structuredClone(value);
    if (auditionOnly) {
      if (audition.bypass) draft.voice = { cleanup: 'off', gain_db: 0 };
      draft.audio_tracks = draft.audio_tracks.map(t => ({ ...t, enabled: t.enabled && !audition.muted.includes(t.id) && (!audition.solo || audition.solo === t.id) }));
    }
    const e = await wait(await request(`/api/edit-projects/${project.project_id}/composition/preview`, { expected_revision: project.revision, composition: draft, audition_only: auditionOnly }));
    await showMedia(e);
    if (!auditionOnly) setPreview(e);
  };
  return <details className="my-4 border-t border-gray-700 pt-3" onToggle={e => { if (e.currentTarget.open && !loaded) action(refresh); }}><summary>Audio, visuals and local assets</summary>
    <fieldset disabled={busy} className="space-y-4 my-4">
      <p className="text-sm text-gray-300">Draft changes need a preview, playback and approval before saving. Undo restores the complete composition.</p>
      <label>Upload local media <input className="block my-2" type="file" accept=".wav,.mp3,.m4a,.flac,.ogg,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp" onChange={e => { const f = e.target.files?.[0]; if (f) action(async () => { const data = new FormData(); data.append('file', f); await request('/api/edit-assets', data); await refresh(); }); e.target.value = ''; }} /></label>
      <p className="text-sm text-gray-300">Use media you own or have permission to use. Uploads are private to this local editor. Maximum 256 MB per file.</p>
      {caps.audio && <AudioPanel value={value} onChange={change} assets={assets} revision={project.revision} duration={project.duration_ms} audition={audition} setAudition={setAudition} />}
      <div className="flex flex-wrap items-center gap-3"><label><input type="checkbox" checked={audition.bypass} onChange={e => setAudition({ ...audition, bypass: e.target.checked })} /> Bypass voice processing in audition</label><button className="btn-ghost" onClick={() => action(() => render(true))}>Audition only</button><button className="btn-ghost" onClick={() => action(() => render())}>Preview composition to save</button><button className="btn-primary" disabled={!preview || !watched} onClick={() => action(async () => { await request(`/api/edit-projects/${project.project_id}/composition/apply`, { expected_revision: project.revision, preview_id: preview.export_id, composition_hash: preview.composition_hash, approved: true }); await applied(); })}>Approve and save composition</button><button className="btn-ghost" onClick={() => change(structuredClone(project.composition || empty()))}>Reset draft</button></div>
      {preview && <p role="status">Play the preview above, then approve to save this exact version.</p>}
    </fieldset>
  </details>;
}
