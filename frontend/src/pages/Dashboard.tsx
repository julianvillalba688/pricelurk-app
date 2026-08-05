import React, { useState, useEffect } from 'react';
import api from '../services/api';
import type { Product, PriceSnapshot } from '../types';
import ProductCard from '../components/ProductCard';
import AddProductModal from '../components/AddProductModal';
import PriceChart from '../components/PriceChart';
import { Plus, Activity, RefreshCw } from 'lucide-react';

const Dashboard: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [historyData, setHistoryData] = useState<PriceSnapshot[]>([]);
  const [historyStats, setHistoryStats] = useState<any>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchProducts = async () => {
    try {
      const response = await api.get('/products');
      setProducts(response.data);
    } catch (error) {
      console.error('Failed to fetch products', error);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchHistory = async (id: number) => {
    try {
      const response = await api.get(`/products/${id}/history`);
      setHistoryData(response.data.history || []);
      setHistoryStats(response.data.stats || null);
    } catch (error) {
      console.error('Failed to fetch history', error);
    }
  };

  const handleAddProduct = async (url: string, targetPrice: number) => {
    await api.post('/products/track', { url, target_price: targetPrice });
    fetchProducts();
  };

  const handleDeleteProduct = async (id: number) => {
    try {
      await api.delete(`/products/${id}`);
      fetchProducts();
      if (selectedProduct?.id === id) {
        setSelectedProduct(null);
      }
    } catch (error) {
      console.error('Failed to delete product', error);
    }
  };

  const handleProductClick = async (id: number) => {
    const product = products.find(p => p.id === id);
    if (product) {
      setSelectedProduct(product);
      await fetchHistory(id);
    }
  };

  const handleRefresh = async () => {
    if (!selectedProduct) return;
    setIsRefreshing(true);
    try {
      const response = await api.post(`/products/${selectedProduct.id}/refresh`);
      setSelectedProduct(response.data);
      await fetchHistory(selectedProduct.id);
      await fetchProducts();
    } catch (error) {
      console.error('Failed to refresh product', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 text-blue-600">
            <Activity size={28} />
            <h1 className="text-xl font-bold tracking-tight text-gray-900">PriceLurk</h1>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} /> Add Product
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-8">
        <div className="flex-1">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Tracked Products</h2>
            <p className="text-sm text-gray-500">Monitoring {products.length} items for price drops.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {products.map(product => (
              <ProductCard
                key={product.id}
                product={product}
                onDelete={handleDeleteProduct}
                onClick={handleProductClick}
              />
            ))}
            {products.length === 0 && (
              <div className="col-span-full bg-white border border-dashed border-gray-300 rounded-xl p-12 text-center">
                <p className="text-gray-500 mb-4">You are not tracking any products yet.</p>
                <button onClick={() => setIsModalOpen(true)} className="text-blue-600 font-medium hover:underline">
                  Start tracking now
                </button>
              </div>
            )}
          </div>
        </div>

        {selectedProduct && (
          <aside className="w-full md:w-96 bg-white rounded-xl shadow-sm border border-gray-100 p-6 h-fit sticky top-24">
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-gray-900 line-clamp-1 flex-1">{selectedProduct.title}</h3>
              <button
                onClick={handleRefresh}
                disabled={isRefreshing}
                title="Actualizar precio"
                className="ml-2 p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-4">Price History</p>
            {historyStats && (
              <div className="flex flex-wrap gap-2 mb-4 text-xs">
                <span className="bg-green-100 text-green-800 px-2 py-1 rounded font-medium">
                  🟢 Min: ${historyStats.lowest_price?.toFixed(2)}
                </span>
                <span className="bg-red-100 text-red-800 px-2 py-1 rounded font-medium">
                  🔴 Max: ${historyStats.highest_price?.toFixed(2)}
                </span>
                <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded font-medium">
                  🔵 Prom: ${historyStats.average_price?.toFixed(2)}
                </span>
              </div>
            )}
            {historyData.length > 0 ? (
              <PriceChart data={historyData} targetPrice={selectedProduct.target_price} />
            ) : (
              <p className="text-sm text-gray-400 text-center py-10">Cargando historial...</p>
            )}
            <div className="mt-6 pt-6 border-t border-gray-100 flex justify-between text-sm">
              <span className="text-gray-500">Target Price:</span>
              <span className="font-semibold text-gray-900">${selectedProduct.target_price.toFixed(2)}</span>
            </div>
          </aside>
        )}
      </main>

      <AddProductModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleAddProduct}
      />
    </div>
  );
};

export default Dashboard;
