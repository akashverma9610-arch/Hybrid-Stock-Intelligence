import React, { DragEvent, useEffect, useRef, useState } from 'react';
import { ImagePlus, LoaderCircle, Trash2, X } from 'lucide-react';
import { useDataClient } from '../../api/context';
import { PortfolioImportDraft, ReviewedPortfolioHolding } from '../../types/portfolio';
import { formatINR } from '../../utils/formatters';

type PendingImage = { file: File; preview: string };
const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const MAX_IMAGES = 5;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export const PortfolioScreenshotImportModal: React.FC<{ onClose: () => void; onConfirmed: (snapshotId: string) => void }> = ({ onClose, onConfirmed }) => {
  const { client, isMockMode } = useDataClient();
  const [images, setImages] = useState<PendingImage[]>([]);
  const [draft, setDraft] = useState<PortfolioImportDraft | null>(null);
  const [rows, setRows] = useState<ReviewedPortfolioHolding[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const previewUrls = useRef(new Set<string>());

  useEffect(() => () => previewUrls.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const addFiles = (files: FileList | File[]) => {
    const valid: PendingImage[] = [];
    for (const file of Array.from(files)) {
      if (!ALLOWED_TYPES.has(file.type)) { setMessage('Only JPG, PNG, and WebP images are supported.'); continue; }
      if (file.size === 0 || file.size > MAX_IMAGE_BYTES) { setMessage('Each image must be non-empty and no larger than 5 MB.'); continue; }
      if (images.length + valid.length >= MAX_IMAGES) { setMessage(`You can upload at most ${MAX_IMAGES} screenshots.`); break; }
      const preview = URL.createObjectURL(file); previewUrls.current.add(preview);
      valid.push({ file, preview });
    }
    if (valid.length) setImages((current) => [...current, ...valid]);
  };
  const removeImage = (index: number) => setImages((current) => {
    URL.revokeObjectURL(current[index].preview); previewUrls.current.delete(current[index].preview);
    return current.filter((_, itemIndex) => itemIndex !== index);
  });
  const extract = async () => {
    if (!images.length) { setMessage('Add at least one screenshot before extraction.'); return; }
    setLoading(true); setMessage(null);
    const response = await client.uploadPortfolioScreenshots(images.map((image) => image.file));
    setLoading(false);
    if (!response.data) { setMessage(response.message ?? 'Screenshot extraction is unavailable.'); return; }
    setDraft(response.data);
    setRows(response.data.holdings.map((holding) => ({ rowId: holding.rowId, instrumentId: holding.instrumentId, symbol: holding.symbol, quantity: holding.quantity, averagePrice: holding.averagePrice, include: holding.resolutionStatus === 'MATCHED' })));
  };
  const updateRow = (rowId: string, patch: Partial<ReviewedPortfolioHolding>) => setRows((current) => current.map((row) => row.rowId === rowId ? { ...row, ...patch } : row));
  const addRow = () => setRows((current) => [...current, { rowId: `manual-${crypto.randomUUID()}`, instrumentId: null, symbol: '', quantity: null, averagePrice: null, include: true }]);
  const cancel = async () => {
    if (draft?.importId) await client.cancelPortfolioImport(draft.importId);
    onClose();
  };
  const confirm = async () => {
    if (!draft) return;
    setLoading(true); setMessage(null);
    const response = await client.confirmPortfolioImport(draft.importId, rows);
    setLoading(false);
    if (!response.data) { setMessage(response.message ?? 'The reviewed portfolio could not be imported.'); return; }
    setMessage(`Imported ${response.data.holdingsImported} reviewed holdings. Analysis will be available after the backend analysis cycle processes them.`);
    onConfirmed(response.data.portfolioSnapshotId);
  };
  const onDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); addFiles(event.dataTransfer.files); };
  const sourceCandidate = (rowId: string) => draft?.holdings.find((holding) => holding.rowId === rowId);

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-3" role="dialog" aria-modal="true" aria-label="Import Portfolio Screenshot" onPaste={(event) => addFiles(event.clipboardData.files)}>
    <div className="max-h-[92vh] w-full max-w-6xl overflow-y-auto rounded-xl bg-white p-5 shadow-2xl dark:bg-slate-900">
      <div className="mb-4 flex items-start justify-between gap-4"><div><h2 className="text-lg font-bold">Import Portfolio Screenshot</h2><p className="mt-1 text-sm text-slate-500">Upload screenshots from your broker portfolio. Extracted holdings will be shown for review before anything is saved.</p>{isMockMode && <p className="mt-1 text-xs font-semibold text-amber-600">MOCK DATA — synthetic extraction only</p>}</div><button aria-label="Close import" onClick={cancel}><X /></button></div>
      {!draft && <><div onDragOver={(event) => event.preventDefault()} onDrop={onDrop} className="rounded-lg border-2 border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><ImagePlus className="mx-auto mb-2 text-emerald-600"/><p className="text-sm">Drag screenshots here, paste from clipboard, or choose files.</p><label className="mt-3 inline-block cursor-pointer rounded bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Choose images<input aria-label="Portfolio screenshots" className="hidden" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => event.target.files && addFiles(event.target.files)} /></label><p className="mt-2 text-xs text-slate-500">JPG, PNG, or WebP · max {MAX_IMAGES} images · 5 MB each</p></div>
      {images.length > 0 && <div className="mt-4 flex flex-wrap gap-3">{images.map((image, index) => <div className="relative" key={`${image.file.name}-${index}`}><img src={image.preview} alt="Selected screenshot preview" className="h-20 w-28 rounded object-cover"/><button className="absolute -right-2 -top-2 rounded-full bg-white p-1 shadow dark:bg-slate-800" aria-label={`Remove image ${index + 1}`} onClick={() => removeImage(index)}><Trash2 className="h-3 w-3"/></button></div>)}</div>}
      <button disabled={loading || !images.length} onClick={extract} className="mt-4 rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? 'Extracting…' : 'Extract holdings for review'}</button></>}
      {draft && <div><div className="mb-3 flex items-center justify-between"><div><p className="font-semibold text-amber-600">Not saved yet</p><p className="text-xs text-slate-500">Review and correct every row. Ambiguous or unmatched symbols require a canonical instrument ID; the app never guesses one.</p></div><button onClick={addRow} className="rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold dark:border-slate-700">Add missing holding</button></div>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b"><th className="p-2">Use</th><th>Symbol / name</th><th>Canonical instrument ID</th><th>Qty</th><th>Average price</th><th>Screenshot LTP</th><th>Confidence / warnings</th><th /></tr></thead><tbody>{rows.map((row) => { const candidate = sourceCandidate(row.rowId); return <tr className="border-b align-top" key={row.rowId}><td className="p-2"><input type="checkbox" checked={row.include} onChange={(event) => updateRow(row.rowId, { include: event.target.checked })}/></td><td className="p-2"><input aria-label="Symbol" value={row.symbol ?? ''} onChange={(event) => updateRow(row.rowId, { symbol: event.target.value })} className="w-28 rounded border p-1 dark:bg-slate-800"/><div className="mt-1 text-slate-500">{candidate?.instrumentName ?? 'Manual row'} · {candidate?.resolutionStatus ?? 'MANUAL'}</div></td><td className="p-2"><input aria-label="Canonical instrument ID" value={row.instrumentId ?? ''} onChange={(event) => updateRow(row.rowId, { instrumentId: event.target.value || null })} placeholder="Required" className="w-36 rounded border p-1 dark:bg-slate-800"/></td><td className="p-2"><input aria-label="Quantity" type="number" min="0" value={row.quantity ?? ''} onChange={(event) => updateRow(row.rowId, { quantity: event.target.value === '' ? null : Number(event.target.value) })} className="w-20 rounded border p-1 dark:bg-slate-800"/></td><td className="p-2"><input aria-label="Average price" type="number" min="0" value={row.averagePrice ?? ''} onChange={(event) => updateRow(row.rowId, { averagePrice: event.target.value === '' ? null : Number(event.target.value) })} className="w-24 rounded border p-1 dark:bg-slate-800"/></td><td className="p-2">{formatINR(candidate?.currentPrice ?? null)}</td><td className="p-2">{candidate?.extractionConfidence !== null && candidate?.extractionConfidence !== undefined ? `${Math.round(candidate.extractionConfidence * 100)}%` : '—'}<div className="mt-1 text-amber-600">{candidate?.warnings.join(' · ')}</div></td><td className="p-2"><button aria-label="Remove holding" onClick={() => setRows((current) => current.filter((item) => item.rowId !== row.rowId))}><Trash2 className="h-3 w-3"/></button></td></tr>; })}</tbody></table></div>
        <div className="mt-4 flex gap-2"><button onClick={cancel} className="rounded border border-slate-300 px-4 py-2 text-sm dark:border-slate-700">Cancel</button><button disabled={loading || !rows.some((row) => row.include)} onClick={confirm} className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? 'Saving…' : 'Confirm reviewed portfolio (Replace)'}</button></div></div>}
      {loading && <LoaderCircle className="mt-3 h-4 w-4 animate-spin text-emerald-600"/>}{message && <p role="status" className="mt-3 text-sm text-slate-600 dark:text-slate-300">{message}</p>}
    </div>
  </div>;
};
