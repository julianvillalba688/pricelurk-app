import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';
import type { PriceSnapshot } from '../types';

interface PriceChartProps {
  data: PriceSnapshot[];
  targetPrice?: number;
}

const PriceChart: React.FC<PriceChartProps> = ({ data, targetPrice }) => {
  const formattedData = data.map(snapshot => ({
    ...snapshot,
    date: new Date(snapshot.timestamp).toLocaleDateString(),
  }));

  return (
    <div className="w-full h-48 mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={formattedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{fontSize: 12}} />
          <YAxis tick={{fontSize: 12}} domain={['auto', 'auto']} />
          <Tooltip />
          <Line type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} dot={false} />
          {targetPrice && (
            <ReferenceLine y={targetPrice} label="Target" stroke="red" strokeDasharray="3 3" />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PriceChart;
