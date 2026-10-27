import { useState } from 'react';
import AudioPanel from './AudioPanel';
import VisualsPanel from './VisualsPanel';

const empty = () => ({ version: 1, voice: { cleanup: 'off', gain_db: 0 }, audio_tracks: [], visual_layers: [], loudness_lufs: -16 });

export default function CompositionPanel({ project, caps, request, wait, action, busy, showMedia, watched, mediaId, applied }) {
  const [value, setValue] = useState(() => structuredClone(project.composition || empty()));
  const [assets, setAssets] = useState([]);
  const [preview, setPreview] = useState(null);
  const [audition, setAudition] = useState({ muted: [], solo: '', bypass: false });
  const [loaded, setLoaded] = useState(false);
  const [section, setSection] = useState(caps.audio ? 'audio' : caps.visuals ? 'visuals' : 'media');
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
  const sections = [
    ...(caps.audio ? [{ id: 'audio', title: 'Audio storytelling', description: 'Voice, music & sound effects', count: value.audio_tracks.length }] : []),
    ...(caps.visuals ? [{ id: 'visuals', title: 'Visual explanations', description: 'Key points, steps & callouts', count: value.visual_layers.length }] : []),
    { id: 'media', title: 'Local media', description: 'Your private asset library', count: assets.length },
  ];
  return <details className="composition-workspace my-5" onToggle={e => { if (e.currentTarget.open && !loaded) action(refresh); }}><summary><span>Audio, visuals and local assets</span><span className="composition-badge">Preview before saving</span></summary>
    <fieldset disabled={busy} className="space-y-4 my-4">
      <p className="text-sm text-gray-300">Draft changes need a preview, playback and approval before saving. Undo restores the complete composition.</p>
      <div className="composition-sections" role="group" aria-label="Editing tools">{sections.map(s => <button key={s.id} type="button" aria-pressed={section === s.id} aria-controls="composition-tool-content" onClick={() => setSection(s.id)}><span className="flex items-center justify-between gap-2"><strong>{s.title}</strong><span className="composition-count">{s.count}</span></span><span className="composition-description">{s.description}</span></button>)}</div>
      <div id="composition-tool-content" className="composition-content">
      {section === 'media' && <section aria-label="Local media" className="space-y-3">
      <label>Upload local media <input className="block my-2" type="file" accept=".wav,.mp3,.m4a,.flac,.ogg,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp" onChange={e => { const f = e.target.files?.[0]; if (f) action(async () => { const data = new FormData(); data.append('file', f); await request('/api/edit-assets', data); await refresh(); }); e.target.value = ''; }} /></label>
      <p className="text-sm text-gray-300">Use media you own or have permission to use. Uploads are private to this local editor. Maximum 256 MB per file.</p>
      {assets.length ? <ul className="composition-assets">{assets.map(a => <li key={a.id}><span className="min-w-0 break-words">{a.name}</span><span className="composition-badge">{a.available === false ? 'Unavailable' : a.type}</span></li>)}</ul> : <p className="composition-empty">Your library is empty. Upload music, images or footage to use in your edit.</p>}
      </section>}
      {section === 'audio' && caps.audio && <><button className="btn-ghost mb-3" onClick={() => setSection('media')}>Upload or browse media</button><AudioPanel value={value} onChange={change} assets={assets} revision={project.revision} duration={project.duration_ms} audition={audition} setAudition={setAudition} /></>}
      {section === 'visuals' && caps.visuals && <VisualsPanel value={value} onChange={change} project={project} request={request} wait={wait} action={action} />}
      </div>
      <div className="composition-approval"><p className="text-sm mb-3">{preview ? '2. Play the preview above, then approve your changes.' : '1. Preview your draft to review the complete edit.'}</p><div className="flex flex-wrap items-center gap-3">{caps.audio && <><label><input type="checkbox" checked={audition.bypass} onChange={e => setAudition({ ...audition, bypass: e.target.checked })} /> Bypass voice processing in audition</label><button className="btn-ghost" onClick={() => action(() => render(true))}>Audition only</button></>}<button className="btn-quiet" onClick={() => action(() => render())}>Preview composition to save</button><button className="btn-primary" disabled={!preview || !watched || mediaId !== preview.export_id} onClick={() => action(async () => { await request(`/api/edit-projects/${project.project_id}/composition/apply`, { expected_revision: project.revision, preview_id: preview.export_id, composition_hash: preview.composition_hash, approved: true }); await applied(); })}>Approve and save composition</button><button className="btn-ghost" onClick={() => change(structuredClone(project.composition || empty()))}>Reset draft</button></div></div>
      {preview && <p role="status">Play the preview above, then approve to save this exact version.</p>}
    </fieldset>
  </details>;
}
