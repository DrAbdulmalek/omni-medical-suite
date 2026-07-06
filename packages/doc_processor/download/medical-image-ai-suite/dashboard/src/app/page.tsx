'use client';

import React, { useState, useMemo } from 'react';
import {
  Brain,
  BarChart3,
  Rocket,
  Database,
  Wifi,
  WifiOff,
  RefreshCw,
  Settings,
  Bell,
  Search,
  Moon,
  GitCompareArrows,
} from 'lucide-react';
import useWebSocket from '@/hooks/useWebSocket';
import useTrainingData from '@/hooks/useTrainingData';
import EvaluationDashboard from '@/components/EvaluationDashboard';
import DeploymentManager from '@/components/DeploymentManager';
import DataCollectionPanel from '@/components/DataCollectionPanel';
import ModelComparison from '@/components/ModelComparison';

// ============================================================================
// Tab Definitions
// ============================================================================

type TabId = 'training' | 'evaluation' | 'deployment' | 'data';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const TABS: Tab[] = [
  { id: 'training', label: 'Training', icon: <Brain className="h-4 w-4" /> },
  { id: 'evaluation', label: 'Evaluation', icon: <BarChart3 className="h-4 w-4" /> },
  { id: 'deployment', label: 'Deployment', icon: <Rocket className="h-4 w-4" /> },
  { id: 'data', label: 'Data Collection', icon: <Database className="h-4 w-4" /> },
];

