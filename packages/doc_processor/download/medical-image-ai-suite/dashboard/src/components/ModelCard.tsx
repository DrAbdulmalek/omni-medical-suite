'use client';

import React from 'react';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { Eye, Rocket, GitCompareArrows, MoreVertical } from 'lucide-react';
import StatusIndicator from './StatusIndicator';
import MetricBadge from './MetricBadge';
import type { TrainingModel } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface ModelCardProps {
  model: TrainingModel;
  isSelected?: boolean;
  onSelect?: (modelId: string) => void;
  onDeploy?: (modelId: string) => void;
  onCompare?: (modelId: string) => void;
  onViewDetails?: (modelId: string) => void;
}

// ============================================================================
// Helpers
// ============================================================================

function getProgress(model: TrainingModel): number {
  if (model.totalEpochs === 0) return 0;
  return Math.round((model.currentEpoch / model.totalEpochs) * 100);
}

function getProgressColor(progress: number): string {
  if (progress >= 100) return 'bg-green-500';
  if (progress >= 50) return 'bg-medical-blue';
  if (progress >= 25) return 'bg-yellow-500';
  return 'bg-red-500';
}

// ============================================================================
// Component
// ============================================================================

const ModelCard: React.FC<ModelCardProps> = ({
  model,
  isSelected = false,
  onSelect,
  onDeploy,
  onCompare,
  onViewDetails,
}) => {
  const progress = getProgress(model);
  const lastMetrics = model.latestMetrics || (model.metrics.length > 0 ? model.metrics[model.metrics.length - 1] : null);
  const sparklineData = model.metrics.slice(-10).map((m) => ({ loss: m.loss }));
  const canDeploy = model.status === 'completed' || model.status === 'deployed';

  return (
    <div
      onClick={() => onSelect?.(model.id)}
      className={`group relative rounded-xl border p-5 transition-all duration-200 ${
        isSelected
          ? 'border-medical-blue bg-medical-blue/5 shadow-lg shadow-medical-blue/10'
          : 'border-gray-800 bg-gray-900/50 hover:border-gray-700 hover:bg-gray-900/80'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-base font-semibold text-white">{model.name}</h3>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="rounded-md bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400">
              v{model.version}
            </span>
            <StatusIndicator status={model.status} size="sm" />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            onClick={(e) => { e.stopPropagation(); onViewDetails?.(model.id); }}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
            title="View Details"
          >
            <Eye className="h-4 w-4" />
          </button>
          {canDeploy && (
            <button
              onClick={(e) => { e.stopPropagation(); onDeploy?.(model.id); }}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-green-500/10 hover:text-green-400"
              title="Deploy"
            >
              <Rocket className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onCompare?.(model.id); }}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white"
            title="Compare"
          >
            <GitCompareArrows className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Description */}
      <p className="mt-2 line-clamp-2 text-xs text-gray-500">{model.description}</p>

      {/* Metrics Row */}
      {lastMetrics && (
        <div className="mt-3 grid grid-cols-3 gap-2">
          <MetricBadge label="CER" value={lastMetrics.cer} unit="%" lowerIsBetter compact />
          <MetricBadge label="WER" value={lastMetrics.wer} unit="%" lowerIsBetter compact />
          <MetricBadge label="Loss" value={lastMetrics.loss} unit="" lowerIsBetter compact />
        </div>
      )}

      {/* Progress Bar */}
      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs text-gray-400">
            Epoch {model.currentEpoch}/{model.totalEpochs}
          </span>
          <span className="text-xs font-medium text-gray-300">{progress}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-800">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getProgressColor(progress)}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Sparkline */}
      {sparklineData.length > 1 && (
        <div className="mt-3 h-12 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparklineData}>
              <YAxis domain={['auto', 'auto']} hide />
              <Line
                type="monotone"
                dataKey="loss"
                stroke="#3b82f6"
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tags */}
      <div className="mt-3 flex flex-wrap gap-1">
        {model.tags.slice(0, 4).map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400"
          >
            {tag}
          </span>
        ))}
        {model.tags.length > 4 && (
          <span className="rounded-full bg-gray-800 px-2 py-0.5 text-[10px] text-gray-500">
            +{model.tags.length - 4}
          </span>
        )}
      </div>
    </div>
  );
};

export default ModelCard;
