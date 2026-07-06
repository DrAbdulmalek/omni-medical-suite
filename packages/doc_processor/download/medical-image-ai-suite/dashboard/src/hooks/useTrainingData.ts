'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  TrainingModel,
  TrainingMetrics,
  TrainingConfig,
  Deployment,
  DeploymentStrategy,
  DataCollectionStats,
  CollectionActivity,
  TrainingJob,
  ModelStatus,
  JobStatus,
  MetricUpdatePayload,
  WebSocketMessage,
} from '@/types';

// ============================================================================
// Seed / Mock Data Generators
// ============================================================================

function generateMetrics(
  startEpoch: number,
  endEpoch: number,
  baseLoss = 3.5,
  noise = 0.05
): TrainingMetrics[] {
  const metrics: TrainingMetrics[] = [];
  for (let e = startEpoch; e <= endEpoch; e++) {
    const progress = e / endEpoch;
    const decay = Math.exp(-3 * progress);
    const lr = 0.001 * (1 - progress * 0.8);
    metrics.push({
      epoch: e,
      loss: Math.max(0.01, baseLoss * decay + (Math.random() - 0.5) * noise * baseLoss),
      valLoss: Math.max(0.01, baseLoss * decay * 1.15 + (Math.random() - 0.5) * noise * baseLoss * 1.2),
      cer: Math.max(0.001, 0.35 * decay + (Math.random() - 0.5) * 0.01),
      wer: Math.max(0.001, 0.55 * decay + (Math.random() - 0.5) * 0.015),
      accuracy: Math.min(0.99, 0.99 - 0.6 * decay + (Math.random() - 0.5) * 0.01),
      f1Score: Math.min(0.99, 0.98 - 0.55 * decay + (Math.random() - 0.5) * 0.01),
      learningRate: lr,
      timestamp: new Date(Date.now() - (endEpoch - e) * 600_000).toISOString(),
    });
  }
  return metrics;
}

const DEFAULT_CONFIG: TrainingConfig = {
  batchSize: 32,
  learningRate: 0.001,
  optimizer: 'AdamW',
  scheduler: 'CosineAnnealing',
  architecture: 'TrOCR-Large',
  backbone: 'ViT-Large',
  maxTextLength: 128,
  augmentation: ['Rotation', 'ElasticDistortion', 'GaussianNoise', 'Contrast'],
  mixedPrecision: true,
  gradientCheckpointing: true,
};

function createSeedModels(): TrainingModel[] {
  const completedMetrics = generateMetrics(1, 50);
  const trainingMetrics = generateMetrics(1, 32);

  return [
    {
      id: 'model-001',
      name: 'ArabicOCR-TrOCR-v3',
      version: '3.0.0',
      description: 'Production TrOCR model trained on Arabic medical prescriptions and lab reports.',
      status: 'deployed',
      metrics: completedMetrics,
      latestMetrics: completedMetrics[completedMetrics.length - 1],
      totalEpochs: 50,
      currentEpoch: 50,
      createdAt: '2024-11-15T08:00:00Z',
      updatedAt: '2024-11-20T14:30:00Z',
      config: { ...DEFAULT_CONFIG, architecture: 'TrOCR-Large', batchSize: 48 },
      tags: ['production', 'arabic', 'medical'],
    },
    {
      id: 'model-002',
      name: 'ArabicOCR-TrOCR-v4-beta',
      version: '4.0.0-beta.2',
      description: 'Next-gen model with augmented synthetic data and improved backbone.',
      status: 'training',
      metrics: trainingMetrics,
      latestMetrics: trainingMetrics[trainingMetrics.length - 1],
      totalEpochs: 60,
      currentEpoch: 32,
      createdAt: '2024-12-01T10:00:00Z',
      updatedAt: new Date().toISOString(),
      config: { ...DEFAULT_CONFIG, architecture: 'TrOCR-XLarge', batchSize: 24, learningRate: 0.0005 },
      tags: ['beta', 'arabic', 'medical', 'xlarge'],
    },
    {
      id: 'model-003',
      name: 'ArabicOCR-PaddleOCR-finetune',
      version: '2.1.0',
      description: 'Fine-tuned PaddleOCR for Arabic script with custom tokenizer.',
      status: 'completed',
      metrics: generateMetrics(1, 40, 4.0),
      latestMetrics: undefined,
      totalEpochs: 40,
      currentEpoch: 40,
      createdAt: '2024-10-20T06:00:00Z',
      updatedAt: '2024-10-24T12:00:00Z',
      config: { ...DEFAULT_CONFIG, architecture: 'PaddleOCR-SVTR', optimizer: 'Adam', batchSize: 64 },
      tags: ['paddleocr', 'arabic', 'finetune'],
    },
    {
      id: 'model-004',
      name: 'ArabicOCR-Multimodal-v1',
      version: '1.0.0-alpha',
      description: 'Experimental multimodal model combining text and layout understanding.',
      status: 'pending',
      metrics: [],
      latestMetrics: undefined,
      totalEpochs: 80,
      currentEpoch: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      config: { ...DEFAULT_CONFIG, architecture: 'Donut-base', maxTextLength: 256 },
      tags: ['experimental', 'multimodal', 'alpha'],
    },
    {
      id: 'model-005',
      name: 'ArabicOCR-SATRN-v2',
      version: '2.0.0',
      description: 'SATRN-based model with stage-wise attention for complex layouts.',
      status: 'failed',
      metrics: generateMetrics(1, 18, 5.0, 0.15),
      latestMetrics: undefined,
      totalEpochs: 45,
      currentEpoch: 18,
      createdAt: '2024-11-28T09:00:00Z',
      updatedAt: '2024-11-30T02:15:00Z',
      config: { ...DEFAULT_CONFIG, architecture: 'SATRN', scheduler: 'StepLR' },
      tags: ['satrn', 'arabic', 'failed'],
    },
  ];
}

