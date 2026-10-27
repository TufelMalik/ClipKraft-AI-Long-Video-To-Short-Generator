import { useImperativeHandle, useRef, useState } from 'react';
import AudioPanel from './AudioPanel';
import VisualsPanel from './VisualsPanel';
import BrollPanel from './BrollPanel';
import AssetLibrary from './AssetLibrary';

const empty = () => ({ version: 1, voice: { cleanup: 'off', gain_db: 0 }, audio_tracks: [], visual_layers: [], loudness_lufs: -16 });

export default function CompositionPanel({ project, caps, request, wait, action, busy, showMedia, watched, mediaId, applied, guideRef = null }) {
  const workspace = useRef(null);
  const [value, setValue] = useState(() => structuredClone(project.composition || empty()));
  const [assets, setAssets] = useState([]);
  const [preview, setPreview] = useState(null);
  const [audition, setAudition] = useState({ muted: [], solo: '', bypass: false });
  const [loaded, setLoaded] = useState(false);
  const [section, setSection] = useState(caps.audio ? 'audio' : caps.visuals ? 'visuals' : caps.broll ? 'broll' : 'media');
  useImperativeHandle(guideRef, () => ({ openTool(name) {
    setSection(name);
    if (workspace.current) { workspace.current.open = true; workspace.current.scrollIntoView({ block: 'start', behavior: 'auto' }); }
  } }));
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
  const canSave = preview && watched && mediaId === preview.export_id;
  const dirty = JSON.stringify(value) !== JSON.stringify(project.composition || empty());
  const sections = [
    ...(caps.audio ? [{ id: 'audio', title: 'Audio', description: 'Voice, music & effects', count: value.audio_tracks.length }] : []),
    ...(caps.visuals ? [{ id: 'visuals', title: 'Text & graphics', description: 'Titles, steps & callouts', count: value.visual_layers.filter(v => v.kind !== 'broll').length }] : []),
    ...(caps.broll ? [{ id: 'broll', title: 'B-roll', description: 'Add footage & images', count: value.visual_layers.filter(v => v.kind === 'broll').length }] : []),
    { id: 'media', title: 'My media', description: 'Upload & organize files', count: assets.length },
  ];
  return <details ref={workspace} open className="composition-workspace my-5" onToggle={e => { if (e.currentTarget.open && !loaded) action(refresh); }}><summary><span>Edit your video</span><span className="composition-badge">Changes save after preview</span></summary>
    <fieldset disabled={busy} className="space-y-4 my-4">
      <ol className="composition-steps" aria-label="Editing progress"><li aria-current={!preview ? 'step' : undefined}>1. Edit</li><li aria-current={preview && !canSave ? 'step' : undefined}>2. Watch preview</li><li aria-current={canSave ? 'step' : undefined}>3. Save</li></ol>
      <div className="composition-layout">
      <div className="composition-sections" role="group" aria-label="Editing tools">{sections.map(s => <button key={s.id} type="button" aria-pressed={section === s.id} aria-controls="composition-tool-content" onClick={() => setSection(s.id)}><span className="flex items-center justify-between gap-2"><strong>{s.title}</strong><span className="composition-count">{s.count}</span></span><span className="composition-description">{s.description}</span></button>)}</div>
      <div id="composition-tool-content" className="composition-content">
      {section === 'media' && <section aria-label="Local media" className="space-y-3">
      <h3 className="font-semibold">My media</h3><label className="block rounded-lg border border-dashed border-rule p-4">Upload a file<input className="block my-2 max-w-full" type="file" accept=".wav,.mp3,.m4a,.flac,.ogg,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp" onChange={e => { const f = e.target.files?.[0]; if (f) action(async () => { const data = new FormData(); data.append('file', f); await request('/api/edit-assets', data); await refresh(); }); e.target.value = ''; }} /></label>
      <p className="text-sm text-gray-300">Use media you own or have permission to use. Uploads are private to this local editor. Maximum 256 MB per file.</p>
      {assets.length ? <AssetLibrary assets={assets} request={request} action={action} refresh={refresh} /> : <p className="composition-empty">Your library is empty. Upload music, images or footage to use in your edit.</p>}
      </section>}
      {section === 'audio' && caps.audio && <><div className="flex flex-wrap items-center justify-between gap-2 mb-4"><h3 className="font-semibold">Voice & background audio</h3><button className="btn-ghost" onClick={() => setSection('media')}>Upload audio</button></div><AudioPanel value={value} onChange={change} assets={assets} revision={project.revision} duration={project.duration_ms} audition={audition} setAudition={setAudition} /><details className="editor-advanced mt-4"><summary>Compare audio before saving</summary><div className="space-y-3 pt-3"><label className="block"><input type="checkbox" checked={audition.bypass} onChange={e => setAudition({ ...audition, bypass: e.target.checked })} /> Hear original voice processing</label><button className="btn-ghost" onClick={() => action(() => render(true))}>Listen to comparison</button><p className="text-xs text-muted">Uses your mute/solo choices. This comparison cannot be saved; use Preview changes for the final version.</p></div></details></>}
      {section === 'visuals' && caps.visuals && <VisualsPanel value={value} onChange={change} project={project} request={request} wait={wait} action={action} />}
      {section === 'broll' && caps.broll && <BrollPanel value={value} onChange={change} project={project} assets={assets} request={request} wait={wait} action={action} openLibrary={() => setSection('media')} />}
      </div>
      </div>
      <div className="composition-approval"><p role="status" className="text-sm">{canSave ? 'Preview watched. Ready to save.' : preview ? 'Play the preview above to unlock Save.' : dirty ? 'Unsaved changes. Preview before saving.' : 'No unsaved changes.'}</p><div className="flex flex-wrap items-center gap-2"><button aria-label="Preview changes" className={canSave ? 'btn-quiet' : 'btn-primary'} onClick={() => action(() => render())}>{busy ? 'Working…' : <><span className="sm:hidden">Preview</span><span className="hidden sm:inline">Preview changes</span></>}</button><button aria-label="Save changes" className={canSave ? 'btn-primary' : 'btn-quiet'} disabled={!canSave} onClick={() => action(async () => { await request(`/api/edit-projects/${project.project_id}/composition/apply`, { expected_revision: project.revision, preview_id: preview.export_id, composition_hash: preview.composition_hash, approved: true }); await applied(); })}><span className="sm:hidden">Save</span><span className="hidden sm:inline">Save changes</span></button><button aria-label="Discard draft" className="btn-ghost" onClick={() => change(structuredClone(project.composition || empty()))}><span className="sm:hidden">Reset</span><span className="hidden sm:inline">Discard draft</span></button></div></div>
    </fieldset>
  </details>;
}
