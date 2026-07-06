// ============================================================================
// Medical Training Dashboard — Type Definitions
// ============================================================================

/** Possible statuses for a training model */
export type ModelStatus = 'training' | 'completed' | 'failed' | 'deployed' | 'pending';

/** Possible deployment strategies */
export type DeploymentStrategy = 'canary' | 'blue-green' | 'rolling';

/** Possible deployment statuses */
export type DeploymentStatus = 'active' | 'rolling-back' | 'completed' | 'failed' | 'pending';

/** Possible training job statuses */
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

/** Metric trend direction */
export type Trend = 'up' | 'down' | 'stable';

/** WebSocket message types */
export type WSMessageType = 'metric_update' | 'job_update' | 'deployment_update';

// ============================================================================
// Core Data Types
// ============================================================================

/** Metrics captured at a single training epoch */
export interface TrainingMetrics {
  epoch: number;
  loss: number;
  valLoss: number;
  cer: number;
  wer: number;
  accuracy: number;
  f1Score: number;
  learningRate: number;
  timestamp: string;
}

/** A training model entity */
export interface TrainingModel {
  id: string;
  name: string;
  version: string;
  description: string;
  status: ModelStatus;
  metrics: TrainingMetrics[];
  latestMetrics?: TrainingMetrics;
  totalEpochs: number;
  currentEpoch: number;
  createdAt: string;
  updatedAt: string;
  config: TrainingConfig;
  tags: string[];
}

/** Training hyper-parameter configuration */
export interface TrainingConfig {
  batchSize: number;
  learningRate: number;
  optimizer: string;
  scheduler: string;
  architecture: string;
  backbone: string;
  maxTextLength: number;
  augmentation: string[];
  mixedPrecision: boolean;
  gradientCheckpointing: boolean;
}

/** A deployment record */
export interface Deployment {
  id: string;
  modelId: string;
  modelName: string;
  modelVersion: string;
  strategy: DeploymentStrategy;
  status: DeploymentStatus;
  trafficPercent: number;
  endpoint: string;
  createdAt: string;
  updatedAt: string;
  rollbackFrom?: string;
  healthChecks: HealthCheck[];
  timeline: DeploymentEvent[];
}

/** Health check result */
export interface HealthCheck {
  name: string;
  status: 'passing' | 'warning' | 'critical';
  latency: number;
  lastCheck: string;
}

/** Deployment timeline event */
export interface DeploymentEvent {
  timestamp: string;
  action: string;
  description: string;
  user?: string;
}

/** Data collection statistics */
export interface DataCollectionStats {
  totalSamples: number;
  targetSamples: number;
  digitalLibrary: SourceBreakdown;
  academic: SourceBreakdown;
  synthetic: SourceBreakdown;
  qualityScore: number;
  averageResolution: string;
  languages: LanguageBreakdown[];
  lastUpdated: string;
  isCollecting: boolean;
}

/** Breakdown of a data source */
export interface SourceBreakdown {
  count: number;
  percentage: number;
  qualityScore: number;
}

/** Language breakdown */
export interface LanguageBreakdown {
  code: string;
  name: string;
  count: number;
  percentage: number;
}

/** Collection activity event */
export interface CollectionActivity {
  id: string;
  timestamp: string;
  source: string;
  count: number;
  type: 'added' | 'validated' | 'rejected' | 'augmented';
  description: string;
}

/** A training job */
export interface TrainingJob {
  id: string;
  modelName: string;
  modelId: string;
  status: JobStatus;
  progress: number;
  startTime: string;
  endTime?: string;
  config: TrainingConfig;
  currentEpoch: number;
  totalEpochs: number;
  estimatedTimeRemaining?: string;
  gpuUtilization: number;
  gpuMemory: number;
}

/** WebSocket message envelope */
export interface WebSocketMessage<T = unknown> {
  type: WSMessageType;
  payload: T;
  timestamp: string;
}

/** Metric update payload */
export interface MetricUpdatePayload {
  modelId: string;
  metrics: TrainingMetrics;
}

/** Job update payload */
export interface JobUpdatePayload {
  jobId: string;
  status: JobStatus;
  progress: number;
  currentEpoch: number;
  estimatedTimeRemaining?: string;
}

/** Deployment update payload */
export interface DeploymentUpdatePayload {
  deploymentId: string;
  status: DeploymentStatus;
  trafficPercent: number;
  healthChecks: HealthCheck[];
}

/** Side-by-side model comparison data */
export interface ModelComparison {
  modelA: TrainingModel;
  modelB: TrainingModel;
  metricsDelta: MetricsDelta;
}

/** Delta between two models' metrics */
export interface MetricsDelta {
  cer: number;
  wer: number;
  loss: number;
  accuracy: number;
  f1Score: number;
  inferenceTime: number;
}

/** Radar chart data point for model comparison */
export interface RadarDataPoint {
  metric: string;
  modelA: number;
  modelB: number;
  fullMark: number;
}

/** Tab definition for the main page */
export interface DashboardTab {
  id: string;
  label: string;
  icon: string;
}
