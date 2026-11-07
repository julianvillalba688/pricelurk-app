import type { Product } from '../types';
import { money } from '../services/money';

interface Props {
  product: Product;
  onDelete: (id: number) => void;
  onClick: (id: number) => void;
  canWrite: boolean;
  busy: boolean;
}

export default function ProductCard({ product, onDelete, onClick, canWrite, busy }: Props) {
  return <article className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
    <p className="text-sm text-gray-500 mb-2">{product.platform} · {product.source === 'demo' ? 'DEMO' : product.source === 'legacy_unverified' ? 'Dato antiguo no verificado' : 'Observado'}</p>
    <button onClick={() => onClick(product.id)} className="font-semibold text-left text-blue-700 hover:underline">{product.title || 'Producto sin título'}</button>
    <p className="text-xs text-gray-500 mt-5">Precio actual</p>
    <p className="text-xl font-bold">{money(product.current_price, product.currency)}</p>
    <p className="text-sm mt-2">Objetivo: {money(product.target_price, product.target_currency)}</p>
    {!product.target_currency && <p className="text-xs mt-2 text-amber-800">Objetivo antiguo sin moneda: alertas deshabilitadas. Vuelve a agregarlo con una moneda verificada.</p>}
    <div className="mt-5 flex justify-between text-sm"><button className="text-blue-700" onClick={() => onClick(product.id)}>Ver historial</button><button disabled={!canWrite || busy} className="text-red-700 disabled:opacity-40" onClick={() => onDelete(product.id)}>Eliminar</button></div>
  </article>;
}
