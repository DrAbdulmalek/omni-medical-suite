'use client';

import React from 'react';
import type { ModelStatus, DeploymentStatus } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface StatusIndicatorProps {
  status: ModelStatus | DeploymentStatus;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  pulse?: boolean;
  className?: string;
}

// ============================================================================
// Style Maps
// ============================================================================

const STATUS_COLORS: Record<string, string> = {
  training: 'bg-green-500',
  completed: 'bg-blue-500',
  failed: 'bg-red-500',
  deployed: 'bg-green-500',
  pending: 'bg-yellow-500',
  active: 'bg-green-500',
  'rolling-back': 'bg-amber-500',
  queued: 'bg-gray-500',
  running: 'bg-green-500',
  cancelled: 'bg-gray-400',
};

const STATUS_LABELS: Record<string, string> = {
  training: 'Training',
  completed: 'Completed',
  failed: 'Failed',
  deployed: 'Deployed',
  pending: 'Pending',
  active: 'Active',
  'rolling-back': 'Rolling Back',
  queued: 'Queued',
  running: 'Running',
  cancelled: 'Cancelled',
};

const SIZE_MAP = {
  sm: { dot: 'h-2 w-2', text: 'text-xs', gap: 'gap-1.5' },
  md: { dot: 'h-2.5 w-2.5', text: 'text-sm', gap: 'gap-2' },
  lg: { dot: 'h-3 w-3', text: 'text-base', gap: 'gap-2.5' },
};

// ============================================================================
// Component
// ============================================================================

const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  size = 'md',
  showLabel = true,
  pulse = false,
  className = '',
}) => {
  const colorClass = STATUS_COLORS[status] || 'bg-gray-500';
  const label = STATUS_LABELS[status] || status;
  const sizeConfig = SIZE_MAP[size];
  const isAnimated = pulse || status === 'training' || status === 'running';

  return (
    <span className={`inline-flex items-center ${sizeConfig.gap} ${className}`}>
      <span className="relative flex">
        {isAnimated && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${colorClass}`}
          />
        )}
        <span
          className={`relative inline-flex rounded-full ${sizeConfig.dot} ${colorClass}`}
        />
      </span>
      {showLabel && (
        <span className={`font-medium capitalize text-gray-300 ${sizeConfig.text}`}>
          {label}
        </span>
      )}
    </span>
  );
};

export default StatusIndicator;
