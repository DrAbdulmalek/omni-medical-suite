'use client';

import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { TrainingMetrics } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface TrainingChartProps {
  metrics: TrainingMetrics[];
  title?: string;
  className?: string;
}

// ============================================================================
// Metric Toggle Type
// ============================================================================

type MetricKey = 'loss' | 'cer' | 'wer' | 'accuracy' | 'f1Score';

interface MetricOption {
  key: MetricKey;
  label: string;
  color: string;
  yAxisId: 'left' | 'right';
}

const METRIC_OPTIONS: MetricOption[] = [
  { key: 'loss', label: 'Loss', color: '#f97316', yAxisId: 'left' },
  { key: 'cer', label: 'CER', color: '#8b5cf6', yAxisId: 'right' },
  { key: 'wer', label: 'WER', color: '#ec4899', yAxisId: 'right' },
  { key: 'accuracy', label: 'Accuracy', color: '#22c55e', yAxisId: 'right' },
  { key: 'f1Score', label: 'F1 Score', color: '#06b6d4', yAxisId: 'right' },
];

// ============================================================================
// Custom Tooltip
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color: string }>;
  label?: number;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-xl">
      <p className="mb-2 text-xs font-semibold text-gray-300">Epoch {label}</p>
      <div className="space-y-1">
        {payload.map((entry) => (
          <div key={entry.dataKey} className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-gray-400">
              {entry.dataKey === 'valLoss'
                ? 'Val Loss'
                : entry.dataKey === 'loss'
                  ? 'Train Loss'
                  : entry.dataKey.charAt(0).toUpperCase() + entry.dataKey.slice(1)}
              :
            </span>
            <span className="font-mono font-medium text-white">
              {entry.dataKey === 'loss' || entry.dataKey === 'valLoss'
                ? entry.value.toFixed(4)
                : (entry.value * 100).toFixed(2)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// Component
// ============================================================================

const TrainingChart: React.FC<TrainingChartProps> = ({ metrics, title = 'Training Metrics', className = '' }) => {
  const [activeMetrics, setActiveMetrics] = useState<Set<MetricKey>>(
    new Set(['loss', 'cer', 'wer'])
  );
  const [showValLoss, setShowValLoss] = useState(true);
  const [epochRange, setEpochRange] = useState<[number, number]>([0, Infinity]);

  // Compute available epoch range
  const maxEpoch = useMemo(() => metrics.length > 0 ? metrics[metrics.length - 1].epoch : 100, [metrics]);

  const filteredMetrics = useMemo(
    () => metrics.filter((m) => m.epoch >= epochRange[0] && m.epoch <= epochRange[1]),
    [metrics, epochRange]
  );

  const toggleMetric = (key: MetricKey) => {
    setActiveMetrics((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (metrics.length === 0) {
    return (
      <div className={`flex h-64 items-center justify-center rounded-xl border border-gray-800 bg-gray-900/50 ${className}`}>
        <p className="text-gray-500">No metrics data available yet.</p>
      </div>
    );
  }

  const hasLeftAxis = activeMetrics.has('loss');
  const hasRightAxis = activeMetrics.size > 0 && !activeMetrics.has('loss');

  return (
    <div className={`rounded-xl border border-gray-800 bg-gray-900/50 p-5 ${className}`}>
      {/* Header */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-base font-semibold text-white">{title}</h3>

        {/* Metric toggles */}
        <div className="flex flex-wrap items-center gap-2">
          {METRIC_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => toggleMetric(opt.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                activeMetrics.has(opt.key)
                  ? 'text-white'
                  : 'bg-gray-800 text-gray-500 hover:text-gray-300'
              }`}
              style={
                activeMetrics.has(opt.key)
                  ? { backgroundColor: `${opt.color}20`, color: opt.color, borderColor: `${opt.color}40`, border: '1px solid' }
                  : {}
              }
            >
              {opt.label}
            </button>
          ))}
          {(activeMetrics.has('loss')) && (
            <button
              onClick={() => setShowValLoss(!showValLoss)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                showValLoss
                  ? 'bg-orange-500/20 text-orange-400 border border-orange-400/40'
                  : 'bg-gray-800 text-gray-500 hover:text-gray-300'
              }`}
            >
              Val Loss
            </button>
          )}
        </div>
      </div>

      {/* Epoch Range Selector */}
      <div className="mb-4 flex items-center gap-3">
        <span className="text-xs text-gray-500">Epoch range:</span>
        <input
          type="range"
          min={0}
          max={maxEpoch}
          value={epochRange[0]}
          onChange={(e) => setEpochRange([Number(e.target.value), epochRange[1]])}
          className="h-1 w-24 cursor-pointer appearance-none rounded-full bg-gray-700 accent-medical-blue"
        />
        <span className="font-mono text-xs text-gray-400">{epochRange[0]}</span>
        <span className="text-gray-600">–</span>
        <input
          type="range"
          min={0}
          max={maxEpoch}
          value={epochRange[1] === Infinity ? maxEpoch : epochRange[1]}
          onChange={(e) => setEpochRange([epochRange[0], Number(e.target.value)])}
          className="h-1 w-24 cursor-pointer appearance-none rounded-full bg-gray-700 accent-medical-blue"
        />
        <span className="font-mono text-xs text-gray-400">
          {epochRange[1] === Infinity ? maxEpoch : epochRange[1]}
        </span>
      </div>

      {/* Chart */}
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={filteredMetrics} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="epoch"
              stroke="#4b5563"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              label={{ value: 'Epoch', position: 'insideBottom', offset: -2, style: { fontSize: 11, fill: '#6b7280' } }}
            />
            {hasLeftAxis && (
              <YAxis
                yAxisId="left"
                stroke="#4b5563"
                tick={{ fontSize: 11, fill: '#9ca3af' }}
                label={{ value: 'Loss', angle: -90, position: 'insideLeft', style: { fontSize: 11, fill: '#6b7280' } }}
              />
            )}
            {hasRightAxis && (
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#4b5563"
                tick={{ fontSize: 11, fill: '#9ca3af' }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                label={{ value: 'Score', angle: 90, position: 'insideRight', style: { fontSize: 11, fill: '#6b7280' } }}
              />
            )}
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px', color: '#9ca3af' }}
              formatter={(value: string) => (
                <span style={{ color: '#d1d5db' }}>
                  {value === 'valLoss' ? 'Validation Loss' : value === 'loss' ? 'Training Loss' : value}
                </span>
              )}
            />

            {/* Lines */}
            {activeMetrics.has('loss') && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="loss"
                stroke="#f97316"
                strokeWidth={2}
                dot={false}
                name="loss"
              />
            )}
            {showValLoss && activeMetrics.has('loss') && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="valLoss"
                stroke="#fb923c"
                strokeWidth={1.5}
                strokeDasharray="5 5"
                dot={false}
                name="valLoss"
              />
            )}
            {activeMetrics.has('cer') && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="cer"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={false}
              />
            )}
            {activeMetrics.has('wer') && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="wer"
                stroke="#ec4899"
                strokeWidth={2}
                dot={false}
              />
            )}
            {activeMetrics.has('accuracy') && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="accuracy"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
              />
            )}
            {activeMetrics.has('f1Score') && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="f1Score"
                stroke="#06b6d4"
                strokeWidth={2}
                dot={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrainingChart;
