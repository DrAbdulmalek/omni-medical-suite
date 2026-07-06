'use client';

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { Trend } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface MetricBadgeProps {
  label: string;
  value: number;
  unit?: string;
  trend?: Trend;
  compact?: boolean;
  /** Whether lower values are better (e.g., CER, WER, Loss) */
  lowerIsBetter?: boolean;
  className?: string;
}

// ============================================================================
// Helpers
// ============================================================================

function getColor(value: number, lowerIsBetter: boolean): string {
  if (lowerIsBetter) {
    if (value <= 0.05) return 'text-green-400';
    if (value <= 0.15) return 'text-yellow-400';
    return 'text-red-400';
  }
  if (value >= 0.95) return 'text-green-400';
  if (value >= 0.85) return 'text-yellow-400';
  return 'text-red-400';
}

function getBgColor(value: number, lowerIsBetter: boolean): string {
  if (lowerIsBetter) {
    if (value <= 0.05) return 'bg-green-500/10 border-green-500/20';
    if (value <= 0.15) return 'bg-yellow-500/10 border-yellow-500/20';
    return 'bg-red-500/10 border-red-500/20';
  }
  if (value >= 0.95) return 'bg-green-500/10 border-green-500/20';
  if (value >= 0.85) return 'bg-yellow-500/10 border-yellow-500/20';
  return 'bg-red-500/10 border-red-500/20';
}

function getTrendIcon(trend?: Trend) {
  switch (trend) {
    case 'up':
      return <TrendingUp className="h-3 w-3 text-green-400" />;
    case 'down':
      return <TrendingDown className="h-3 w-3 text-red-400" />;
    case 'stable':
      return <Minus className="h-3 w-3 text-gray-400" />;
    default:
      return null;
  }
}

// ============================================================================
// Component
// ============================================================================

const MetricBadge: React.FC<MetricBadgeProps> = ({
  label,
  value,
  unit = '%',
  trend,
  compact = false,
  lowerIsBetter = false,
  className = '',
}) => {
  const displayValue = lowerIsBetter
    ? value < 0.01
      ? value.toFixed(4)
      : value < 1
        ? `${(value * 100).toFixed(1)}${unit === '%' ? '%' : unit}`
        : value.toFixed(2)
    : `${(value * 100).toFixed(1)}${unit}`;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-xs ${getBgColor(value, lowerIsBetter)} ${getColor(value, lowerIsBetter)} ${className}`}
      >
        {trend && getTrendIcon(trend)}
        {label}: {displayValue}
      </span>
    );
  }

  return (
    <div
      className={`flex flex-col rounded-lg border p-3 ${getBgColor(value, lowerIsBetter)} ${className}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400">{label}</span>
        {trend && getTrendIcon(trend)}
      </div>
      <span className={`mt-1 font-mono text-lg font-bold ${getColor(value, lowerIsBetter)}`}>
        {displayValue}
      </span>
    </div>
  );
};

export default MetricBadge;
