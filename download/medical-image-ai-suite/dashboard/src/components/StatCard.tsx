'use client';

import React from 'react';
import { type LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

// ============================================================================
// Props
// ============================================================================

interface StatCardProps {
  icon: LucideIcon;
  title: string;
  value: string | number;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

const StatCard: React.FC<StatCardProps> = ({
  icon: Icon,
  title,
  value,
  description,
  trend,
  className = '',
}) => {
  return (
    <div
      className={`group relative overflow-hidden rounded-xl border border-gray-800 bg-gray-900/50 p-5 backdrop-blur-sm transition-all duration-300 hover:border-gray-700 hover:bg-gray-900/80 hover:shadow-lg hover:shadow-black/20 ${className}`}
    >
      {/* Background glow on hover */}
      <div className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 rounded-full bg-medical-blue/5 transition-all duration-500 group-hover:scale-150 group-hover:bg-medical-blue/10" />

      <div className="relative flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-400">{title}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-white">{value}</p>
          {description && (
            <p className="mt-1 text-xs text-gray-500">{description}</p>
          )}
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-medical-blue/10">
          <Icon className="h-5 w-5 text-medical-blue" />
        </div>
      </div>

      {trend && (
        <div className="relative mt-3 flex items-center gap-1.5">
          {trend.isPositive ? (
            <TrendingUp className="h-4 w-4 text-green-400" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-400" />
          )}
          <span
            className={`text-sm font-medium ${trend.isPositive ? 'text-green-400' : 'text-red-400'}`}
          >
            {trend.value > 0 ? '+' : ''}
            {trend.value}%
          </span>
          <span className="text-xs text-gray-500">vs last week</span>
        </div>
      )}
    </div>
  );
};

export default StatCard;