function createSeedDeployments(): Deployment[] {
  return [
    {
      id: 'deploy-001',
      modelId: 'model-001',
      modelName: 'ArabicOCR-TrOCR-v3',
      modelVersion: '3.0.0',
      strategy: 'blue-green',
      status: 'active',
      trafficPercent: 100,
      endpoint: 'https://api.omnimed.ai/v2/ocr/arabic',
      createdAt: '2024-11-21T08:00:00Z',
      updatedAt: new Date().toISOString(),
      healthChecks: [
        { name: 'Latency P50', status: 'passing', latency: 145, lastCheck: new Date().toISOString() },
        { name: 'Latency P99', status: 'passing', latency: 320, lastCheck: new Date().toISOString() },
        { name: 'Error Rate', status: 'passing', latency: 0.02, lastCheck: new Date().toISOString() },
        { name: 'GPU Memory', status: 'warning', latency: 87, lastCheck: new Date().toISOString() },
      ],
      timeline: [
        { timestamp: '2024-11-21T08:00:00Z', action: 'deploy_started', description: 'Blue-Green deployment initiated' },
        { timestamp: '2024-11-21T08:15:00Z', action: 'green_ready', description: 'Green environment healthy' },
        { timestamp: '2024-11-21T08:20:00Z', action: 'traffic_switched', description: '100% traffic routed to green' },
        { timestamp: '2024-11-21T08:25:00Z', action: 'blue_retired', description: 'Blue environment scaled down' },
      ],
    },
    {
      id: 'deploy-002',
      modelId: 'model-002',
      modelName: 'ArabicOCR-TrOCR-v4-beta',
      modelVersion: '4.0.0-beta.2',
      strategy: 'canary',
      status: 'active',
      trafficPercent: 10,
      endpoint: 'https://api.omnimed.ai/v2-beta/ocr/arabic',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      healthChecks: [
        { name: 'Latency P50', status: 'passing', latency: 168, lastCheck: new Date().toISOString() },
        { name: 'Latency P99', status: 'passing', latency: 385, lastCheck: new Date().toISOString() },
        { name: 'Error Rate', status: 'passing', latency: 0.05, lastCheck: new Date().toISOString() },
        { name: 'GPU Memory', status: 'warning', latency: 92, lastCheck: new Date().toISOString() },
      ],
      timeline: [
        { timestamp: new Date().toISOString(), action: 'canary_started', description: 'Canary deployment at 10% traffic' },
      ],
    },
  ];
}

