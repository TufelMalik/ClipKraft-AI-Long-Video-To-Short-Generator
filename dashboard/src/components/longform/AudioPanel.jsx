export default function AudioPanel({ value, onChange, assets, revision, duration, audition, setAudition }) {
  const update = (id, changes) => onChange({ ...value, audio_tracks: value.audio_tracks.map(t => t.id === id ? { ...t, ...changes } : t) });
  const field = (label, val, change, min, max, step = 1) => <label className="flex flex-col gap-1">{label}<input className="bg-black border rounded p-2 w-32" type="number" value={val} min={min} max={max} step={step} onChange={e => change(Number(e.target.value))} /></label>;
  return <section aria-label="Audio storytelling" className="space-y-4">
    <p className="text-sm text-gray-300">Adjust your voice, then add music or sound effects. Preview to hear the result.</p>
    <div className="flex flex-wrap gap-4">
      <label>Voice cleanup <select className="bg-black border p-2" value={value.voice.cleanup} onChange={e => onChange({ ...value, voice: { ...value.voice, cleanup: e.target.value } })}><option value="off">Off</option><option value="gentle">Gentle noise reduction</option></select></label>
      {field('Voice gain (dB)', value.voice.gain_db, v => onChange({ ...value, voice: { ...value.voice, gain_db: v } }), -60, 12)}
      <label>Music preset <select className="bg-black border p-2" value="" onChange={e => onChange({ ...value, audio_tracks: value.audio_tracks.map(t => t.kind === 'music' ? { ...t, enabled: e.target.value !== 'none', gain_db: e.target.value === 'emphasis' ? -12 : -24, duck_under_voice: e.target.value !== 'none' } : t) })}><option value="">Choose settings</option><option value="background">Background: −24 dB, duck</option><option value="emphasis">Emphasis: −12 dB, duck</option><option value="none">No music: disable music tracks</option></select></label>
    </div>
    <details className="editor-advanced"><summary>Advanced voice settings</summary><div className="py-3">{field('Final loudness (LUFS)', value.loudness_lufs, v => onChange({ ...value, loudness_lufs: v }), -24, -14)}<p className="text-xs text-muted mt-2">Noise reduction reduces steady noise; it cannot remove music already mixed with speech.</p></div></details>
    <label>Add local music or SFX <select className="bg-black border p-2 ml-2" value="" onChange={e => { const a = assets.find(a => a.id === e.target.value); if (a) onChange({ ...value, audio_tracks: [...value.audio_tracks, { id: crypto.randomUUID(), kind: 'music', asset_id: a.id, asset_version: a.version, asset_in_ms: 0, anchor: { type: 'output', start_ms: 0, end_ms: Math.min(duration, a.duration_ms), base_revision: revision }, gain_db: -18, fade_in_ms: 0, fade_out_ms: 0, loop: false, duck_under_voice: false, enabled: true, needs_review: false }] }); }}><option value="">Choose uploaded audio</option>{assets.filter(a => a.type === 'audio' && a.available !== false).map(a => <option key={a.id} value={a.id}>{a.name} · {(a.duration_ms / 1000).toFixed(1)}s</option>)}</select></label>
    {value.audio_tracks.map(t => <fieldset key={t.id} className="border border-gray-600 rounded p-3 space-y-3"><legend>{assets.find(a => a.id === t.asset_id)?.name || 'Missing asset'}</legend>
      {t.needs_review && <p role="alert">Timeline changed. Review timing, then confirm below or disable this track.</p>}
      <div className="flex flex-wrap gap-4"><label>Track kind <select className="bg-black border p-2" value={t.kind} onChange={e => update(t.id, { kind: e.target.value })}><option value="music">Music</option><option value="sfx">SFX</option></select></label>
        {['start_ms', 'end_ms'].map(k => <span key={k}>{field(k === 'start_ms' ? 'Start (seconds)' : 'End (seconds)', t.anchor[k] / 1000, v => update(t.id, { anchor: { ...t.anchor, [k]: Math.round(v * 1000) } }), 0, duration / 1000, .1)}</span>)}
        {field('Gain (dB)', t.gain_db, v => update(t.id, { gain_db: v }), -60, 6)}
      </div>
      <div className="flex flex-wrap gap-4">{[['enabled', 'Include in export'], ['duck_under_voice', 'Lower music while speaking']].map(([k, label]) => <label key={k}><input type="checkbox" checked={t[k]} onChange={e => update(t.id, { [k]: e.target.checked })} /> {label}</label>)}
        {t.needs_review && <button className="btn-ghost" onClick={() => update(t.id, { needs_review: false, anchor: { ...t.anchor, base_revision: revision } })}>Confirm reviewed timing</button>}
        <button className="btn-ghost" onClick={() => onChange({ ...value, audio_tracks: value.audio_tracks.filter(x => x.id !== t.id) })}>Remove track</button>
      </div>
      <details className="editor-advanced"><summary>Fades, looping & comparison</summary><div className="flex flex-wrap gap-4 py-3">
        {field('Start within audio file (s)', t.asset_in_ms / 1000, v => update(t.id, { asset_in_ms: Math.round(v * 1000) }), 0, 7200, .1)}
        {['fade_in_ms', 'fade_out_ms'].map(k => <span key={k}>{field(k === 'fade_in_ms' ? 'Fade in (seconds)' : 'Fade out (seconds)', t[k] / 1000, v => update(t.id, { [k]: Math.round(v * 1000) }), 0, 10, .1)}</span>)}
        <label><input type="checkbox" checked={t.loop} onChange={e => update(t.id, { loop: e.target.checked })} /> Loop selected audio</label>
        <label><input type="checkbox" checked={audition.muted.includes(t.id)} onChange={e => setAudition({ ...audition, muted: e.target.checked ? [...audition.muted, t.id] : audition.muted.filter(id => id !== t.id) })} /> Mute audition only</label>
        <label><input type="checkbox" checked={audition.solo === t.id} onChange={e => setAudition({ ...audition, solo: e.target.checked ? t.id : '' })} /> Solo background in audition</label>
      </div><p className="text-xs text-muted">Looping repeats the selected tail. Mute/solo affect comparisons only; check the loop in preview.</p></details>
    </fieldset>)}
  </section>;
}
