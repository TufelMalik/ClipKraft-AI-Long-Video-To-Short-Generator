import React from 'react';

export default function EditorialSettings({ value, onChange, intro, outro, onIntro, onOutro, disabled }) {
    const set = (key, next) => onChange({ ...value, [key]: next });
    return (
        <fieldset disabled={disabled} className="col-span-1 sm:col-span-3 border-t border-rule pt-4 space-y-3">
            <legend className="eyebrow pt-4">editorial additions</legend>
            <p className="text-xs text-muted">Add your context, commentary, and channel identity to each clip.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[['speaker', 'Speaker name'], ['topic', 'Your context or topic'], ['source', 'Source credit'], ['channel_name', 'Channel name']].map(([key, label]) => (
                    <label key={key} className="text-xs text-ink2 space-y-1 block">
                        <span>{label}</span>
                        <input className="input-field" maxLength={160} value={value[key]} onChange={(e) => set(key, e.target.value)} />
                    </label>
                ))}
                <label className="text-xs text-ink2 space-y-1 block">
                    <span>Channel niche</span>
                    <select className="input-field" value={value.niche} onChange={(e) => set('niche', e.target.value)}>
                        <option value="finance">Finance · green</option>
                        <option value="tech">Tech / AI · purple</option>
                        <option value="motivation">Motivation · orange</option>
                    </select>
                </label>
                <label className="text-xs text-ink2 space-y-1 block">
                    <span>Caption style</span>
                    <select className="input-field" value={value.caption_preset} onChange={(e) => set('caption_preset', e.target.value)}>
                        <option value="default">Karaoke</option>
                        <option value="hormozi">Hormozi</option>
                        <option value="neon">Neon</option>
                        <option value="clean">Minimalist</option>
                    </select>
                </label>
                {[['intro', intro, onIntro], ['outro', outro, onOutro]].map(([kind, file, update]) => (
                    <label key={kind} className="text-xs text-ink2 space-y-1 block">
                        <span>{kind} commentary · 0.5–15 seconds</span>
                        <input className="input-field text-xs" type="file" accept="audio/*" onChange={(e) => update(e.target.files?.[0] || null)} />
                        {file && <button type="button" className="text-muted underline" onClick={() => update(null)}>Remove {file.name}</button>}
                    </label>
                ))}
            </div>
            <div className="flex flex-wrap gap-4">
                {[['branding', 'Branded intro and outro'], ['trim_silence', 'Trim pauses longer than 0.8s'], ['color_grade', 'Consistent color grade'], ['sound_design', 'Subtle sound accents'], ['zoom_punches', 'Zoom on key words'], ['speaker_colors', 'Color captions by speaker'], ['reaction_shots', 'Reaction cutaways (experimental)']].map(([key, label]) => (
                    <label key={key} className="flex gap-2 items-center text-xs text-ink2">
                        <input type="checkbox" checked={value[key]} onChange={(e) => set(key, e.target.checked)} className="accent-[var(--color-accent)]" />
                        {label}
                    </label>
                ))}
            </div>
        </fieldset>
    );
}
