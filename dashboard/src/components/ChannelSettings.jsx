import React, { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

export default function ChannelSettings({ value, onChange, disabled }) {
    const [profiles, setProfiles] = useState(null);
    const [error, setError] = useState('');
    const [draft, setDraft] = useState('');
    const [saving, setSaving] = useState(false);
    useEffect(() => {
        let cancelled = false;
        apiJson('/api/channel-profiles').then((data) => {
            if (!cancelled) {
                setProfiles(data);
                setDraft(JSON.stringify({ channels: data.channels }, null, 2));
            }
        }).catch((e) => { if (!cancelled) setError(e.message || 'Could not load channel profiles'); });
        return () => { cancelled = true; };
    }, []);
    if (!profiles?.available) return error ? <p className="text-xs text-muted">{error}</p> : null;
    const selected = profiles.channels.find((c) => c.id === value.channelId);
    const save = async () => {
        setSaving(true);
        setError('');
        try {
            const data = JSON.parse(draft);
            const result = await apiJson('/api/channel-profiles', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
            setProfiles({ ...profiles, channels: result.channels });
            onChange({ channelId: '', creatorId: '', niche: '' });
        } catch (e) { setError(e.detail || e.message || 'Could not save profiles'); }
        finally { setSaving(false); }
    };
    return (
        <fieldset disabled={disabled || saving} className="border-t border-rule pt-4 mt-4 space-y-3">
            <legend className="eyebrow pt-4">channel settings</legend>
            <p className="text-xs text-muted">Optionally choose a channel for niche, duplicate checks, and source tracking.</p>
            <label className="block text-xs text-ink2">Channel
                <select className="input-field mt-1" value={value.channelId} onChange={(e) => {
                    const c = profiles.channels.find((p) => p.id === e.target.value);
                    onChange({ channelId: c?.id || '', creatorId: '', niche: c?.niche || '' });
                }}>
                    <option value="">No channel assignment</option>
                    {profiles.channels.map((c) => <option key={c.id} value={c.id}>{c.name || c.id} · {c.niche}</option>)}
                </select>
            </label>
            {selected && <label className="block text-xs text-ink2">Source creator ID (optional for uploads)
                <input className="input-field mt-1" value={value.creatorId} onChange={(e) => onChange({ ...value, creatorId: e.target.value })} placeholder="Creator ID for source tracking" />
                <span className="block text-muted mt-1">Video links use the source uploader automatically.</span>
            </label>}
            <details>
                <summary className="text-xs text-ink2 cursor-pointer">Configure channels</summary>
                <p className="text-xs text-muted my-2">Add channel profiles with an id, name and niche (finance, tech or motivation). Creator lists are optional.</p>
                <label className="block text-xs text-ink2">Channel profiles
                    <textarea className="input-field font-mono text-xs mt-1" rows={10} value={draft} onChange={(e) => setDraft(e.target.value)} />
                </label>
                <button type="button" className="btn-secondary mt-2" onClick={save}>{saving ? 'Saving…' : 'Save profiles'}</button>
            </details>
            {error && <p role="alert" className="text-xs text-red-500">{error}</p>}
        </fieldset>
    );
}
