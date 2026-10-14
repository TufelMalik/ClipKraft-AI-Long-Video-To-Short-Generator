import React, { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

export default function BrollNotes({ jobId, clipIndex, points, duration, disabled }) {
    const [draft, setDraft] = useState(points || []);
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState('');
    useEffect(() => { setDraft(points || []); setMessage(''); }, [points]);
    const update = (i, key, value) => setDraft(draft.map((p, index) => index === i ? { ...p, [key]: value } : p));
    const save = async () => {
        setBusy(true);
        setMessage('');
        try {
            const result = await apiJson('/api/clip/broll', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_id: jobId, clip_index: clipIndex, points: draft.map((p) => ({ ...p, start: Number(p.start), end: Number(p.end) })) }) });
            setDraft(result.points);
            setMessage('B-roll notes saved');
        } catch (e) { setMessage(e.detail || e.message || 'Could not save notes'); }
        finally { setBusy(false); }
    };
    return (
        <fieldset disabled={disabled || busy} className="border-t border-rule pt-4 space-y-2">
            <legend className="eyebrow pt-4">B-roll notes</legend>
            <p className="text-xs text-muted">Mark 0.5–3 second cutaways for manual editing. Times refer to the exported video, including any intro. These notes do not insert footage.</p>
            {draft.map((p, i) => (
                <div key={i} className="grid grid-cols-2 gap-2">
                    <label className="text-xs text-ink2">Start (s)<input type="number" min="0" max={duration} step="0.1" className="input-field" value={p.start} onChange={(e) => update(i, 'start', e.target.value)} /></label>
                    <label className="text-xs text-ink2">End (s)<input type="number" min="0" max={duration} step="0.1" className="input-field" value={p.end} onChange={(e) => update(i, 'end', e.target.value)} /></label>
                    <label className="text-xs text-ink2 col-span-2">Visual to add<input className="input-field" maxLength={120} value={p.label || ''} onChange={(e) => update(i, 'label', e.target.value)} /></label>
                    <button type="button" className="text-xs text-muted underline col-span-2 justify-self-start" onClick={() => setDraft(draft.filter((_, index) => index !== i))}>Remove note</button>
                </div>
            ))}
            <div className="flex gap-2 flex-wrap">
                <button type="button" className="btn-secondary" disabled={draft.length >= 24 || duration < .5} onClick={() => setDraft([...draft, { start: 0, end: Math.min(2.5, duration), label: '' }])}>Add note</button>
                <button type="button" className="btn-secondary" onClick={save}>{busy ? 'Saving…' : 'Save notes'}</button>
            </div>
            {message && <p role="status" className="text-xs text-muted">{message}</p>}
        </fieldset>
    );
}
