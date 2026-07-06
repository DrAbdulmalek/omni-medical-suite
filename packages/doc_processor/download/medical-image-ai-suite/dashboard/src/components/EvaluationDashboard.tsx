'use client';

import React, { useState } from 'react';
import {
  Brain,
  Activity,
  Clock,
  Cpu,
  TrendingUp,
  CheckCircle2,
} from 'lucide-react';
import StatCard from './StatCard';
import ModelCard from './ModelCard';
import TrainingChart from './TrainingChart';
import MetricBadge from './MetricBadge';
import type { TrainingModel, TrainingMetrics } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface EvaluationDashboardProps {
  models: TrainingModel[];
  selectedModelId: string | null;
  selectedModelMetrics: TrainingMetrics[];
  onSelectModel: (modelId: string) => void;
  onDeploy: (modelId: string) => void;
  onCompare: (modelId: string) => void;
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function getOverallStats(models: TrainingModel[]) {
  const activeModels = models.filter((m) => m.status === 'training');
  const completedModels = models.filter((m) => m.status === 'completed' || m.status === 'deployed');
  const allMetrics = models.flatMap((m) => m.metrics);
  const latestMetrics = models
    .map((m) => m.latestMetrics)
    .filter((m): m is TrainingMetrics => m !== undefined);

  const avgCer = latestMetrics.length > 0
    ? latestMetrics.reduce((sum, m) => sum + m.cer, 0) / latestMetrics.length
    : 0;
  const avgAccuracy = latestMetrics.length > 0
    ? latestMetrics.reduce((sum, m) => sum + m.accuracy, 0) / latestMetrics.length
    : 0;

  return {
    totalModels: models.length,
    activeTraining: activeModels.length,
    completed: completedModels.length,
    avgCer,
    avgAccuracy,
    bestModel: latestMetrics.reduce((best, m) => (m.cer < (best?.cer ?? 1) ? m : best), null as TrainingMetrics | null),
  };
}

// ============================================================================
// Evaluation Results Table
// ============================================================================

interface ResultsRow {
  model: TrainingModel;
  metrics: TrainingMetrics | undefined;
}

const EvaluationResultsTable: React.FC<{ models: TrainingModel[] }> = ({ models }) => {
  const modelsWithMetrics = models
    .filter((m) => m.latestMetrics)
    .sort((a, b) => (a.latestMetrics?.cer ?? 1) - (b.latestMetrics?.cer ?? 1));

  if (modelsWithMetrics.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-gray-500">
        No evaluation results yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="pb-3 pr-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">Model</th>
            <th className="pb-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">CER</th>
            <th className="pb-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">WER</th>
            <th className="pb-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Accuracy</th>
            <th className="pb-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">F1 Score</th>
            <th className="pb-3 px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Loss</th>
            <th className="pb-3 pl-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
          </tr>
        </thead>
        <tbody>
          {modelsWithMetrics.map((model, idx) => {
            const m = model.latestMetrics!;
            return (
              <tr key={model.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-3 pr-4">
                  <div>
                    <span className="font-medium text-white">{model.name}</span>
                    {idx === 0 && (
                      <span className="ml-2 rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-400">
                        BEST
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">v{model.version}</span>
                </td>
                <td className="py-3 px-3 font-mono text-gray-300">{(m.cer * 100).toFixed(2)}%</td>
                <td className="py-3 px-3 font-mono text-gray-300">{(m.wer * 100).toFixed(2)}%</td>
                <td className="py-3 px-3 font-mono text-gray-300">{(m.accuracy * 100).toFixed(2)}%</td>
                <td className="py-3 px-3 font-mono text-gray-300">{(m.f1Score * 100).toFixed(2)}%</td>
                <td className="py-3 px-3 font-mono text-gray-300">{m.loss.toFixed(4)}</td>
                <td className="py-3 pl-3">
                  <MetricBadge label="" value={m.cer} unit="%" lowerIsBetter compact />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const EvaluationDashboard: React.FC<EvaluationDashboardProps> = ({
  models,
  selectedModelId,
  selectedModelMetrics,
  onSelectModel,
  onDeploy,
  onCompare,
  className = '',
}) => {
  const stats = getOverallStats(models);
  const selectedModel = models.find((m) => m.id === selectedModelId);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Overview Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Brain}
          title="Total Models"
          value={stats.totalModels}
          description={`${stats.activeTraining} training, ${stats.completed} completed`}
          trend={{ value: 25, isPositive: true }}
        />
        <StatCard
          icon={Activity}
          title="Avg CER"
          value={`${(stats.avgCer * 100).toFixed(2)}%`}
          description="Character Error Rate"
          trend={{ value: -12, isPositive: true }}
        />
        <StatCard
          icon={TrendingUp}
          title="Avg Accuracy"
          value={`${(stats.avgAccuracy * 100).toFixed(1)}%`}
          description="Across all evaluated models"
          trend={{ value: 3.5, isPositive: true }}
        />
        <StatCard
          icon={Cpu}
          title="GPU Hours"
          value="1,247"
          description="Total compute used"
          trend={{ value: 8, isPositive: false }}
        />
      </div>

      {/* Model Cards Grid */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Training Models
        </h3>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {models.map((model) => (
            <ModelCard
              key={model.id}
              model={model}
              isSelected={model.id === selectedModelId}
              onSelect={onSelectModel}
              onDeploy={onDeploy}
              onCompare={onCompare}
            />
          ))}
        </div>
      </div>

      {/* Selected Model Chart */}
      {selectedModel && (
        <TrainingChart
          metrics={selectedModelMetrics}
          title={`${selectedModel.name} — Training Curves`}
        />
      )}

      {/* Evaluation Results Table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
        <div className="mb-4 flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-medical-green" />
          <h3 className="text-base font-semibold text-white">Evaluation Results</h3>
        </div>
        <EvaluationResultsTable models={models} />
      </div>
    </div>
  );
};

export default EvaluationDashboard;
