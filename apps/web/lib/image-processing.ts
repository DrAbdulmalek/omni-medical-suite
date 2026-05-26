import sharp from 'sharp';
import fs from 'fs';
import path from 'path';

const UPLOADS_DIR = '/home/z/my-project/uploads';
const THUMBNAILS_DIR = '/home/z/my-project/uploads/thumbnails';

// Smart crop: detect and remove gray borders
export async function smartCrop(buffer: Buffer, threshold: number = 200): Promise<{
  cropped: Buffer;
  cropLeft: number;
  cropTop: number;
  cropRight: number;
  cropBottom: number;
}> {
  const image = sharp(buffer);
  const metadata = await image.metadata();
  const w = metadata.width!;
  const h = metadata.height!;

  // Get raw pixel data
  const { data, info } = await image
    .raw()
    .toBuffer({ resolveWithObject: true });

  const channels = info.channels;

  function getColMedian(col: number): number {
    const values: number[] = [];
    for (let y = 0; y < info.height; y++) {
      const idx = (y * info.width + col) * channels;
      const gray = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
      values.push(gray);
    }
    values.sort((a, b) => a - b);
    return values[Math.floor(values.length / 2)];
  }

  function getRowMedian(row: number, left: number, right: number): number {
    const values: number[] = [];
    for (let x = left; x <= right; x++) {
      const idx = (row * info.width + x) * channels;
      const gray = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
      values.push(gray);
    }
    values.sort((a, b) => a - b);
    return values[Math.floor(values.length / 2)];
  }

  let left = 0, right = w - 1, top = 0, bottom = h - 1;

  for (let x = 0; x < w; x++) {
    if (getColMedian(x) > threshold) { left = x; break; }
  }
  for (let x = w - 1; x >= 0; x--) {
    if (getColMedian(x) > threshold) { right = x; break; }
  }

  for (let y = 0; y < h; y++) {
    if (getRowMedian(y, left, right) > threshold) { top = y; break; }
  }
  for (let y = h - 1; y >= 0; y--) {
    if (getRowMedian(y, left, right) > threshold) { bottom = y; break; }
  }

  const margin = 5;
  left = Math.max(0, left - margin);
  top = Math.max(0, top - margin);
  right = Math.min(w - 1, right + margin);
  bottom = Math.min(h - 1, bottom + margin);

  const cropW = right - left + 1;
  const cropH = bottom - top + 1;

  if (cropW <= 0 || cropH <= 0) {
    return { cropped: buffer, cropLeft: 0, cropTop: 0, cropRight: 0, cropBottom: 0 };
  }

  const cropped = await sharp(buffer)
    .extract({ left, top, width: cropW, height: cropH })
    .png()
    .toBuffer();

  return {
    cropped,
    cropLeft: left,
    cropTop: top,
    cropRight: w - right - 1,
    cropBottom: h - bottom - 1
  };
}

// Calculate blur score (Laplacian variance approximation)
export async function calculateBlurScore(buffer: Buffer): Promise<number> {
  const { data, info } = await sharp(buffer)
    .grayscale()
    .raw()
    .toBuffer({ resolveWithObject: true });

  let sum = 0, sumSq = 0, count = 0;
  for (let y = 1; y < info.height - 1; y++) {
    for (let x = 1; x < info.width - 1; x++) {
      const idx = y * info.width + x;
      const laplacian =
        -4 * data[idx]
        + data[idx - 1] + data[idx + 1]
        + data[idx - info.width] + data[idx + info.width];
      sum += laplacian;
      sumSq += laplacian * laplacian;
      count++;
    }
  }
  const mean = sum / count;
  return Math.round(((sumSq / count) - (mean * mean)) * 100) / 100;
}

// Apply manual crop
export async function applyCrop(
  buffer: Buffer,
  left: number, top: number, right: number, bottom: number
): Promise<Buffer> {
  const metadata = await sharp(buffer).metadata();
  const w = metadata.width!;
  const h = metadata.height!;

  const cropW = w - left - right;
  const cropH = h - top - bottom;

  if (cropW <= 0 || cropH <= 0) return buffer;

  return sharp(buffer)
    .extract({ left, top, width: cropW, height: cropH })
    .png()
    .toBuffer();
}

// Generate thumbnail
export async function generateThumbnail(buffer: Buffer, fileName: string): Promise<string> {
  const thumbPath = path.join(THUMBNAILS_DIR, `thumb_${fileName.replace(/\.[^.]+$/, '.png')}`);

  await sharp(buffer)
    .resize(200, 200, { fit: 'inside', background: { r: 255, g: 255, b: 255, alpha: 0 } })
    .png()
    .toFile(thumbPath);

  return thumbPath;
}

// Get image metadata
export async function getImageMetadata(buffer: Buffer): Promise<{
  width: number;
  height: number;
  format: string;
}> {
  const metadata = await sharp(buffer).metadata();
  return {
    width: metadata.width || 0,
    height: metadata.height || 0,
    format: metadata.format || 'unknown'
  };
}

// Remove shadow using illumination normalization
export async function removeShadow(buffer: Buffer): Promise<Buffer> {
  return sharp(buffer)
    .normalize()
    .modulate({ brightness: 1.05 })
    .sharpen({ sigma: 0.5, m1: 0.5, m2: 0.3 })
    .png()
    .toBuffer();
}

// Ensure directories exist
export function ensureUploadDirs() {
  if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
  }
  if (!fs.existsSync(THUMBNAILS_DIR)) {
    fs.mkdirSync(THUMBNAILS_DIR, { recursive: true });
  }
}