function createSeedDataStats(): DataCollectionStats {
  return {
    totalSamples: 38420,
    targetSamples: 50000,
    digitalLibrary: { count: 11526, percentage: 30, qualityScore: 94 },
    academic: { count: 7684, percentage: 20, qualityScore: 91 },
    synthetic: { count: 19210, percentage: 50, qualityScore: 87 },
    qualityScore: 90.5,
    averageResolution: '300 DPI',
    languages: [
      { code: 'ar', name: 'Arabic', count: 32000, percentage: 83.3 },
      { code: 'ar-en', name: 'Arabic + English', count: 4500, percentage: 11.7 },
      { code: 'en', name: 'English', count: 1920, percentage: 5.0 },
    ],
    lastUpdated: new Date().toISOString(),
    isCollecting: true,
  };
}

function createSeedActivities(): CollectionActivity[] {
  const now = Date.now();
  return [
    { id: 'act-1', timestamp: new Date(now - 30_000).toISOString(), source: 'Digital Library', count: 12, type: 'added', description: '12 new prescription images from MOH digital archive' },
    { id: 'act-2', timestamp: new Date(now - 120_000).toISOString(), source: 'Synthetic Generator', count: 50, type: 'augmented', description: '50 augmented prescription variants generated' },
    { id: 'act-3', timestamp: new Date(now - 300_000).toISOString(), source: 'Academic Corpus', count: 8, type: 'validated', description: '8 academic paper figures validated' },
    { id: 'act-4', timestamp: new Date(now - 600_000).toISOString(), source: 'Quality Gate', count: 3, type: 'rejected', description: '3 low-resolution samples rejected (<150 DPI)' },
    { id: 'act-5', timestamp: new Date(now - 900_000).toISOString(), source: 'Digital Library', count: 25, type: 'added', description: '25 lab report images from hospital partner' },
    { id: 'act-6', timestamp: new Date(now - 1_500_000).toISOString(), source: 'Synthetic Generator', count: 100, type: 'added', description: 'Batch of 100 synthetic handwritten prescriptions created' },
  ];
}

function createSeedJobs(): TrainingJob[] {
  return [
    {
      id: 'job-001',
      modelName: 'ArabicOCR-TrOCR-v4-beta',
      modelId: 'model-002',
      status: 'running',
      progress: 53.3,
      startTime: '2024-12-01T10:00:00Z',
      config: DEFAULT_CONFIG,
      currentEpoch: 32,
      totalEpochs: 60,
      estimatedTimeRemaining: '4h 12m',
      gpuUtilization: 94,
      gpuMemory: 38.4,
    },
  ];
}

// ============================================================================
// Hook Return Type
// ============================================================================

interface UseTrainingDataReturn {
  // State
  models: TrainingModel[];
  deployments: Deployment[];
  selectedModelMetrics: TrainingMetrics[];
  dataStats: DataCollectionStats;
  collectionActivities: CollectionActivity[];
  trainingJobs: TrainingJob[];
  isLoading: boolean;

  // Actions
  fetchModels: () => Promise<void>;
  fetchDeployments: () => Promise<void>;
  fetchMetrics: (modelId: string) => Promise<void>;
  startTraining: (modelId: string) => Promise<void>;
  stopTraining: (modelId: string) => Promise<void>;
  deployModel: (modelId: string, strategy: DeploymentStrategy) => Promise<void>;
  rollbackDeployment: (deploymentId: string) => Promise<void>;
  selectModel: (modelId: string) => void;
  setSelectedModelId: (id: string | null) => void;
  selectedModelId: string | null;
  toggleCollection: () => void;
}

// ============================================================================
// Custom Hook
// ============================================================================

