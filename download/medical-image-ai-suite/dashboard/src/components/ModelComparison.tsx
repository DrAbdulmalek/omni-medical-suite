'use client';

import React, { useMemo } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import type { TrainingModel, RadarDataPoint, MetricsDelta } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface ModelComparisonProps {
  modelA: TrainingModel;
  modelB: TrainingModel;
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

interface DeltaDisplay {
  label: string;
  delta: number;
  unit: string;
  lowerIsBetter: boolean;
}

function computeDelta(modelA: TrainingModel, modelB: TrainingModel): MetricsDelta {
  const mA = modelA.latestMetrics || (modelA.metrics.length > 0 ? modelA.metrics[modelA.metrics.length - 1] : null);
  const mB = modelB.latestMetrics || (modelB.metrics.length > 0 ? modelB.metrics[modelB.metrics.length - 1] : null);

  if (!mA || !mB) {
    return { cer: 0, wer: 0, loss: 0, accuracy: 0, f1Score: 0, inferenceTime: 0 };
  }

  return {
    cer: mB.cer - mA.cer,
    wer: mB.wer - mA.wer,
    loss: mB.loss - mA.loss,
    accuracy: mB.accuracy - mA.accuracy,
    f1Score: mB.f1Score - mA.f1Score,
    inferenceTime: (Math.random() - 0.5) * 40, // Simulated
  };
}

function computeRadarData(modelA: TrainingModel, modelB: TrainingModel): RadarDataPoint[] {
  const mA = modelA.latestMetrics || (modelA.metrics.length > 0 ? modelA.metrics[modelA.metrics.length - 1] : null);
  const mB = modelB.latestMetrics || (modelB.metrics.length > 0 ? modelB.metrics[modelB.metrics.length - 1] : null);

  if (!mA || !mB) return [];

  return [
    { metric: 'Accuracy', modelA: mA.accuracy * 100, modelB: mB.accuracy * 100, fullMark: 100 },
    { metric: 'CER', modelA: (1 - mA.cer) * 100, modelB: (1 - mB.cer) * 100, fullMark: 100 },
    { metric: 'WER', modelA: (1 - mA.wer) * 100, modelB: (1 - mB.wer) * 100, fullMark: 100 },
    { metric: 'F1 Score', modelA: mA.f1Score * 100, modelB: mB.f1Score * 100, fullMark: 100 },
    { metric: 'Speed', modelA: 85 + Math.random() * 10, modelB: 85 + Math.random() * 10, fullMark: 100 },
  ];
}

// ============================================================================
// Custom Tooltip
// ============================================================================

interface RadarTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

const RadarTooltip: React.FC<RadarTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload) return null;
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-xl">
      <p className="mb-1 text-xs font-semibold text-gray-300">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-xs">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-400">{entry.name}:</span>
          <span className="font-mono font-medium text-white">{entry.value.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
};

// ============================================================================
// Delta Row Component
// ============================================================================

const DeltaRow: React.FC<{ label: string; delta: number; unit: string; lowerIsBetter: boolean }> = ({
  label,
  delta,
  unit,
  lowerIsBetter,
}) => {
  const isPositive = lowerIsBetter ? delta < 0 : delta > 0;
  const isNeutral = Math.abs(delta) < 0.001;
  const icon = isNeutral ? (
    <Minus className="h-3.5 w-3.5 text-gray-400" />
  ) : isPositive ? (
    <ArrowUp className="h-3.5 w-3.5 text-green-400" />
  ) : (
    <ArrowDown className="h-3.5 w-3.5 text-red-400" />
  );

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-2">
        {icon}
        <span
          className={`font-mono text-sm font-medium ${
            isNeutral ? 'text-gray-400' : isPositive ? 'text-green-400' : 'text-red-400'
          }`}
        >
          {delta > 0 ? '+' : ''}
          {lowerIsBetter
            ? (Math.abs(delta) * 100).toFixed(2) + unit
            : (delta * 100).toFixed(2) + unit}
        </span>
      </div>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const ModelComparison: React.FC<ModelComparisonProps> = ({ modelA, modelB, className = '' }) => {
  const radarData = useMemo(() => computeRadarData(modelA, modelB), [modelA, modelB]);
  const delta = useMemo(() => computeDelta(modelA, modelB), [modelA, modelB]);

  const deltas: DeltaDisplay[] = [
    { label: 'Character Error Rate', delta: delta.cer, unit: '%', lowerIsBetter: true },
    { label: 'Word Error Rate', delta: delta.wer, unit: '%', lowerIsBetter: true },
    { label: 'Training Loss', delta: delta.loss, unit: '', lowerIsBetter: true },
    { label: 'Accuracy', delta: delta.accuracy, unit: '%', lowerIsBetter: false },
    { label: 'F1 Score', delta: delta.f1Score, unit: '%', lowerIsBetter: false },
  ];

  return (
    <div className={`rounded-xl border border-gray-800 bg-gray-900/50 p-5 ${className}`}>
      <h3 className="mb-4 text-base font-semibold text-white">Model Comparison</h3>

      {/* Model Headers */}
      <div className="mb-4 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-medical-blue" />
          <span className="text-sm font-medium text-gray-300">{modelA.name}</span>
        </div>
        <span className="text-gray-600">vs</span>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-medical-green" />
          <span className="text-sm font-medium text-gray-300">{modelB.name}</span>
        </div>
      </div>

      {/* Radar Chart */}
      {radarData.length > 0 && (
        <div className="mb-6 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
              <PolarGrid stroke="#374151" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Radar
                name={modelA.name}
                dataKey="modelA"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Radar
                name={modelB.name}
                dataKey="modelB"
                stroke="#22c55e"
                fill="#22c55e"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px' }}
                formatter={(value: string) => <span style={{ color: '#d1d5db' }}>{value}</span>}
              />
              <Tooltip content={<RadarTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Delta Table */}
      <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
        <p className="mb-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
          {modelB.name} relative to {modelA.name}
        </p>
        {deltas.map((d) => (
          <DeltaRow key={d.label} {...d} />
        ))}
      </div>
    </div>
  );
};

export default ModelComparison;
