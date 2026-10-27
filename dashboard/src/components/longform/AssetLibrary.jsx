import { useState } from 'react';
import { getApiUrl } from '../../config';

export function AssetInspector({ asset, request, action }) {
  const [access, setAccess] = useState(null);
  return <div className="space-y-2"><button className="btn-ghost" onClick={() => action(async () => setAccess(await request(`/api/edit-assets/${asset.id}/access`, {})))}>Inspect {asset.name}</button>
    {access && <div className="max-w-md">{asset.type === 'image' ? <img className="max-h-56 object-contain" src={getApiUrl(access.media)} alt={asset.description || asset.name} /> : asset.type === 'video' ? <video className="w-full max-h-56 bg-black" src={getApiUrl(access.media)} controls muted playsInline /> : <audio src={getApiUrl(access.media)} controls />}<p className="text-xs text-muted">{asset.width && `${asset.width} × ${asset.height} · `}{(asset.duration_ms / 1000).toFixed(1)}s · {asset.usage_notes || 'Usage rights not specified'}</p></div>}
  </div>;
}

function Metadata({ asset, request, action, refresh }) {
  const [fields, setFields] = useState({ tags: asset.tags.join(', '), description: asset.description, language: asset.language, source_label: asset.source_label, usage_notes: asset.usage_notes });
  return <details><summary>Edit tags and description</summary><div className="grid sm:grid-cols-2 gap-3 my-3">{[['tags', 'Tags (comma separated)'], ['description', 'Description of visible content'], ['language', 'Language'], ['source_label', 'Source label'], ['usage_notes', 'Usage / license notes']].map(([k, label]) => <label key={k} className="flex flex-col gap-1 text-sm">{label}<input maxLength={k === 'tags' ? 2500 : 1000} value={fields[k]} onChange={e => setFields({ ...fields, [k]: e.target.value })} /></label>)}</div><button className="btn-quiet" onClick={() => action(async () => { await request(`/api/edit-assets/${asset.id}`, { expected_version: asset.metadata_version, ...fields, tags: fields.tags.split(',').map(s => s.trim()).filter(Boolean) }, 'PATCH'); await refresh(); })}>Save asset metadata</button></details>;
}

export default function AssetLibrary({ assets, request, action, refresh }) {
  return <ul className="space-y-3">{assets.map(a => <li key={a.id} className="border border-rule rounded-lg p-3 space-y-2"><div className="flex justify-between gap-3"><strong className="break-all">{a.name}</strong><span className="composition-badge">{a.available === false ? 'Unavailable' : a.type}</span></div><p className="text-sm text-muted">{a.tags.join(' · ') || 'Add tags to enable passage matching'}</p><AssetInspector asset={a} request={request} action={action} /><Metadata key={`${a.id}:${a.metadata_version}`} asset={a} request={request} action={action} refresh={refresh} /><button className="btn-ghost" onClick={() => action(async () => { await request(`/api/edit-assets/${a.id}`, undefined, 'DELETE'); await refresh(); })}>Delete unreferenced asset</button></li>)}</ul>;
}
