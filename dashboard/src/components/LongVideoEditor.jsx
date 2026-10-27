import { useEffect, useRef, useState } from 'react';
import { apiFetch } from '../lib/api';
import { getApiUrl } from '../config';
import LongformTranscript from './LongformTranscript';
import CompositionPanel from './longform/CompositionPanel';
import './longform/editor.css';

const seconds = ms => (ms / 1000).toFixed(1);
const stamp = ms => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;

export default function LongVideoEditor({ jobId }) {
  const [caps, setCaps] = useState(null);
  const [open, setOpen] = useState(false);
  const [locked, setLocked] = useState(false);
  const [token, setToken] = useState('');
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [cards, setCards] = useState([]);
  const [selected, setSelected] = useState([]);
  const [kind, setKind] = useState('cold_open');
  const [preview, setPreview] = useState(null);
  const [watched, setWatched] = useState(false);
  const [media, setMedia] = useState(null);
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [redo, setRedo] = useState([]);
  const [publication, setPublication] = useState('');
  const [report, setReport] = useState(null);
  const [videoInput, setVideoInput] = useState('');
  const [exportId, setExportId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [dates, setDates] = useState({ start_date: new Date(Date.now() - 28 * 86400000).toISOString().slice(0, 10), end_date: new Date().toISOString().slice(0, 10) });
  const [range, setRange] = useState({ start: '', end: '' });
  const dialog = useRef(null);
  const player = useRef(null);
  const polling = useRef(null);

  async function request(path, body, method = 'POST') {
    const response = await apiFetch(path, { method, headers: { 'X-Longform-Token': token, ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: body instanceof FormData ? body : JSON.stringify(body) }) });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request failed');
    return result;
  }

  useEffect(() => {
    let active = true;
    apiFetch('/api/edit-projects/capabilities').then(async r => {
      if (!active) return;
      if (r.status === 401) { setLocked(true); return; }
      if (r.ok) { const c = await r.json(); setCaps(c); setLocked(c.enabled && c.requires_token && !c.authenticated); }
    }).catch(() => {});
    return () => { active = false; polling.current?.abort(); };
  }, []);

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);

  async function action(fn) {
    setError(''); setBusy(true);
    try { await fn(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function load(id) {
    const p = await request(`/api/edit-projects/${id}`, undefined, 'GET');
    setProject(p); setCards([]); setSelected([]); setPreview(null); setWatched(false);
    setProjects(items => [...items.filter(x => x.project_id !== p.project_id), { project_id: p.project_id, job_id: p.job_id, revision: p.revision }]);
    return p;
  }

  async function wait(submission) {
    const id = submission.operation_id;
    setOperation({ id, state: 'queued' });
    polling.current?.abort();
    const controller = new AbortController();
    polling.current = controller;
    while (!controller.signal.aborted) {
      const op = await request(`/api/edit-operations/${id}`, undefined, 'GET');
      setOperation(op);
      if (op.state === 'completed') return op.result;
      if (['failed', 'cancelled', 'interrupted'].includes(op.state)) throw new Error(op.error);
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    throw new Error('Polling stopped; the server operation may still be running.');
  }

  async function showMedia(manifest, seek = 0) {
    const access = await request(`/api/edit-exports/${manifest.export_id}/access`, {});
    setMedia({ ...manifest, ...Object.fromEntries(Object.entries(access).map(([k, v]) => [k, getApiUrl(v)])), seek });
    setWatched(false);
  }

  async function begin() {
    setOpen(true);
    await action(async () => {
      const c = await request('/api/edit-projects/capabilities', undefined, 'GET');
      if (c.requires_token && !c.authenticated) throw new Error('longform_token_required');
      setCaps(c); setLocked(false);
      setProjects(await request('/api/edit-projects', undefined, 'GET'));
    });
  }

  async function analyze(nextKind) {
    setKind(nextKind); setCards([]); setSelected([]); setPreview(null); setWatched(false);
    const result = await wait(await request(`/api/edit-projects/${project.project_id}/${nextKind.replaceAll('_', '-')}/analyze`, { expected_revision: project.revision }));
    setCards(result.suggestions);
    if (!result.suggestions.length) setError('No suitable grounded suggestions. You can continue editing manually.');
  }

  async function save(body) {
    await request(`/api/edit-projects/${project.project_id}`, { expected_revision: project.revision, ...body }, 'PATCH');
    setHistory(h => [...h, project.revision]); setRedo([]);
    await load(project.project_id);
  }

  async function restore(direction) {
    const list = direction === 'undo' ? history : redo;
    const target = list[list.length - 1];
    await request(`/api/edit-projects/${project.project_id}/restore`, { expected_revision: project.revision, target_revision: target });
    if (direction === 'undo') { setHistory(history.slice(0, -1)); setRedo([...redo, project.revision]); }
    else { setRedo(redo.slice(0, -1)); setHistory([...history, project.revision]); }
    await load(project.project_id);
  }

  if (!caps?.enabled && !locked) return null;
  return <>
    <button className="btn-quiet px-2 sm:px-3 py-2 text-xs" aria-haspopup="dialog" onClick={begin}>Edit full video</button>
    <dialog ref={dialog} aria-labelledby="long-video-editor-title" onCancel={() => setOpen(false)} className="long-video-editor">
      <div className="flex justify-between items-start gap-4 mb-4"><div><p className="eyebrow mb-2">OpenShorts / Full video</p><h2 id="long-video-editor-title" className="text-xl font-semibold">Shape your story</h2></div><button className="btn-ghost" onClick={() => setOpen(false)} aria-label="Close long video editor">Close</button></div>
      <p className="text-sm text-gray-300 mb-4">Source framing and normal speed. AI suggestions require a preview and your approval.</p>
      {locked && <form onSubmit={e => { e.preventDefault(); begin(); }} className="flex gap-2"><label>Local editor token <input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} className="bg-black border p-2" /></label><button className="btn-primary">Unlock</button></form>}
      {error && <p role="alert" className="my-3 text-amber-300">{error.replaceAll('_', ' ')}</p>}
      {!locked && <>
        <div className="flex flex-wrap gap-3 items-center mb-4">
          {jobId && <button disabled={busy} className="btn-primary" onClick={() => action(async () => { const p = await wait(await request('/api/edit-projects', { job_id: jobId })); setHistory([]); setRedo([]); await load(p.project_id); })}>Use current source</button>}
          <label className="btn-ghost cursor-pointer">Upload full video<input className="sr-only" type="file" accept="video/*" disabled={busy} onChange={e => { const file = e.target.files?.[0]; if (!file) return; action(async () => { const data = new FormData(); data.append('file', file); const p = await wait(await request('/api/edit-sources', data)); setHistory([]); setRedo([]); await load(p.project_id); setProjects(await request('/api/edit-projects', undefined, 'GET')); }); e.target.value = ''; }} /></label>
          <label>Open saved project <select className="bg-black p-2 border border-gray-600 ml-2" value={project?.project_id || ''} disabled={busy} onChange={e => action(async () => { setHistory([]); setRedo([]); setMedia(null); setReport(null); await load(e.target.value); })}><option value="" disabled>Select project</option>{projects.map(p => <option key={p.project_id} value={p.project_id}>{p.job_id} · revision {p.revision}</option>)}</select></label>
        </div>
        {operation && <p role="status" className="text-sm my-2">{operation.kind || 'Operation'}: {operation.state} {busy && <button className="btn-ghost" onClick={() => request(`/api/edit-operations/${operation.id}/cancel`, {}).catch(e => setError(e.message))}>Cancel operation</button>}</p>}
        {project && <>
          <p className="text-sm text-gray-300">Revision {project.revision} · {stamp(project.duration_ms)} · {project.source_retention}</p>
          {project.source_lease_expires_at && <p className="text-xs text-gray-400">Source lease expires {new Date(project.source_lease_expires_at * 1000).toLocaleString()}.</p>}
          {!project.source_available && <p role="alert" className="text-amber-300">Source expired. Restore or re-upload before analysis or rendering.</p>}
          <div className="flex flex-wrap gap-2 my-4">
            <button className="btn-ghost" disabled={busy || !history.length} onClick={() => action(() => restore('undo'))}>Undo</button>
            <button className="btn-ghost" disabled={busy || !redo.length} onClick={() => action(() => restore('redo'))}>Redo</button>
            {caps.cold_open && <button className="btn-primary" disabled={busy || !project.source_available} onClick={() => action(() => analyze('cold_open'))}>Find opening moments</button>}
            {caps.smart_cuts && <button className="btn-primary" disabled={busy || !project.source_available} onClick={() => action(() => analyze('smart_cuts'))}>Analyze story cuts</button>}
            <button className="btn-ghost" disabled={busy || !project.segments.some(s => s.role === 'cold_open')} onClick={() => action(() => save({ segments: project.segments.filter(s => s.role !== 'cold_open') }))}>Remove opening</button>
            <button className="btn-ghost" disabled={busy || !project.source_available} onClick={() => action(async () => { setPreview(null); await showMedia(await wait(await request(`/api/edit-projects/${project.project_id}/preview`, { expected_revision: project.revision }))); })}>Preview current edit</button>
            {caps.export && <button className="btn-primary" disabled={busy || !project.source_available} onClick={() => action(async () => { const e = await wait(await request(`/api/edit-projects/${project.project_id}/exports`, { expected_revision: project.revision })); await showMedia(e); await load(project.project_id); })}>Export video</button>}
          </div>
          {media && <section className="my-4"><p>{media.preview ? 'Preview' : 'Export'} · revision {media.revision} {report?.revision !== undefined && media.revision !== project.revision ? '· Historical timeline' : ''}</p><video key={media.export_id + media.seek} ref={player} className="w-full max-h-[45vh] bg-black" controls preload="metadata" onLoadedMetadata={() => { if (player.current) player.current.currentTime = media.seek; }} onPlay={() => setWatched(true)}><source src={media.video} type="video/mp4" /><track src={media.track} kind="captions" srcLang="en" label="Source captions" default /></video><div className="flex gap-4 my-2"><a className="underline" href={media.video} download>Download video</a><a className="underline" href={media.captions} download>Download captions (SRT)</a></div></section>}
          {(caps.audio || caps.visuals || caps.broll || project.composition) && <CompositionPanel key={project.project_id + ':' + project.revision} project={project} caps={caps} request={request} wait={wait} action={action} busy={busy} showMedia={showMedia} watched={watched} mediaId={media?.export_id} applied={async () => { setHistory([...history, project.revision]); setRedo([]); setMedia(null); await load(project.project_id); }} />}
          {!!cards.length && <section aria-label="AI suggestions"><h3 className="font-semibold my-3">{kind === 'cold_open' ? 'Opening suggestions' : 'Story cut suggestions'}</h3><div className="grid md:grid-cols-2 gap-3">{cards.map(c => <label key={c.id} className="block border border-gray-600 rounded-lg p-4"><input type={kind === 'cold_open' ? 'radio' : 'checkbox'} name="suggestion" disabled={busy} checked={selected.includes(c.id)} onChange={e => { setSelected(kind === 'cold_open' ? [c.id] : e.target.checked ? [...selected, c.id] : selected.filter(id => id !== c.id)); setPreview(null); setWatched(false); }} /> <strong>{stamp(c.start_ms)}–{stamp(c.end_ms)}</strong> · {seconds(c.end_ms - c.start_ms)}s {kind === 'smart_cuts' ? 'saved' : ''}<blockquote className="my-2">{c.text}</blockquote><p className="text-sm text-gray-300">{c.category && `${c.category.replaceAll('_', ' ')}: `}{c.reason}</p>{kind === 'smart_cuts' && <button type="button" className="btn-ghost mt-2" disabled={busy} onClick={e => { e.preventDefault(); action(() => save({ protected_ranges: [...project.protected_ranges, { start_ms: c.start_ms, end_ms: c.end_ms }] })); }}>Keep this section</button>}</label>)}</div><div className="flex gap-3 my-3"><button className="btn-ghost" disabled={busy || !selected.length} onClick={() => action(async () => { const e = await wait(await request(`/api/edit-projects/${project.project_id}/preview`, { expected_revision: project.revision, kind, suggestion_ids: selected })); setPreview(e); await showMedia(e); })}>Preview selected changes</button><button className="btn-primary" disabled={busy || !preview || !watched} onClick={() => action(async () => { await request(`/api/edit-projects/${project.project_id}/${kind.replaceAll('_', '-')}/apply`, { expected_revision: project.revision, suggestion_ids: selected, preview_id: preview.export_id, approved: true }); setHistory([...history, project.revision]); setRedo([]); setMedia(null); await load(project.project_id); })}>Approve and apply selected</button></div></section>}
          <details className="my-4 border-t border-gray-700 pt-3"><summary>Timeline, transcript and protected sections</summary><ol className="my-3">{project.segments.map(s => <li key={s.id}>{s.role.replaceAll('_', ' ')}: source {stamp(s.source_start_ms)}–{stamp(s.source_end_ms)} <button className="btn-ghost" disabled={busy || project.segments.length === 1} onClick={() => action(() => save({ segments: project.segments.filter(x => x.id !== s.id) }))}>Remove segment</button></li>)}</ol><div className="flex flex-wrap gap-3"><label>Source start (seconds)<input type="number" min="0" value={range.start} onChange={e => setRange({ ...range, start: e.target.value })} className="bg-black border p-1 w-24 ml-2" /></label><label>Source end (seconds)<input type="number" min="0" value={range.end} onChange={e => setRange({ ...range, end: e.target.value })} className="bg-black border p-1 w-24 ml-2" /></label><button className="btn-ghost" disabled={busy || range.start === '' || range.end === ''} onClick={() => action(() => save({ protected_ranges: [...project.protected_ranges, { start_ms: Math.round(Number(range.start) * 1000), end_ms: Math.round(Number(range.end) * 1000) }] }))}>Protect range</button><button className="btn-ghost" disabled={busy || range.start === '' || range.end === ''} onClick={() => action(() => save({ segments: [...project.segments, { id: crypto.randomUUID(), role: 'body', source_start_ms: Math.round(Number(range.start) * 1000), source_end_ms: Math.round(Number(range.end) * 1000) }] }))}>Append manual range</button></div>{project.protected_ranges.map((r, i) => <p key={i}>Protected {stamp(r.start_ms)}–{stamp(r.end_ms)} <button className="btn-ghost" disabled={busy} onClick={() => action(() => save({ protected_ranges: project.protected_ranges.filter((_, j) => i !== j) }))}>Unprotect</button></p>)}<LongformTranscript transcript={project.transcript} suggestions={cards.filter(c => selected.includes(c.id))} /></details>
          {caps.retention && <section className="border-t border-gray-700 pt-4"><h3 className="font-semibold">YouTube retention feedback</h3><p className="text-sm text-gray-300 my-2">Link an owned publication to the exact completed export. Retention belongs to that export, even after more edits.</p><div className="flex gap-3"><button className="btn-ghost" disabled={busy} onClick={() => action(async () => { const c = await request('/api/youtube-analytics/connect', {}); window.open(c.url, '_blank', 'noopener,noreferrer'); })}>Connect YouTube read access</button><button className="btn-ghost" disabled={busy} onClick={() => action(async () => { await request('/api/youtube-analytics/connection', undefined, 'DELETE'); setReport(null); setPublication(''); await load(project.project_id); })}>Disconnect and delete cached data</button></div><div className="flex flex-wrap gap-3 my-3"><label>Export <select className="bg-black border p-2" value={exportId} onChange={e => { setExportId(e.target.value); setConfirmed(false); }}><option value="">Choose export</option>{project.exports.map(e => <option key={e.export_id} value={e.export_id}>Revision {e.revision} · {stamp(e.duration_ms)} · {e.export_id.slice(0, 8)}</option>)}</select></label><label>YouTube video ID or URL <input className="bg-black border p-2" value={videoInput} onChange={e => { setVideoInput(e.target.value); setConfirmed(false); }} /></label></div><label className="block my-2"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> I uploaded this exact export without external edits.</label><button className="btn-primary" disabled={busy || !confirmed || !exportId || !videoInput} onClick={() => action(async () => { const link = await wait(await request(`/api/edit-projects/${project.project_id}/publications`, { export_id: exportId, video: videoInput, confirmed_exact_export: confirmed })); setPublication(link.id); await load(project.project_id); })}>Verify and link publication</button><div className="flex flex-wrap gap-3 my-3"><label>Publication <select className="bg-black border p-2" value={publication} onChange={e => { setPublication(e.target.value); setReport(null); }}><option value="">Select publication</option>{project.publications.map(p => <option key={p.id} value={p.id}>{p.video_id} · export revision {p.revision}</option>)}</select></label><label>From <input className="bg-black border p-2" type="date" value={dates.start_date} onChange={e => setDates({ ...dates, start_date: e.target.value })} /></label><label>To <input className="bg-black border p-2" type="date" value={dates.end_date} onChange={e => setDates({ ...dates, end_date: e.target.value })} /></label><button className="btn-ghost" disabled={busy || !publication} onClick={() => action(async () => setReport(await wait(await request(`/api/edit-projects/${project.project_id}/retention/refresh`, { publication_id: publication, ...dates }))))}>Refresh retention</button></div>{report && <><p className="text-sm">Export revision {report.revision} · {report.start_date}–{report.end_date}. {report.definition}</p>{!report.buckets.length ? <p role="status">Data not available yet. YouTube processing may take 1–2 days.</p> : <><svg viewBox="0 0 1000 180" role="img" aria-label="Audience watch ratio by publication interval" className="w-full my-3 border border-gray-600"><polyline fill="none" stroke="#a5b4fc" strokeWidth="3" points={report.buckets.map(b => `${b.end_ms / report.duration_ms * 1000},${175 - b.watch_ratio / Math.max(1, ...report.buckets.map(x => x.watch_ratio)) * 160}`).join(' ')} /></svg><p className="text-sm text-gray-300">Select an interval to seek the linked export. Source occurrences are shown below; markers describe correlation only.</p><div className="max-h-64 overflow-auto"><table className="w-full text-sm"><caption className="sr-only">Retention intervals and source mappings</caption><thead><tr><th>Published interval</th><th>Watch ratio</th><th>Source ranges</th><th>Observation</th></tr></thead><tbody>{report.buckets.map(b => <tr key={b.end_ms}><td><button className="underline p-2" onClick={() => action(async () => { const e = project.exports.find(x => x.export_id === report.export_id); await showMedia(e, b.start_ms / 1000); })}>{stamp(b.start_ms)}–{stamp(b.end_ms)}</button></td><td>{(b.watch_ratio * 100).toFixed(1)}%</td><td>{b.source_ranges.map(r => `${stamp(r.start_ms)}–${stamp(r.end_ms)} (${r.segment_id.slice(0, 6)})`).join(', ')}</td><td>{report.observations.find(o => o.end_ms === b.end_ms)?.kind || '—'}</td></tr>)}</tbody></table></div></>}</>}</section>}
        </>}
      </>}
    </dialog>
  </>;
}
