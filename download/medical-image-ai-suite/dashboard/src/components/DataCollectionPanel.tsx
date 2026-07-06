'use client';

import React from 'react';
import {
  Database,
  CircleDot,
  BookOpen,
  GraduationCap,
  Cpu,
  Activity,
  Play,
  Pause,
  Plus,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import type { DataCollectionStats, CollectionActivity } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface DataCollectionPanelProps {
  stats: DataCollectionStats;
  activities: CollectionActivity[];
  onToggleCollection: () => void;
  className?: string;
}

// ============================================================================
// Circular Progress Component
// ============================================================================

interface CircularProgressProps {
  percentage: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
}

const CircularProgress: React.FC<CircularProgressProps> = ({
  percentage,
  size = 160,
  strokeWidth = 12,
  label,
  sublabel,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1f2937"
          strokeWidth={strokeWidth}
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="url(#progressGradient)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
        <defs>
          <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        {label && (
          <span className="text-2xl font-bold text-white">{label}</span>
        )}
        {sublabel && (
          <span className="mt-1 text-xs text-gray-400">{sublabel}</span>
        )}
      </div>
    </div>
  );
};

// ============================================================================
// Source Breakdown Bar
// ============================================================================

interface SourceBarProps {
  name: string;
  count: number;
  percentage: number;
  qualityScore: number;
  color: string;
  icon: React.ReactNode;
}

const SourceBar: React.FC<SourceBarProps> = ({ name, count, percentage, qualityScore, color, icon }) => {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span style={{ color }}>{icon}</span>
          <span className="text-sm font-medium text-gray-300">{name}</span>
        </div>
        <span className="font-mono text-xs text-gray-400">{count.toLocaleString()} samples</span>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-800">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${percentage}%`, backgroundColor: color }}
          />
        </div>
        <span className="text-xs font-medium text-gray-400">{percentage}%</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-[10px] text-gray-600">Quality: {qualityScore}/100</span>
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-1 w-4 rounded-full"
              style={{
                backgroundColor: i < Math.round(qualityScore / 20) ? color : '#1f2937',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Quality Gauge
// ============================================================================

const QualityGauge: React.FC<{ score: number }> = ({ score }) => {
  const getGrade = (s: number) => {
    if (s >= 95) return { grade: 'A+', color: '#22c55e' };
    if (s >= 90) return { grade: 'A', color: '#22c55e' };
    if (s >= 85) return { grade: 'B+', color: '#3b82f6' };
    if (s >= 80) return { grade: 'B', color: '#3b82f6' };
    if (s >= 70) return { grade: 'C', color: '#f59e0b' };
    return { grade: 'D', color: '#ef4444' };
  };
  const { grade, color } = getGrade(score);

  return (
    <div className="flex flex-col items-center rounded-lg border border-gray-800 bg-gray-950/50 p-4">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Quality Score</span>
      <div
        className="mt-2 flex h-16 w-16 items-center justify-center rounded-full border-2"
        style={{ borderColor: color }}
      >
        <span className="text-xl font-bold" style={{ color }}>
          {grade}
        </span>
      </div>
      <span className="mt-1 font-mono text-sm text-gray-300">{score.toFixed(1)}</span>
      <span className="text-[10px] text-gray-500">out of 100</span>
    </div>
  );
};

// ============================================================================
// Activity Timeline
// ============================================================================

interface ActivityTimelineProps {
  activities: CollectionActivity[];
}

const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ activities }) => {
  const getIcon = (type: CollectionActivity['type']) => {
    switch (type) {
      case 'added':
        return <Plus className="h-3.5 w-3.5 text-green-400" />;
      case 'validated':
        return <CheckCircle2 className="h-3.5 w-3.5 text-blue-400" />;
      case 'rejected':
        return <XCircle className="h-3.5 w-3.5 text-red-400" />;
      case 'augmented':
        return <RefreshCw className="h-3.5 w-3.5 text-purple-400" />;
    }
  };

  const timeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div className="space-y-3">
      {activities.map((activity) => (
        <div key={activity.id} className="flex items-start gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-800">
            {getIcon(activity.type)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-300">{activity.description}</p>
            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-gray-500">
              <span>{activity.source}</span>
              <span>•</span>
              <span>+{activity.count}</span>
              <span>•</span>
              <span>{timeAgo(activity.timestamp)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const DataCollectionPanel: React.FC<DataCollectionPanelProps> = ({
  stats,
  activities,
  onToggleCollection,
  className = '',
}) => {
  const progressPercent = Math.round((stats.totalSamples / stats.targetSamples) * 100);
  const remaining = stats.targetSamples - stats.totalSamples;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">Data Collection Pipeline</h3>
          <p className="text-sm text-gray-500">
            Target: {stats.targetSamples.toLocaleString()} samples for production training
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-950 px-3 py-1.5">
            <div className={`h-2 w-2 rounded-full ${stats.isCollecting ? 'animate-pulse bg-green-400' : 'bg-gray-500'}`} />
            <span className="text-xs text-gray-400">{stats.isCollecting ? 'Collecting' : 'Paused'}</span>
          </div>
          <button
            onClick={onToggleCollection}
            className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              stats.isCollecting
                ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20'
                : 'bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20'
            }`}
          >
            {stats.isCollecting ? (
              <>
                <Pause className="h-4 w-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Resume
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Circular Progress */}
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-800 bg-gray-900/50 p-6">
          <div className="relative">
            <CircularProgress
              percentage={progressPercent}
              size={180}
              strokeWidth={14}
              label={`${progressPercent}%`}
              sublabel="Complete"
            />
          </div>
          <div className="mt-4 text-center">
            <p className="text-lg font-bold text-white">
              {stats.totalSamples.toLocaleString()}{' '}
              <span className="text-sm font-normal text-gray-500">/ {stats.targetSamples.toLocaleString()}</span>
            </p>
            <p className="mt-1 text-xs text-gray-400">
              {remaining.toLocaleString()} samples remaining
            </p>
          </div>
        </div>

        {/* Source Breakdown */}
        <div className="space-y-3 lg:col-span-2">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Sources</h4>
          <SourceBar
            name="Digital Library"
            count={stats.digitalLibrary.count}
            percentage={stats.digitalLibrary.percentage}
            qualityScore={stats.digitalLibrary.qualityScore}
            color="#3b82f6"
            icon={<BookOpen className="h-4 w-4" />}
          />
          <SourceBar
            name="Academic Corpus"
            count={stats.academic.count}
            percentage={stats.academic.percentage}
            qualityScore={stats.academic.qualityScore}
            color="#8b5cf6"
            icon={<GraduationCap className="h-4 w-4" />}
          />
          <SourceBar
            name="Synthetic Data"
            count={stats.synthetic.count}
            percentage={stats.synthetic.percentage}
            qualityScore={stats.synthetic.qualityScore}
            color="#22c55e"
            icon={<Cpu className="h-4 w-4" />}
          />
        </div>
      </div>

      {/* Quality & Languages */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <QualityGauge score={stats.qualityScore} />

        <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Avg Resolution</span>
          <p className="mt-2 text-xl font-bold text-white">{stats.averageResolution}</p>
          <p className="text-[10px] text-gray-500">Across all sources</p>
        </div>

        <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Languages</span>
          <div className="mt-2 space-y-1.5">
            {stats.languages.map((lang) => (
              <div key={lang.code} className="flex items-center justify-between text-xs">
                <span className="text-gray-300">{lang.name}</span>
                <span className="font-mono text-gray-400">{lang.percentage}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Last Updated</span>
          <p className="mt-2 text-sm font-medium text-white">
            {new Date(stats.lastUpdated).toLocaleTimeString()}
          </p>
          <p className="text-[10px] text-gray-500">
            {new Date(stats.lastUpdated).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
        <div className="mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4 text-gray-400" />
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Recent Activity</h4>
        </div>
        <ActivityTimeline activities={activities} />
      </div>
    </div>
  );
};

export default DataCollectionPanel;