// ============================================================================
// Main Page Component
// ============================================================================

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabId>('training');
  const [compareModelIds, setCompareModelIds] = useState<[string, string] | null>(null);
  const [showComparison, setShowComparison] = useState(false);

  // WebSocket connection
  const { isConnected, reconnect } = useWebSocket();

  // Training data (demo mode by default)
  const {
    models,
    deployments,
    selectedModelMetrics,
    dataStats,
    collectionActivities,
    isLoading,
    selectedModelId,
    setSelectedModelId,
    selectModel,
    fetchModels,
    deployModel,
    rollbackDeployment,
    toggleCollection,
    startTraining,
    stopTraining,
  } = useTrainingData(true);

  // Handle model compare
  const handleCompare = (modelId: string) => {
    if (compareModelIds === null) {
      setCompareModelIds([modelId, '']);
    } else if (compareModelIds[1] === '') {
      if (compareModelIds[0] !== modelId) {
        setCompareModelIds([compareModelIds[0], modelId]);
        setShowComparison(true);
      }
    } else {
      setCompareModelIds([modelId, '']);
      setShowComparison(false);
    }
  };

  const comparisonModels = useMemo(() => {
    if (!compareModelIds || !compareModelIds[1]) return null;
    const mA = models.find((m) => m.id === compareModelIds[0]);
    const mB = models.find((m) => m.id === compareModelIds[1]);
    if (!mA || !mB) return null;
    return { modelA: mA, modelB: mB };
  }, [compareModelIds, models]);

  return (
    <div className="min-h-screen bg-gray-950">
      {/* ================================================================= */}
      {/* Header                                                             */}
      {/* ================================================================= */}
      <header className="sticky top-0 z-50 border-b border-gray-800 bg-gray-950/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Left: Logo & Title */}
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-medical-blue/10 border border-medical-blue/20">
                <Brain className="h-5 w-5 text-medical-blue" />
              </div>
              <div>
                <h1 className="text-base font-bold text-white leading-tight">
                  OmniMedical
                  <span className="ml-1.5 text-medical-blue">Training</span>
                </h1>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider">
                  Arabic Medical OCR Dashboard
                </p>
              </div>
            </div>

            {/* Center: Search (hidden on mobile) */}
            <div className="hidden md:flex items-center">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search models, deployments..."
                  className="h-9 w-72 rounded-lg border border-gray-800 bg-gray-900 pl-9 pr-3 text-sm text-white placeholder-gray-500 focus:border-medical-blue focus:outline-none focus:ring-1 focus:ring-medical-blue/30"
                />
              </div>
            </div>

            {/* Right: Status & Controls */}
            <div className="flex items-center gap-3">
              {/* Connection Status */}
              <button
                onClick={reconnect}
                className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900 px-3 py-1.5 text-xs transition-colors hover:border-gray-700"
                title={isConnected ? 'WebSocket Connected' : 'WebSocket Disconnected — Click to reconnect'}
              >
                {isConnected ? (
                  <>
                    <Wifi className="h-3.5 w-3.5 text-green-400" />
                    <span className="text-green-400">Live</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3.5 w-3.5 text-red-400" />
                    <span className="text-red-400">Demo</span>
                  </>
                )}
              </button>

              {/* Notifications */}
              <button className="relative rounded-lg border border-gray-800 bg-gray-900 p-1.5 text-gray-400 hover:text-white transition-colors">
                <Bell className="h-4 w-4" />
                <span className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[8px] font-bold text-white">
                  3
                </span>
              </button>

              {/* Refresh */}
              <button
                onClick={() => fetchModels()}
                className="rounded-lg border border-gray-800 bg-gray-900 p-1.5 text-gray-400 hover:text-white transition-colors"
                title="Refresh data"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </button>

              {/* Settings */}
              <button className="rounded-lg border border-gray-800 bg-gray-900 p-1.5 text-gray-400 hover:text-white transition-colors">
                <Settings className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* ================================================================= */}
      {/* Tab Navigation                                                     */}
      {/* ================================================================= */}
      <div className="border-b border-gray-800 bg-gray-950/50">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-1 overflow-x-auto py-2 -mb-px">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setShowComparison(false);
                }}
                className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-medical-blue/10 text-medical-blue border border-medical-blue/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`}
              >
                {tab.icon}
                {tab.label}
                {tab.id === 'training' && (
                  <span className="ml-1 rounded-full bg-gray-800 px-1.5 py-0.5 text-[10px] font-mono text-gray-400">
                    {models.filter((m) => m.status === 'training').length}
                  </span>
                )}
                {tab.id === 'deployment' && (
                  <span className="ml-1 rounded-full bg-gray-800 px-1.5 py-0.5 text-[10px] font-mono text-gray-400">
                    {deployments.filter((d) => d.status === 'active').length}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ================================================================= */}
      {/* Main Content                                                       */}
      {/* ================================================================= */}
      <main className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
        {/* Training Tab (combined with Evaluation) */}
        {(activeTab === 'training' || activeTab === 'evaluation') && (
          <div className="space-y-6">
            {showComparison && comparisonModels ? (
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                  Model Comparison
                </h2>
                <button
                  onClick={() => { setShowComparison(false); setCompareModelIds(null); }}
                  className="text-xs text-gray-500 hover:text-gray-300"
                >
                  Close comparison
                </button>
              </div>
            ) : null}

            {showComparison && comparisonModels ? (
              <ModelComparison modelA={comparisonModels.modelA} modelB={comparisonModels.modelB} />
            ) : (
              <EvaluationDashboard
                models={models}
                selectedModelId={selectedModelId}
                selectedModelMetrics={selectedModelMetrics}
                onSelectModel={selectModel}
                onDeploy={deployModel}
                onCompare={handleCompare}
              />
            )}
          </div>
        )}

        {/* Deployment Tab */}
        {activeTab === 'deployment' && (
          <DeploymentManager
            deployments={deployments}
            models={models}
            onDeployModel={deployModel}
            onRollback={rollbackDeployment}
          />
        )}

        {/* Data Collection Tab */}
        {activeTab === 'data' && (
          <DataCollectionPanel
            stats={dataStats}
            activities={collectionActivities}
            onToggleCollection={toggleCollection}
          />
        )}
      </main>

      {/* ================================================================= */}
      {/* Footer                                                             */}
      {/* ================================================================= */}
      <footer className="border-t border-gray-800 bg-gray-950/50 py-4">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-2 sm:flex-row">
            <p className="text-xs text-gray-600">
              OmniMedical AI Training Dashboard v2.0 — Arabic Medical OCR
            </p>
            <p className="text-xs text-gray-600">
              {isConnected ? '🟢 Connected to live training backend' : '🟡 Running in demo mode with simulated data'}
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
