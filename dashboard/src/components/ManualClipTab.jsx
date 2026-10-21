import React, { useState, useRef } from 'react';
import { Upload, Plus, Trash2, Scissors, Sparkles, Clock, CheckCircle2, AlertCircle, FileVideo, X, Film, Zap } from 'lucide-react';
import { getApiUrl } from '../config';

const DEFAULT_OUTRO_PATH = "C:\\Youtube Channels\\Videos\\Temp Videos\\OUTRO_D_3.5s.mp4";

export default function ManualClipTab({ onJobStarted, isProcessing }) {
    const [file, setFile] = useState(null);
    const [localVideoPath, setLocalVideoPath] = useState('');
    const [videoUrl, setVideoUrl] = useState('');
    const [inputMode, setInputMode] = useState('file'); // 'file' | 'path' | 'url'
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Dynamic Timestamp clips list
    const [clips, setClips] = useState([
        { id: 1, hook: 'BORING JOB. REAL OPPORTUNITY?', start: '03:26', end: '04:05' },
        { id: 2, hook: 'LOOKING RICH IS EXPENSIVE.', start: '10:21', end: '12:28' }
    ]);

    // Features / Options
    const [speed, setSpeed] = useState(1.20);
    const [addOutro, setAddOutro] = useState(true);
    const [outroPath, setOutroPath] = useState(DEFAULT_OUTRO_PATH);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const fileInputRef = useRef(null);

    const addClipRow = () => {
        setClips(prev => [
            ...prev,
            { id: Date.now(), hook: '', start: '', end: '' }
        ]);
    };

    const removeClipRow = (id) => {
        if (clips.length <= 1) return;
        setClips(prev => prev.filter(c => c.id !== id));
    };

    const updateClipField = (id, field, value) => {
        setClips(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c));
    };

    const handleFileChange = (e) => {
        const selected = e.target.files?.[0];
        if (selected) {
            setFile(selected);
            setError('');
        }
    };

    const parseToSeconds = (val) => {
        if (!val) return 0;
        const s = String(val).trim();
        if (s.includes(':')) {
            const parts = s.split(':').map(Number);
            if (parts.length === 2) return parts[0] * 60 + parts[1];
            if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        }
        return parseFloat(s) || 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (inputMode === 'file' && !file) {
            setError('Please upload a video file first.');
            return;
        }
        if (inputMode === 'path' && !localVideoPath.trim()) {
            setError('Please provide a valid local video path.');
            return;
        }
        if (inputMode === 'url' && !videoUrl.trim()) {
            setError('Please provide a valid YouTube/video URL.');
            return;
        }

        // Validate timestamp ranges
        const formattedClips = [];
        for (let i = 0; i < clips.length; i++) {
            const c = clips[i];
            const startSec = parseToSeconds(c.start);
            const endSec = parseToSeconds(c.end);

            if (endSec <= startSec) {
                setError(`Clip #${i + 1} has an invalid range (End must be greater than Start).`);
                return;
            }

            formattedClips.push({
                id: String(i + 1),
                hook: c.hook.trim() || `CLIP #${i + 1}`,
                start: startSec,
                end: endSec
            });
        }

        setIsSubmitting(true);

        try {
            const formData = new FormData();
            if (inputMode === 'file' && file) {
                formData.append('file', file);
            } else if (inputMode === 'path' && localVideoPath) {
                formData.append('video_path', localVideoPath.trim());
            } else if (inputMode === 'url' && videoUrl) {
                formData.append('url', videoUrl.trim());
            }

            formData.append('timestamps', JSON.stringify(formattedClips));
            formData.append('speed', String(speed));
            if (addOutro && outroPath.trim()) {
                formData.append('outro_path', outroPath.trim());
            }

            const res = await fetch(getApiUrl('/api/manual-clip/process'), {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to start manual clipping job.');
            }

            const data = await res.json();
            if (data.job_id) {
                // Pass to App.jsx to switch to live analysis & processing view
                onJobStarted(data.job_id, {
                    type: inputMode === 'file' ? 'file' : 'url',
                    name: file ? file.name : (localVideoPath || videoUrl),
                    payload: file || localVideoPath || videoUrl
                });
            }
        } catch (err) {
            setError(err.message || 'Error starting job.');
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="card p-4 sm:p-6 text-left space-y-6 animate-fade">
            {/* Header info */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-rule pb-4">
                <div>
                    <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                        <Scissors className="text-brass" size={18} />
                        Manual Clip &amp; Edit
                    </h2>
                    <p className="text-xs text-muted mt-0.5">
                        Clip specific viral timestamps with 1.20x speed, smart 9:16 face-tracking, karaoke captions, and outro.
                    </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                    <span className="badge-brass flex items-center gap-1 font-mono">
                        <Zap size={12} /> 1.20x SPEED
                    </span>
                    <span className="badge-ok flex items-center gap-1 font-mono">
                        <Film size={12} /> OUTRO INCLUDED
                    </span>
                </div>
            </div>

            {error && (
                <div className="rounded-input border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400 flex items-center gap-2">
                    <AlertCircle size={16} className="shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* Video Input Source */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <label className="text-xs font-medium uppercase tracking-wider text-muted">
                        1. Select Source Video
                    </label>
                    <div className="flex items-center gap-2 text-xs">
                        <button
                            type="button"
                            onClick={() => setInputMode('file')}
                            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${inputMode === 'file' ? 'bg-paper3 text-ink border border-brass' : 'text-muted hover:text-ink'}`}
                        >
                            Upload File
                        </button>
                        <button
                            type="button"
                            onClick={() => setInputMode('path')}
                            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${inputMode === 'path' ? 'bg-paper3 text-ink border border-brass' : 'text-muted hover:text-ink'}`}
                        >
                            Local Path
                        </button>
                        <button
                            type="button"
                            onClick={() => setInputMode('url')}
                            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${inputMode === 'url' ? 'bg-paper3 text-ink border border-brass' : 'text-muted hover:text-ink'}`}
                        >
                            YouTube URL
                        </button>
                    </div>
                </div>

                {inputMode === 'file' && (
                    <div
                        onClick={() => fileInputRef.current?.click()}
                        className="border-2 border-dashed border-rule hover:border-brass/70 bg-paper/40 hover:bg-paper3/40 rounded-card p-6 text-center cursor-pointer transition-all duration-200 group"
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="video/*"
                            onChange={handleFileChange}
                            className="hidden"
                        />
                        {file ? (
                            <div className="flex items-center justify-center gap-3 text-ink">
                                <FileVideo size={24} className="text-brass" />
                                <div className="text-left">
                                    <div className="font-medium text-sm truncate max-w-sm">{file.name}</div>
                                    <div className="text-xs text-muted">{(file.size / (1024 * 1024)).toFixed(1)} MB · Ready to clip</div>
                                </div>
                                <button
                                    type="button"
                                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                                    className="p-1 text-muted hover:text-red-400 rounded-full hover:bg-paper"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                <div className="w-10 h-10 rounded-full bg-paper3 border border-rule flex items-center justify-center mx-auto text-brass group-hover:scale-105 transition-transform">
                                    <Upload size={18} />
                                </div>
                                <div className="text-sm font-medium text-ink">Click or drag &amp; drop your full video here</div>
                                <div className="text-xs text-muted">Supports MP4, MOV, MKV up to 4K</div>
                            </div>
                        )}
                    </div>
                )}

                {inputMode === 'path' && (
                    <input
                        type="text"
                        value={localVideoPath}
                        onChange={(e) => setLocalVideoPath(e.target.value)}
                        placeholder="e.g. C:\Youtube Channels\Videos\Temp Videos\01 - Mike Rowe.mp4"
                        className="w-full px-3.5 py-2.5 rounded-input border border-rule bg-paper text-sm text-ink placeholder:text-muted focus:border-brass focus:outline-none font-mono text-xs"
                    />
                )}

                {inputMode === 'url' && (
                    <input
                        type="url"
                        value={videoUrl}
                        onChange={(e) => setVideoUrl(e.target.value)}
                        placeholder="https://www.youtube.com/watch?v=..."
                        className="w-full px-3.5 py-2.5 rounded-input border border-rule bg-paper text-sm text-ink placeholder:text-muted focus:border-brass focus:outline-none"
                    />
                )}
            </div>

            {/* Dynamic Timestamps List */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <label className="text-xs font-medium uppercase tracking-wider text-muted flex items-center gap-1.5">
                        2. Viral Timestamps &amp; Hooks ({clips.length} {clips.length === 1 ? 'clip' : 'clips'})
                    </label>
                    <button
                        type="button"
                        onClick={addClipRow}
                        className="btn-ghost px-2.5 py-1 text-xs text-brass border border-brass/30 hover:border-brass hover:bg-brass/5 rounded-input flex items-center gap-1 font-medium transition-colors"
                    >
                        <Plus size={14} /> Add Timestamp Clip
                    </button>
                </div>

                <div className="space-y-3">
                    {clips.map((clip, index) => {
                        const startSec = parseToSeconds(clip.start);
                        const endSec = parseToSeconds(clip.end);
                        const rawDur = Math.max(0, endSec - startSec);
                        const finalDur = rawDur > 0 ? (rawDur / speed + (addOutro ? 3.5 : 0)).toFixed(1) : 0;

                        return (
                            <div
                                key={clip.id}
                                className="p-3.5 rounded-input border border-rule bg-paper/60 hover:border-rule2 transition-colors space-y-3"
                            >
                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-mono font-semibold text-brass flex items-center gap-1.5">
                                        <Clock size={13} /> CLIP #{index + 1}
                                    </span>
                                    <div className="flex items-center gap-2">
                                        {rawDur > 0 && (
                                            <span className="text-[11px] font-mono text-muted">
                                                {rawDur.toFixed(0)}s raw &rarr; <b className="text-ink font-semibold">{finalDur}s</b> final
                                            </span>
                                        )}
                                        {clips.length > 1 && (
                                            <button
                                                type="button"
                                                onClick={() => removeClipRow(clip.id)}
                                                className="p-1 text-muted hover:text-red-400 transition-colors"
                                                title="Remove this clip"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5">
                                    {/* Hook Banner Text */}
                                    <div className="sm:col-span-6">
                                        <label className="block text-[11px] text-muted mb-1">
                                            Hook Banner Text (Yellow on Black Box)
                                        </label>
                                        <input
                                            type="text"
                                            value={clip.hook}
                                            onChange={(e) => updateClipField(clip.id, 'hook', e.target.value)}
                                            placeholder="e.g. BORING JOB. REAL OPPORTUNITY?"
                                            className="w-full px-3 py-1.5 rounded-input border border-rule bg-paper text-xs text-ink placeholder:text-muted focus:border-brass focus:outline-none"
                                        />
                                    </div>

                                    {/* Start Time */}
                                    <div className="sm:col-span-3">
                                        <label className="block text-[11px] text-muted mb-1">
                                            Start Time (MM:SS)
                                        </label>
                                        <input
                                            type="text"
                                            value={clip.start}
                                            onChange={(e) => updateClipField(clip.id, 'start', e.target.value)}
                                            placeholder="e.g. 03:26"
                                            className="w-full px-3 py-1.5 rounded-input border border-rule bg-paper text-xs text-ink placeholder:text-muted focus:border-brass focus:outline-none font-mono"
                                        />
                                    </div>

                                    {/* End Time */}
                                    <div className="sm:col-span-3">
                                        <label className="block text-[11px] text-muted mb-1">
                                            End Time (MM:SS)
                                        </label>
                                        <input
                                            type="text"
                                            value={clip.end}
                                            onChange={(e) => updateClipField(clip.id, 'end', e.target.value)}
                                            placeholder="e.g. 04:05"
                                            className="w-full px-3 py-1.5 rounded-input border border-rule bg-paper text-xs text-ink placeholder:text-muted focus:border-brass focus:outline-none font-mono"
                                        />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Presets & Polish Badges */}
            <div className="rounded-input border border-rule/60 bg-paper3/30 p-3 space-y-2.5 text-xs">
                <div className="flex items-center justify-between text-muted text-[11px] uppercase tracking-wider font-medium">
                    <span>Applied Styles &amp; Automation</span>
                    <button
                        type="button"
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="text-brass hover:underline normal-case text-xs"
                    >
                        {showAdvanced ? 'Hide Settings' : 'Custom Outro & Speed'}
                    </button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-ink2 text-[11px]">
                    <div className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-brass" /> 1.20x Speed scaling</div>
                    <div className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-brass" /> Black box &amp; yellow hook</div>
                    <div className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-brass" /> Word karaoke subtitles</div>
                    <div className="flex items-center gap-1.5"><CheckCircle2 size={13} className="text-brass" /> Face tracking + slow zoom</div>
                </div>

                {showAdvanced && (
                    <div className="pt-2.5 border-t border-rule space-y-2 animate-fade">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                                <label className="block text-[11px] text-muted mb-1">Playback Speed Multiplier</label>
                                <input
                                    type="number"
                                    step="0.05"
                                    min="1.0"
                                    max="2.0"
                                    value={speed}
                                    onChange={(e) => setSpeed(parseFloat(e.target.value) || 1.20)}
                                    className="w-full px-2.5 py-1.5 rounded-input border border-rule bg-paper text-xs font-mono"
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] text-muted mb-1">Outro Video Path</label>
                                <input
                                    type="text"
                                    value={outroPath}
                                    onChange={(e) => setOutroPath(e.target.value)}
                                    className="w-full px-2.5 py-1.5 rounded-input border border-rule bg-paper text-xs font-mono"
                                />
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Submit Button */}
            <button
                type="submit"
                disabled={isSubmitting || isProcessing}
                className="btn-primary w-full py-3 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-brass/20 transition-all"
            >
                {isSubmitting || isProcessing ? (
                    <>
                        <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                        Processing Timestamp Clips...
                    </>
                ) : (
                    <>
                        <Scissors size={16} />
                        Generate {clips.length} Edited {clips.length === 1 ? 'Short' : 'Shorts'} (1.20x + Captions + Outro)
                    </>
                )}
            </button>
        </form>
    );
}
