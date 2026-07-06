'use client';

import React, { useState } from 'react';
import {
  Rocket,
  ArrowRightLeft,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Server,
  Trash2,
  ChevronDown,
  Activity,
} from 'lucide-react';
import StatusIndicator from './StatusIndicator';
import type { Deployment, DeploymentStrategy, TrainingModel } from '@/types';

// ============================================================================
// Props
// ============================================================================

interface DeploymentManagerProps {
  deployments: Deployment[];
  models: TrainingModel[];
  onDeployModel: (modelId: string, strategy: DeploymentStrategy) => void;
  onRollback: (deploymentId: string) => void;
  className?: string;
}

// ============================================================================
// Health Status Icons
// ============================================================================

const HealthIcon: React.FC<{ status: 'passing' | 'warning' | 'critical' }> = ({ status }) => {
  switch (status) {
    case 'passing':
      return <ShieldCheck className="h-4 w-4 text-green-400" />;
    case 'warning':
      return <ShieldAlert className="h-4 w-4 text-yellow-400" />;
    case 'critical':
      return <ShieldAlert className="h-4 w-4 text-red-400" />;
  }
};

// ============================================================================
// Strategy Badge
// ============================================================================

const StrategyBadge: React.FC<{ strategy: DeploymentStrategy }> = ({ strategy }) => {
  const styles: Record<DeploymentStrategy, string> = {
    canary: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    'blue-green': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    rolling: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  };
  const icons: Record<DeploymentStrategy, string> = {
    canary: '🐦',
    'blue-green': '🔄',
    rolling: '⏩',
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[strategy]}`}>
      <span>{icons[strategy]}</span>
      {strategy === 'blue-green' ? 'Blue-Green' : strategy.charAt(0).toUpperCase() + strategy.slice(1)}
    </span>
  );
};

// ============================================================================
// Deployment Card
// ============================================================================

interface DeploymentCardProps {
  deployment: Deployment;
  onRollback: (deploymentId: string) => void;
  onTrafficChange: (deploymentId: string, percent: number) => void;
}

const DeploymentCard: React.FC<DeploymentCardProps> = ({ deployment, onRollback, onTrafficChange }) => {
  const [expanded, setExpanded] = useState(true);

  const passingChecks = deployment.healthChecks.filter((h) => h.status === 'passing').length;
  const totalChecks = deployment.healthChecks.length;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 overflow-hidden">
      {/* Header */}
      <div
        className="flex cursor-pointer items-center justify-between p-4 hover:bg-gray-800/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <Server className="h-5 w-5 text-gray-400" />
          <div>
            <h4 className="text-sm font-semibold text-white">{deployment.modelName}</h4>
            <div className="mt-0.5 flex items-center gap-2">
              <span className="font-mono text-xs text-gray-500">v{deployment.modelVersion}</span>
              <StrategyBadge strategy={deployment.strategy} />
              <StatusIndicator status={deployment.status} size="sm" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {deployment.strategy === 'canary' && (
            <span className="font-mono text-sm font-medium text-white">
              {deployment.trafficPercent}% traffic
            </span>
          )}
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-800 p-4 space-y-4">
          {/* Health Checks */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Health Checks</span>
              <span className={`text-xs font-medium ${passingChecks === totalChecks ? 'text-green-400' : 'text-yellow-400'}`}>
                {passingChecks}/{totalChecks} passing
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {deployment.healthChecks.map((hc) => (
                <div
                  key={hc.name}
                  className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-950/50 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <HealthIcon status={hc.status} />
                    <span className="text-xs text-gray-300">{hc.name}</span>
                  </div>
                  <span className="font-mono text-xs text-gray-400">
                    {hc.name.includes('Latency')
                      ? `${hc.latency.toFixed(0)}ms`
                      : `${(hc.latency * 100).toFixed(2)}%`}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Traffic Slider (Canary only) */}
          {deployment.strategy === 'canary' && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Traffic Distribution</span>
                <span className="font-mono text-sm font-medium text-white">{deployment.trafficPercent}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={deployment.trafficPercent}
                onChange={(e) => onTrafficChange(deployment.id, Number(e.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded-full bg-gray-700 accent-medical-blue"
              />
              <div className="mt-1 flex justify-between text-[10px] text-gray-600">
                <span>0%</span>
                <span>25%</span>
                <span>50%</span>
                <span>75%</span>
                <span>100%</span>
              </div>
            </div>
          )}

          {/* Endpoint */}
          <div className="flex items-center gap-2 rounded-lg bg-gray-950/50 px-3 py-2">
            <span className="text-xs text-gray-500">Endpoint:</span>
            <span className="font-mono text-xs text-medical-blue">{deployment.endpoint}</span>
          </div>

          {/* Timeline */}
          {deployment.timeline.length > 0 && (
            <div>
              <span className="mb-2 block text-xs font-semibold text-gray-400 uppercase tracking-wider">Timeline</span>
              <div className="space-y-2">
                {deployment.timeline.map((event, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="flex flex-col items-center">
                      <div className="h-2 w-2 rounded-full bg-medical-blue" />
                      {idx < deployment.timeline.length - 1 && (
                        <div className="h-6 w-px bg-gray-800" />
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-300">{event.description}</p>
                      <p className="text-[10px] text-gray-500">
                        {new Date(event.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2">
            {deployment.status === 'active' && (
              <button
                onClick={() => onRollback(deployment.id)}
                className="flex items-center gap-1.5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <ArrowRightLeft className="h-3.5 w-3.5" />
                Rollback
              </button>
            )}
            <span className="ml-auto text-[10px] text-gray-600">
              Created: {new Date(deployment.createdAt).toLocaleDateString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// New Deployment Form
// ============================================================================

interface NewDeploymentFormProps {
  models: TrainingModel[];
  onSubmit: (modelId: string, strategy: DeploymentStrategy) => void;
}

const NewDeploymentForm: React.FC<NewDeploymentFormProps> = ({ models, onSubmit }) => {
  const [selectedModelId, setSelectedModelId] = useState('');
  const [strategy, setStrategy] = useState<DeploymentStrategy>('canary');

  const deployableModels = models.filter((m) => m.status === 'completed' || m.status === 'deployed');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedModelId) return;
    onSubmit(selectedModelId, strategy);
    setSelectedModelId('');
  };

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Rocket className="h-5 w-5 text-medical-blue" />
        <h3 className="text-base font-semibold text-white">New Deployment</h3>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Model Select */}
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Select Model</label>
          <select
            value={selectedModelId}
            onChange={(e) => setSelectedModelId(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white focus:border-medical-blue focus:outline-none focus:ring-1 focus:ring-medical-blue"
          >
            <option value="">Choose a model...</option>
            {deployableModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} (v{m.version})
              </option>
            ))}
          </select>
        </div>

        {/* Strategy Select */}
        <div>
          <label className="mb-2 block text-xs font-medium text-gray-400">Deployment Strategy</label>
          <div className="grid grid-cols-3 gap-2">
            {([
              { value: 'canary' as const, label: 'Canary', desc: 'Gradual traffic shift', icon: '🐦' },
              { value: 'blue-green' as const, label: 'Blue-Green', desc: 'Instant switchover', icon: '🔄' },
              { value: 'rolling' as const, label: 'Rolling', desc: 'Gradual replacement', icon: '⏩' },
            ]).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setStrategy(opt.value)}
                className={`rounded-lg border p-3 text-center transition-colors ${
                  strategy === opt.value
                    ? 'border-medical-blue bg-medical-blue/10'
                    : 'border-gray-700 bg-gray-950 hover:border-gray-600'
                }`}
              >
                <span className="text-lg">{opt.icon}</span>
                <p className={`mt-1 text-xs font-semibold ${strategy === opt.value ? 'text-medical-blue' : 'text-gray-300'}`}>
                  {opt.label}
                </p>
                <p className="text-[10px] text-gray-500">{opt.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={!selectedModelId}
          className="w-full rounded-lg bg-medical-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-medical-blue/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Deploy Model
        </button>
      </form>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

const DeploymentManager: React.FC<DeploymentManagerProps> = ({
  deployments,
  models,
  onDeployModel,
  onRollback,
  className = '',
}) => {
  const handleTrafficChange = (_deploymentId: string, _percent: number) => {
    // In production this would call an API
    console.log(`Traffic change: ${_deploymentId} -> ${_percent}%`);
  };

  const activeDeployments = deployments.filter((d) => d.status === 'active' || d.status === 'rolling-back');
  const pastDeployments = deployments.filter((d) => d.status === 'completed' || d.status === 'failed');

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Summary Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex items-center gap-3 rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
            <Activity className="h-5 w-5 text-green-400" />
          </div>
          <div>
            <p className="text-xs text-gray-400">Active Deployments</p>
            <p className="text-xl font-bold text-white">{activeDeployments.length}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
            <Shield className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-gray-400">Avg Health Score</p>
            <p className="text-xl font-bold text-white">98.2%</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
            <Clock className="h-5 w-5 text-purple-400" />
          </div>
          <div>
            <p className="text-xs text-gray-400">Last Deployment</p>
            <p className="text-sm font-bold text-white">2 hours ago</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Active Deployments */}
        <div className="lg:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Active Deployments</h3>
          {activeDeployments.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded-xl border border-gray-800 bg-gray-900/50 text-gray-500">
              No active deployments
            </div>
          ) : (
            activeDeployments.map((dep) => (
              <DeploymentCard
                key={dep.id}
                deployment={dep}
                onRollback={onRollback}
                onTrafficChange={handleTrafficChange}
              />
            ))
          )}

          {/* Past Deployments */}
          {pastDeployments.length > 0 && (
            <>
              <h3 className="mt-6 text-sm font-semibold text-gray-400 uppercase tracking-wider">Past Deployments</h3>
              {pastDeployments.map((dep) => (
                <DeploymentCard
                  key={dep.id}
                  deployment={dep}
                  onRollback={onRollback}
                  onTrafficChange={handleTrafficChange}
                />
              ))}
            </>
          )}
        </div>

        {/* New Deployment Form */}
        <div>
          <NewDeploymentForm models={models} onSubmit={onDeployModel} />
        </div>
      </div>
    </div>
  );
};

export default DeploymentManager;
