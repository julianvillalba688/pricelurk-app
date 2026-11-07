import { useState } from 'react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (url: string, target: string, currency: string) => Promise<void>;
}

export default function AddProductModal({ isOpen, onClose, onSubmit }: Props) {
  const [url, setUrl] = useState('');
  const [target, setTarget] = useState('');
  const [currency, setCurrency] = useState('USD');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  if (!isOpen) return null;
  return <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
    <form role="dialog" aria-modal="true" aria-labelledby="add-title" className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4" onSubmit={async e => {
      e.preventDefault(); setLoading(true); setError('');
      try { await onSubmit(url, target, currency); setUrl(''); setTarget(''); onClose(); }
      catch { setError('No se pudo agregar. Verifica la clave, la URL, la moneda y que la tienda publique un precio compatible.'); }
      finally { setLoading(false); }
    }}>
      <h2 id="add-title" className="font-bold text-xl">Agregar producto</h2>
      <p className="text-sm text-gray-600">Amazon (.com/.es), Mercado Libre Colombia y AliExpress. Requiere moneda explícita en la página.</p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <label className="block">URL del producto<input className="border rounded p-2 w-full" type="url" required value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.amazon.com/dp/..." /></label>
      <label className="block">Moneda del objetivo<select className="border rounded p-2 w-full" value={currency} onChange={e => setCurrency(e.target.value)}>{['USD', 'EUR', 'COP', 'JPY'].map(c => <option key={c}>{c}</option>)}</select></label>
      <label className="block">Precio objetivo<input className="border rounded p-2 w-full" type="number" min={currency === 'JPY' ? '1' : '0.01'} step={currency === 'JPY' ? '1' : '0.01'} required value={target} onChange={e => setTarget(e.target.value)} /></label>
      <div className="flex gap-4"><button className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50" disabled={loading}>{loading ? 'Verificando…' : 'Guardar producto'}</button><button type="button" onClick={onClose} disabled={loading}>Cancelar</button></div>
    </form>
  </div>;
}
