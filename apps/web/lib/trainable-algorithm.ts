import sharp from 'sharp';
import fs from 'fs';
import path from 'path';
import { db } from '@/lib/db';

const UPLOADS_DIR = '/home/z/my-project/uploads';
const MODEL_DIR = '/home/z/my-project/model';
const MODEL_PATH = path.join(MODEL_DIR, 'trained-model.json');

export interface ImageFeatures {
  width: number;
  height: number;
  aspectRatio: number;
  blurScore: number;
  brightness: number;
  edgeDensity: number;
  borderNoise: number;
}

export interface PredictedSettings {
  pageThreshold: number;
  grayThreshold: number;
  padding: number;
  confidence: number;
  similarRecords: number;
}

export interface TrainingEntry {
  features: ImageFeatures;
  settings: {
    pageThreshold: number;
    grayThreshold: number;
    padding: number;
  };
}

export interface ModelData {
  entries: TrainingEntry[];
  normalizedFeatures: {
    min: Record<string, number>;
    max: Record<string, number>;
  };
  trainedAt: string;
  totalEntries: number;
  avgConfidence: number;
}

const FEATURE_KEYS = ['width', 'height', 'aspectRatio', 'blurScore', 'brightness', 'edgeDensity', 'borderNoise'] as const;

/**
 * Extract features from an image buffer using sharp
 */
export async function extractFeatures(imageBuffer: Buffer): Promise<ImageFeatures> {
  const image = sharp(imageBuffer);
  const metadata = await image.metadata();
  const w = metadata.width || 0;
  const h = metadata.height || 0;

  // Get grayscale raw data
  const { data, info } = await sharp(imageBuffer)
    .grayscale()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const pixelCount = info.width * info.height;

  // Calculate average brightness
  let brightnessSum = 0;
  for (let i = 0; i < pixelCount; i++) {
    brightnessSum += data[i];
  }
  const brightness = brightnessSum / pixelCount;

  // Calculate edge density (simple gradient magnitude)
  let edgeCount = 0;
  for (let y = 1; y < info.height - 1; y++) {
    for (let x = 1; x < info.width - 1; x++) {
      const idx = y * info.width + x;
      const gx = Math.abs(data[idx + 1] - data[idx - 1]);
      const gy = Math.abs(data[idx + info.width] - data[idx - info.width]);
      if (gx + gy > 30) edgeCount++;
    }
  }
  const edgeDensity = edgeCount / pixelCount;

  // Calculate border noise
  const borderWidth = Math.max(5, Math.floor(Math.min(w, h) * 0.05));
  let borderSum = 0;
  let borderCount = 0;

  // Top border
  for (let y = 0; y < borderWidth; y++) {
    for (let x = 0; x < info.width; x++) {
      borderSum += data[y * info.width + x];
      borderCount++;
    }
  }
  // Bottom border
  for (let y = info.height - borderWidth; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
      borderSum += data[y * info.width + x];
      borderCount++;
    }
  }
  // Left border
  for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < borderWidth; x++) {
      borderSum += data[y * info.width + x];
      borderCount++;
    }
  }
  // Right border
  for (let y = 0; y < info.height; y++) {
    for (let x = info.width - borderWidth; x < info.width; x++) {
      borderSum += data[y * info.width + x];
      borderCount++;
    }
  }

  const borderBrightness = borderSum / borderCount;
  // Border noise = how much the border varies from the average
  const borderNoise = Math.abs(borderBrightness - brightness) / 255;

  // Blur score using Laplacian variance
  let lapSum = 0;
  let lapSumSq = 0;
  let lapCount = 0;
  for (let y = 1; y < info.height - 1; y++) {
    for (let x = 1; x < info.width - 1; x++) {
      const idx = y * info.width + x;
      const laplacian =
        -4 * data[idx]
        + data[idx - 1] + data[idx + 1]
        + data[idx - info.width] + data[idx + info.width];
      lapSum += laplacian;
      lapSumSq += laplacian * laplacian;
      lapCount++;
    }
  }
  const lapMean = lapSum / lapCount;
  const blurScore = Math.sqrt((lapSumSq / lapCount) - (lapMean * lapMean));

  return {
    width: w,
    height: h,
    aspectRatio: w / (h || 1),
    blurScore,
    brightness: brightness / 255, // Normalize to 0-1
    edgeDensity,
    borderNoise,
  };
}

/**
 * Get training entries from the database
 */
