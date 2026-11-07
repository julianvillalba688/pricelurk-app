import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import api from '../services/api';
import { money } from '../services/money';
import type { History, Product, Status } from '../types';
import ProductCard from '../components/ProductCard';
import AddProductModal from '../components/AddProductModal';

const PriceChart = lazy(() => import('../components/PriceChart'));

export default function Dashboard() {
  const [products, setProducts] = useState<Product[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(false);
  const [key, setKey] = useState('');
  const [selected, setSelected] = useState<Product | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [busy, setBusy] = useState(false);
  const [historyVersion, setHistoryVersion] = useState(0);
  const canWrite = Boolean(status?.writes_enabled && key);
  const headers = { 'X-API-Key': key };

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [list, info] = await Promise.all([api.get<Product[]>('/products'), api.get<Status>('/status')]);
      setProducts(list.data); setStatus(info.data);
    } catch { setError('No se pudo conectar con la API. Comprueba que esté iniciada e inténtalo de nuevo.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const selectedId = selected?.id;
  useEffect(() => {
    setHistory(null); setHistoryError('');
    if (!selectedId) return;
    const controller = new AbortController();
    setHistoryLoading(true);
    api.get<History>(`/products/${selectedId}/history`, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setHistory(result.data); })
      .catch(() => { if (!controller.signal.aborted) setHistoryError('No se pudo cargar el historial.'); })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false); });
    return () => controller.abort();
  }, [selectedId, historyVersion]);

  async function remove(id: number) {
    setBusy(true); setError('');
    try { await api.delete(`/products/${id}`, { headers }); if (selectedId === id) setSelected(null); await load(); }
    catch { setError('No se pudo eliminar el producto. Verifica la conexión y la clave de acceso.'); }
    finally { setBusy(false); }
  }
  async function refresh() {
    if (!selectedId) return;
    setBusy(true); setError('');
    try {
      const result = await api.post<Product>(`/products/${selectedId}/refresh`, {}, { headers });
      setSelected(result.data); setHistoryVersion(v => v + 1); await load();
    } catch { setError('No se pudo actualizar. La tienda puede estar bloqueando la consulta o no ofrecer precio y moneda compatibles.'); }
    finally { setBusy(false); }
  }

  return <div className="min-h-screen bg-gray-50 text-gray-900">
    <header className="bg-white border-b"><div className="max-w-7xl mx-auto p-5 flex flex-wrap items-center justify-between gap-4">
      <h1 className="text-2xl font-bold text-blue-700">PriceLurk</h1><div className="flex flex-wrap items-center gap-3">
        {status?.writes_enabled && <label className="text-sm">Clave de escritura <input aria-label="Clave de escritura" type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} className="border rounded p-2" /></label>}
        <button disabled={!canWrite || busy} onClick={() => setModal(true)} className="bg-blue-600 text-white rounded-lg px-4 py-2 disabled:opacity-40">Agregar producto</button>
      </div>
    </div></header>
    <main className="max-w-7xl mx-auto p-5 lg:p-8">
      <h2 className="text-xl font-semibold">Seguimiento de precios</h2>
      <p className="text-gray-600 mt-1 mb-5">{status?.demo ? 'Ejemplos sintéticos para explorar la interfaz.' : 'Observaciones verificadas, con precio y moneda.'} Sin cuentas ni perfiles personales.</p>
      {status?.demo && <p role="status" className="bg-amber-100 p-3 rounded mb-4 font-semibold">Modo DEMO: datos sintéticos de ejemplo, separados de datos reales. Solo lectura.</p>}
      {status && !status.notifications_enabled && <p className="bg-blue-50 p-3 rounded mb-4">Notificaciones de Telegram deshabilitadas. Puedes consultar productos e historial.</p>}
      {status && !status.writes_enabled && <p className="text-sm text-gray-600 mb-4">Solo lectura. Las operaciones de escritura están deshabilitadas.</p>}
      {loading && <p role="status">Cargando productos…</p>}
      {error && <div role="alert" className="bg-red-50 text-red-800 p-4 rounded mb-4">{error} <button className="underline" onClick={() => void load()}>Reintentar</button></div>}
      {!loading && !error && products.length === 0 && <div className="bg-white border border-dashed p-10 rounded-xl text-center">Todavía no hay productos. Agrega una URL compatible para comenzar.</div>}
      <div className="flex flex-col lg:flex-row gap-6"><div className="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 content-start">
        {products.map(product => <ProductCard key={product.id} product={product} canWrite={canWrite} busy={busy} onDelete={id => void remove(id)} onClick={id => setSelected(products.find(p => p.id === id) || null)} />)}
      </div>
      {selected && <aside className="bg-white rounded-xl border p-5 lg:w-96 h-fit">
        <h3 className="font-bold">{selected.title}</h3><p className="text-sm text-gray-500 mt-2 mb-4">Historial · {selected.currency || 'moneda desconocida'}</p>
        {historyLoading && <p role="status">Cargando historial…</p>}
        {historyError && <p role="alert">{historyError} <button className="underline" onClick={() => setHistoryVersion(v => v + 1)}>Reintentar historial</button></p>}
        {history && <>
          {history.excluded_legacy_count > 0 && <p className="text-sm text-amber-800 mb-3">{history.excluded_legacy_count} registros antiguos conservados y excluidos: procedencia o moneda sin verificar.</p>}
          {history.history.length === 0 ? <p>Aún no hay observaciones verificadas.</p> : <>
            <p className="text-sm">{history.history.length} observaciones{history.source === 'demo' ? ' sintéticas (DEMO)' : ' reales'}</p>
            {history.stats && <dl className="text-sm space-y-1 mt-3"><div>Mínimo: {money(history.stats.lowest_price, history.stats.currency)}</div><div>Máximo: {money(history.stats.highest_price, history.stats.currency)}</div><div>Promedio: {money(history.stats.average_price, history.stats.currency)}</div></dl>}
            <Suspense fallback={<p>Cargando gráfica…</p>}><PriceChart data={history.history} currency={selected.currency || ''} targetPrice={selected.target_currency === selected.currency ? Number(selected.target_price) : undefined} /></Suspense>
          </>}
        </>}
        <button disabled={!canWrite || busy} className="mt-5 text-blue-700 disabled:opacity-40" onClick={() => void refresh()}>{busy ? 'Actualizando…' : 'Actualizar precio'}</button>
      </aside>}
      </div>
    </main>
    <AddProductModal isOpen={modal} onClose={() => setModal(false)} onSubmit={async (url, target, currency) => { await api.post('/products/track', { url, target_price: target, currency }, { headers }); await load(); }} />
  </div>;
}
