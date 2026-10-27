export default function LayerTiming({ layer, project, onChange }) {
  const a = layer.anchor;
  return <div className="flex flex-wrap gap-3">
    <label>Source occurrence <select className="bg-black border p-2" value={a.segment_id} onChange={e => { const s = project.segments.find(s => s.id === e.target.value); onChange({ anchor: { type: 'occurrence', segment_id: s.id, source_start_ms: s.source_start_ms, source_end_ms: Math.min(s.source_end_ms, s.source_start_ms + 4000) }, needs_review: false }); }}><option value="" disabled>Choose occurrence</option>{project.segments.map(s => <option key={s.id} value={s.id}>{s.role} · {s.source_start_ms / 1000}–{s.source_end_ms / 1000}s · {s.id.slice(0, 6)}</option>)}</select></label>
    {['source_start_ms', 'source_end_ms'].map(k => <label key={k}>{k === 'source_start_ms' ? 'Source start (s)' : 'Source end (s)'} <input className="bg-black border p-2 w-24" type="number" step="0.1" min="0" value={a[k] / 1000} onChange={e => onChange({ anchor: { ...a, [k]: Math.round(Number(e.target.value) * 1000) } })} /></label>)}
    <label><input type="checkbox" checked={layer.enabled} onChange={e => onChange({ enabled: e.target.checked })} /> Include layer</label>
    {layer.needs_review && <><p role="alert">Source edit changed this placement. Review the occurrence and times.</p><button className="btn-ghost" onClick={() => onChange({ needs_review: false })}>Confirm reviewed placement</button></>}
  </div>;
}
