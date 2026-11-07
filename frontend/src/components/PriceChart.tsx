import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import type { PriceSnapshot } from '../types';

interface PriceChartProps {
  data: PriceSnapshot[];
  targetPrice?: number;
  currency: string;
}

const PriceChart: React.FC<PriceChartProps> = ({ data, targetPrice, currency }) => {
  const formattedData = data.map(snapshot => ({
    ...snapshot,
    price: Number(snapshot.price),
    date: new Date(snapshot.timestamp).toLocaleString(),
  }));

  return (
    <div className="w-full h-48 mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={formattedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{fontSize: 12}} />
          <YAxis tick={{fontSize: 12}} domain={['auto', 'auto']} />
          <Tooltip formatter={value => `${value} ${currency}`} />
          <Line type="linear" dataKey="price" name={currency} stroke="#3b82f6" strokeWidth={2} dot={true} isAnimationActive={false} />
          {targetPrice && (
            <ReferenceLine y={targetPrice} label="Target" stroke="red" strokeDasharray="3 3" />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PriceChart;