export function useTrainingData(demoMode = true): UseTrainingDataReturn {
  const [models, setModels] = useState<TrainingModel[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [selectedModelMetrics, setSelectedModelMetrics] = useState<TrainingMetrics[]>([]);
  const [dataStats, setDataStats] = useState<DataCollectionStats>(createSeedDataStats());
  const [collectionActivities, setCollectionActivities] = useState<CollectionActivity[]>(createSeedActivities());
  const [trainingJobs, setTrainingJobs] = useState<TrainingJob[]>(createSeedJobs());
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  const initializedRef = useRef(false);

  // --- Initialize seed data ---
  useEffect(() => {
    if (demoMode && !initializedRef.current) {
      initializedRef.current = true;
      const seedModels = createSeedModels();
      setModels(seedModels);
      setDeployments(createSeedDeployments());
      if (seedModels.length > 0) {
        setSelectedModelId(seedModels[0].id);
        setSelectedModelMetrics(seedModels[0].metrics);
      }
    }
  }, [demoMode]);

  // --- Simulated live metric updates (demo mode) ---
  useEffect(() => {
    if (!demoMode) return;

    const interval = setInterval(() => {
      setModels((prev) =>
        prev.map((model) => {
          if (model.status !== 'training') return model;
          const nextEpoch = model.currentEpoch + 1;
          if (nextEpoch > model.totalEpochs) {
            return { ...model, status: 'completed' as ModelStatus, currentEpoch: model.totalEpochs };
          }
          const progress = nextEpoch / model.totalEpochs;
          const decay = Math.exp(-3 * progress);
          const newMetric: TrainingMetrics = {
            epoch: nextEpoch,
            loss: Math.max(0.01, 3.5 * decay + (Math.random() - 0.5) * 0.05),
            valLoss: Math.max(0.01, 3.5 * decay * 1.15 + (Math.random() - 0.5) * 0.06),
            cer: Math.max(0.001, 0.35 * decay + (Math.random() - 0.5) * 0.008),
            wer: Math.max(0.001, 0.55 * decay + (Math.random() - 0.5) * 0.012),
            accuracy: Math.min(0.99, 0.99 - 0.6 * decay + (Math.random() - 0.5) * 0.008),
            f1Score: Math.min(0.99, 0.98 - 0.55 * decay + (Math.random() - 0.5) * 0.008),
            learningRate: 0.001 * (1 - progress * 0.8),
            timestamp: new Date().toISOString(),
          };
          const updatedMetrics = [...model.metrics, newMetric];
          return {
            ...model,
            metrics: updatedMetrics,
            latestMetrics: newMetric,
            currentEpoch: nextEpoch,
            updatedAt: new Date().toISOString(),
          };
        })
      );
    }, 5000);

    return () => clearInterval(interval);
  }, [demoMode]);

  // --- Data increment simulation (demo mode) ---
  useEffect(() => {
    if (!demoMode || !dataStats.isCollecting) return;

    const interval = setInterval(() => {
      setDataStats((prev) => {
        const increment = Math.floor(Math.random() * 5) + 1;
        const newTotal = Math.min(prev.totalSamples + increment, prev.targetSamples);
        return {
          ...prev,
          totalSamples: newTotal,
          synthetic: {
            ...prev.synthetic,
            count: Math.round(newTotal * 0.5),
          },
          digitalLibrary: {
            ...prev.digitalLibrary,
            count: Math.round(newTotal * 0.3),
          },
          academic: {
            ...prev.academic,
            count: Math.round(newTotal * 0.2),
          },
          lastUpdated: new Date().toISOString(),
        };
      });
    }, 8000);

    return () => clearInterval(interval);
  }, [demoMode, dataStats.isCollecting]);

  const fetchModels = useCallback(async () => {
    setIsLoading(true);
    // In demo mode, data is already in state
    // In production, this would be: const res = await fetch('/api/models');
    await new Promise((r) => setTimeout(r, 300));
    setIsLoading(false);
  }, []);

  const fetchDeployments = useCallback(async () => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 300));
    setIsLoading(false);
  }, []);

  const fetchMetrics = useCallback(async (modelId: string) => {
    setIsLoading(true);
    await new Promise((r) => setTimeout(r, 200));
    const model = models.find((m) => m.id === modelId);
    if (model) {
      setSelectedModelMetrics(model.metrics);
      setSelectedModelId(modelId);
    }
    setIsLoading(false);
  }, [models]);

  const startTraining = useCallback(async (modelId: string) => {
    setModels((prev) =>
      prev.map((m) =>
        m.id === modelId
          ? { ...m, status: 'training' as ModelStatus, currentEpoch: 0, metrics: [], latestMetrics: undefined }
          : m
      )
    );
    setTrainingJobs((prev) => [
      ...prev,
      {
        id: `job-${Date.now()}`,
        modelName: models.find((m) => m.id === modelId)?.name || modelId,
        modelId,
        status: 'running' as JobStatus,
        progress: 0,
        startTime: new Date().toISOString(),
        config: DEFAULT_CONFIG,
        currentEpoch: 0,
        totalEpochs: 50,
        estimatedTimeRemaining: 'TBD',
        gpuUtilization: 0,
        gpuMemory: 0,
      },
    ]);
  }, [models]);

  const stopTraining = useCallback(async (modelId: string) => {
    setModels((prev) =>
      prev.map((m) =>
        m.id === modelId ? { ...m, status: 'failed' as ModelStatus, updatedAt: new Date().toISOString() } : m
      )
    );
    setTrainingJobs((prev) =>
      prev.map((j) => (j.modelId === modelId ? { ...j, status: 'cancelled' as JobStatus, progress: j.progress } : j))
    );
  }, []);

  const deployModel = useCallback(async (modelId: string, strategy: DeploymentStrategy) => {
    const model = models.find((m) => m.id === modelId);
    if (!model) return;
    const newDeployment: Deployment = {
      id: `deploy-${Date.now()}`,
      modelId,
      modelName: model.name,
      modelVersion: model.version,
      strategy,
      status: 'pending',
      trafficPercent: strategy === 'canary' ? 5 : strategy === 'rolling' ? 25 : 0,
      endpoint: `https://api.omnimed.ai/v2/ocr/${model.name.toLowerCase().replace(/\s+/g, '-')}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      healthChecks: [
        { name: 'Latency P50', status: 'passing', latency: 0, lastCheck: new Date().toISOString() },
        { name: 'Error Rate', status: 'passing', latency: 0, lastCheck: new Date().toISOString() },
      ],
      timeline: [
        { timestamp: new Date().toISOString(), action: 'deploy_created', description: `Deployment created with ${strategy} strategy` },
      ],
    };
    setDeployments((prev) => [...prev, newDeployment]);

    // Simulate deployment becoming active after a delay
    setTimeout(() => {
      setDeployments((prev) =>
        prev.map((d) =>
          d.id === newDeployment.id
            ? {
                ...d,
                status: 'active' as const,
                trafficPercent: strategy === 'canary' ? 10 : 100,
                healthChecks: d.healthChecks.map((h) => ({
                  ...h,
                  latency: h.name.includes('Latency') ? 150 + Math.random() * 100 : Math.random() * 0.1,
                  lastCheck: new Date().toISOString(),
                })),
                timeline: [
                  ...d.timeline,
                  { timestamp: new Date().toISOString(), action: 'deploy_active', description: 'Deployment is now active' },
                ],
              }
            : d
        )
      );
    }, 3000);
  }, [models]);

  const rollbackDeployment = useCallback(async (deploymentId: string) => {
    setDeployments((prev) =>
      prev.map((d) =>
        d.id === deploymentId
          ? {
              ...d,
              status: 'rolling-back' as const,
              timeline: [
                ...d.timeline,
                { timestamp: new Date().toISOString(), action: 'rollback_initiated', description: 'Rollback initiated by user' },
              ],
            }
          : d
      )
    );
    setTimeout(() => {
      setDeployments((prev) =>
        prev.map((d) =>
          d.id === deploymentId
            ? {
                ...d,
                status: 'completed' as const,
                trafficPercent: 0,
                timeline: [
                  ...d.timeline,
                  { timestamp: new Date().toISOString(), action: 'rollback_complete', description: 'Rollback completed successfully' },
                ],
              }
            : d
        )
      );
    }, 5000);
  }, []);

  const selectModel = useCallback(
    (modelId: string) => {
      fetchMetrics(modelId);
    },
    [fetchMetrics]
  );

  const toggleCollection = useCallback(() => {
    setDataStats((prev) => ({ ...prev, isCollecting: !prev.isCollecting }));
  }, []);

  return {
    models,
    deployments,
    selectedModelMetrics,
    dataStats,
    collectionActivities,
    trainingJobs,
    isLoading,
    fetchModels,
    fetchDeployments,
    fetchMetrics,
    startTraining,
    stopTraining,
    deployModel,
    rollbackDeployment,
    selectModel,
    setSelectedModelId,
    selectedModelId,
    toggleCollection,
  };
}

export default useTrainingData;
