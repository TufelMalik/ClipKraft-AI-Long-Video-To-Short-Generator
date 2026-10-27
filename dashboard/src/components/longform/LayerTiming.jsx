export default function LayerTiming({ layer, project, onChange }) {
  const a = layer.anchor;
  return <div className="flex flex-wrap gap-3">
    <label>Video section <select className="bg-black border p-2" value={a.segment_id} onChange={e => { const s = project.segments.find(s => s.id === e.target.value); onChange({ anchor: { type: 'occurrence', segment_id: s.id, source_start_ms: s.source_start_ms, source_end_ms: Math.min(s.source_end_ms, s.source_start_ms + 4000) }, needs_review: false }); }}><option value="" disabled>Choose video section</option>{project.segments.map(s => <option key={s.id} value={s.id}>{s.role === 'cold_open' ? 'Opening' : 'Main video'} · {s.source_start_ms / 1000}–{s.source_end_ms / 1000}s</option>)}</select></label>
    {['source_start_ms', 'source_end_ms'].map(k => <label key={k}>{k === 'source_start_ms' ? 'Start in source (s)' : 'End in source (s)'} <input className="bg-black border p-2 w-24" type="number" step="0.1" min="0" value={a[k] / 1000} onChange={e => onChange({ anchor: { ...a, [k]: Math.round(Number(e.target.value) * 1000) } })} /></label>)}
    <label><input type="checkbox" checked={layer.enabled} onChange={e => onChange({ enabled: e.target.checked })} /> Show in video</label>
    {layer.needs_review && <><p role="alert">Source edit changed this placement. Review the occurrence and times.</p><button className="btn-ghost" onClick={() => onChange({ needs_review: false })}>Confirm reviewed placement</button></>}
  </div>;
}