export async function getTrainingEntriesFromDB(): Promise<TrainingEntry[]> {
  const records = await db.trainingRecord.findMany();
  const entries: TrainingEntry[] = [];

  for (const record of records) {
    try {
      let features: Partial<ImageFeatures> = {};
      try { features = JSON.parse(record.features); } catch { /* empty */ }

      let finalParams: Partial<{ pageThreshold: number; grayThreshold: number; padding: number }> = {};
      try { finalParams = JSON.parse(record.finalParams); } catch { /* empty */ }

      // If we have features, use them directly
      if (features.width && features.blurScore !== undefined) {
        entries.push({
          features: {
            width: features.width || 0,
            height: features.height || 0,
            aspectRatio: features.aspectRatio || (features.width || 0) / (features.height || 1),
            blurScore: features.blurScore || 0,
            brightness: features.brightness || 0.5,
            edgeDensity: features.edgeDensity || 0,
            borderNoise: features.borderNoise || 0,
          },
          settings: {
            pageThreshold: finalParams.pageThreshold || 200,
            grayThreshold: finalParams.grayThreshold || 230,
            padding: finalParams.padding || 10,
          },
        });
      }
    } catch {
      // Skip invalid records
    }
  }

  return entries;
}

/**
 * Normalize features for comparison
 */
function normalizeFeatures(
  features: ImageFeatures,
  min: Record<string, number>,
  max: Record<string, number>
): number[] {
  return FEATURE_KEYS.map((key) => {
    const range = max[key] - min[key];
    if (range === 0) return 0;
    return (features[key] - min[key]) / range;
  });
}

/**
 * Calculate min/max for normalization
 */
function calculateMinMax(entries: TrainingEntry[]): {
  min: Record<string, number>;
  max: Record<string, number>;
} {
  const min: Record<string, number> = {};
  const max: Record<string, number> = {};

  for (const key of FEATURE_KEYS) {
    const values = entries.map((e) => e.features[key]);
    min[key] = Math.min(...values);
    max[key] = Math.max(...values);
  }

  return { min, max };
}

/**
 * Calculate Euclidean distance between two normalized feature vectors
 */
function euclideanDistance(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    sum += (a[i] - b[i]) ** 2;
  }
  return Math.sqrt(sum);
}

/**
 * Train a KNN-like model (K=5 nearest neighbors, weighted average)
 */
export function trainModel(entries: TrainingEntry[]): ModelData {
  if (entries.length === 0) {
    throw new Error('No training entries available');
  }

  const { min, max } = calculateMinMax(entries);

  // Calculate avg confidence
  const avgConfidence = entries.length > 0 ? 1.0 : 0;

  return {
    entries,
    normalizedFeatures: { min, max },
    trainedAt: new Date().toISOString(),
    totalEntries: entries.length,
    avgConfidence,
  };
}

/**
 * Predict optimal settings using KNN (K=5 nearest neighbors)
 */
export function predict(features: ImageFeatures, model: ModelData): PredictedSettings {
  const K = 5;
  const { min, max } = model.normalizedFeatures;

  // Normalize query features
  const queryNorm = normalizeFeatures(features, min, max);

  // Calculate distances to all entries
  const distances = model.entries.map((entry, idx) => {
    const entryNorm = normalizeFeatures(entry.features, min, max);
    const dist = euclideanDistance(queryNorm, entryNorm);
    return { idx, dist, entry };
  });

  // Sort by distance (nearest first)
  distances.sort((a, b) => a.dist - b.dist);

  // Take K nearest neighbors
  const neighbors = distances.slice(0, Math.min(K, distances.length));

  // Calculate weighted average (inverse distance weighting)
  let totalWeight = 0;
  let weightedPageThreshold = 0;
  let weightedGrayThreshold = 0;
  let weightedPadding = 0;

  for (const neighbor of neighbors) {
    const weight = neighbor.dist < 0.001 ? 1000 : 1 / neighbor.dist;
    totalWeight += weight;
    weightedPageThreshold += neighbor.entry.settings.pageThreshold * weight;
    weightedGrayThreshold += neighbor.entry.settings.grayThreshold * weight;
    weightedPadding += neighbor.entry.settings.padding * weight;
  }

  const pageThreshold = Math.round(weightedPageThreshold / totalWeight);
  const grayThreshold = Math.round(weightedGrayThreshold / totalWeight);
  const padding = Math.round(weightedPadding / totalWeight);

  // Confidence based on how close the nearest neighbors are
  const avgDistance = neighbors.reduce((sum, n) => sum + n.dist, 0) / neighbors.length;
  const confidence = Math.max(0.3, Math.min(0.98, 1.0 - avgDistance * 0.8));

  return {
    pageThreshold: Math.max(150, Math.min(250, pageThreshold)),
    grayThreshold: Math.max(200, Math.min(250, grayThreshold)),
    padding: Math.max(0, Math.min(50, padding)),
    confidence,
    similarRecords: neighbors.length,
  };
}

/**
 * Save model to JSON file
 */
export function saveModel(model: ModelData): void {
  if (!fs.existsSync(MODEL_DIR)) {
    fs.mkdirSync(MODEL_DIR, { recursive: true });
  }
  fs.writeFileSync(MODEL_PATH, JSON.stringify(model, null, 2), 'utf-8');
}

/**
 * Load model from JSON file
 */
export function loadModel(): ModelData | null {
  try {
    if (!fs.existsSync(MODEL_PATH)) return null;
    const raw = fs.readFileSync(MODEL_PATH, 'utf-8');
    return JSON.parse(raw) as ModelData;
  } catch {
    return null;
  }
}
