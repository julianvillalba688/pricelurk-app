import React from 'react';
import type { Product } from '../types';
import { Trash2 } from 'lucide-react';

interface ProductCardProps {
  product: Product;
  onDelete: (id: number) => void;
  onClick: (id: number) => void;
}

const ProductCard: React.FC<ProductCardProps> = ({ product, onDelete, onClick }) => {
  const isTargetReached = product.current_price <= product.target_price;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow cursor-pointer" onClick={() => onClick(product.id)}>
      <div className="relative h-48 bg-gray-100 flex items-center justify-center p-4">
        <img src={product.image_url} alt={product.title} className="max-h-full object-contain mix-blend-multiply" />
        {isTargetReached && (
          <span className="absolute top-2 right-2 bg-green-500 text-white text-xs font-bold px-2 py-1 rounded-full">Target Reached</span>
        )}
      </div>
      <div className="p-4">
        <div className="flex justify-between items-start gap-2">
          <h3 className="font-semibold text-gray-800 line-clamp-2" title={product.title}>{product.title}</h3>
          <button 
            onClick={(e) => {
              e.stopPropagation();
              onDelete(product.id);
            }} 
            className="text-gray-400 hover:text-red-500 p-1 rounded transition-colors"
            title="Delete product"
          >
            <Trash2 size={18} />
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-1">{product.platform}</p>
        <div className="mt-4 flex items-end justify-between">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Current</p>
            <p className={`text-xl font-bold ${isTargetReached ? 'text-green-600' : 'text-gray-900'}`}>${product.current_price.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Target</p>
            <p className="text-sm font-medium text-gray-700">${product.target_price.toFixed(2)}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProductCard;
