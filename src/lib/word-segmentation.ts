import sharp from 'sharp';

export interface WordSegment {
  image: Buffer;
  x: number;
  y: number;
  width: number;
  height: number;
  lineIndex: number;
  wordIndex: number;
}

export interface LineSegment {
  x: number;
  y: number;
  width: number;
  height: number;
  startIndex: number;
  endIndex: number;
}

/**
 * Preprocess an image: grayscale → CLAHE-like contrast → Otsu threshold → binary
 */
export async function preprocessImage(buffer: Buffer): Promise<{
  binary: Buffer;
  width: number;
  height: number;
  pixels: Uint8Array;
}> {
  // Convert to raw grayscale
  const raw = await sharp(buffer)
    .grayscale()
    .raw()
    .toBuffer();

  const metadata = await sharp(buffer)
    .grayscale()
    .metadata();

  const width = metadata.width || 0;
  const height = metadata.height || 0;

  if (width === 0 || height === 0) {
    throw new Error('Invalid image dimensions');
  }

  const pixels = new Uint8Array(raw);

  // Step 1: Histogram normalization (CLAHE-like contrast enhancement)
  const hist = new Array(256).fill(0);
  for (let i = 0; i < pixels.length; i++) {
    hist[pixels[i]]++;
  }

  // Compute CDF
  const cdf = new Array(256).fill(0);
  cdf[0] = hist[0];
  for (let i = 1; i < 256; i++) {
    cdf[i] = cdf[i - 1] + hist[i];
  }

  // Find min CDF
  let cdfMin = 0;
  for (let i = 0; i < 256; i++) {
    if (cdf[i] > 0) {
      cdfMin = cdf[i];
      break;
    }
  }

  const totalPixels = pixels.length;
  // Apply histogram equalization
  const equalized = new Uint8Array(pixels.length);
  for (let i = 0; i < pixels.length; i++) {
    equalized[i] = Math.round(
      ((cdf[pixels[i]] - cdfMin) / (totalPixels - cdfMin)) * 255
    );
  }

  // Step 2: Apply Otsu-like threshold using median brightness * 0.85
  const sorted = new Uint8Array(equalized).sort();
  const median = sorted[Math.floor(sorted.length / 2)];
  const threshold = Math.max(0, Math.min(255, Math.floor(median * 0.85)));

  // Step 3: Create binary image (0 = white/background, 255 = black/text)
  const binary = Buffer.alloc(width * height * 3); // RGB for sharp
  for (let i = 0; i < equalized.length; i++) {
    const val = equalized[i] < threshold ? 0 : 255; // dark pixels become 0 (black), light become 255 (white)
    const idx = i * 3;
    binary[idx] = val;
    binary[idx + 1] = val;
    binary[idx + 2] = val;
  }

  // Step 4: Mild sharpening using unsharp mask on the binary
  const sharpened = await sharp(binary, { raw: { width, height, channels: 3 } })
    .sharpen({ sigma: 0.5, m1: 0.5, m2: 0.3 })
    .raw()
    .toBuffer();

  // Return the binary pixels for projection analysis (single channel)
  const binaryPixels = new Uint8Array(width * height);
  for (let i = 0; i < width * height; i++) {
    binaryPixels[i] = sharpened[i * 3] < 128 ? 1 : 0; // 1 = foreground (dark), 0 = background (light)
  }

  // Also create a clean PNG buffer for display/cropping
  const binaryPng = await sharp(sharpened, { raw: { width, height, channels: 3 } })
    .png()
    .toBuffer();

  return { binary: binaryPng, width, height, pixels: binaryPixels };
}

/**
 * Find text lines using horizontal projection profile
 */
export function findLines(
  pixels: Uint8Array,
  width: number,
  height: number
): LineSegment[] {
  // Compute horizontal projection (sum of dark pixels per row)
  const hProjection = new Array(height).fill(0);
  for (let y = 0; y < height; y++) {
    let sum = 0;
    for (let x = 0; x < width; x++) {
      sum += pixels[y * width + x];
    }
    hProjection[y] = sum;
  }

  // Find max projection
  const maxProjection = Math.max(...hProjection);
  if (maxProjection === 0) return [];

  // Find line boundaries: where projection drops below 5% of max for at least 5 pixels
  const lineThreshold = maxProjection * 0.05;
  const minGapPixels = 5;

  const lines: LineSegment[] = [];
  let inLine = false;
  let lineStart = 0;
  let gapCount = 0;

  for (let y = 0; y < height; y++) {
    if (hProjection[y] >= lineThreshold) {
      if (!inLine) {
        lineStart = y;
        inLine = true;
      }
      gapCount = 0;
    } else {
      if (inLine) {
        gapCount++;
        if (gapCount >= minGapPixels) {
          // End of line
          const lineEnd = y - minGapPixels;
          if (lineEnd > lineStart) {
            lines.push({
              x: 0,
              y: lineStart,
              width,
              height: lineEnd - lineStart,
              startIndex: lineStart,
              endIndex: lineEnd,
            });
          }
          inLine = false;
          gapCount = 0;
        }
      }
    }
  }

  // Handle last line
  if (inLine) {
    const lineEnd = height - 1;
    if (lineEnd > lineStart) {
      lines.push({
        x: 0,
        y: lineStart,
        width,
        height: lineEnd - lineStart,
        startIndex: lineStart,
        endIndex: lineEnd,
      });
    }
  }

  // Filter out lines that are too small (likely noise)
  const minHeight = Math.max(5, height * 0.005);
  return lines.filter((line) => line.height >= minHeight);
}

/**
 * Segment words from a line region using vertical projection profile
 */
export function segmentWordsFromLine(
  pixels: Uint8Array,
  width: number,
  height: number,
  line: LineSegment
): WordSegment[] {
  const words: WordSegment[] = [];

  // Extract line region pixels
  const linePixels = new Uint8Array(line.width * line.height);
  for (let y = 0; y < line.height; y++) {
    for (let x = 0; x < line.width; x++) {
      linePixels[y * line.width + x] =
        pixels[(line.startIndex + y) * width + x];
    }
  }

  // Compute vertical projection (sum of dark pixels per column)
  const vProjection = new Array(line.width).fill(0);
  for (let x = 0; x < line.width; x++) {
    let sum = 0;
    for (let y = 0; y < line.height; y++) {
      sum += linePixels[y * line.width + x];
    }
    vProjection[x] = sum;
  }

  const maxProjection = Math.max(...vProjection);
  if (maxProjection === 0) return [];

  // Find word boundaries: where projection drops below 3% of max for at least 2 pixels
  const wordThreshold = maxProjection * 0.03;
  const minGapPixels = 2;

  let inWord = false;
  let wordStart = 0;
  let gapCount = 0;

  const wordBounds: { start: number; end: number }[] = [];

  for (let x = 0; x < line.width; x++) {
    if (vProjection[x] >= wordThreshold) {
      if (!inWord) {
        wordStart = x;
        inWord = true;
      }
      gapCount = 0;
    } else {
      if (inWord) {
        gapCount++;
        if (gapCount >= minGapPixels) {
          const wordEnd = x - minGapPixels;
          if (wordEnd > wordStart) {
            wordBounds.push({ start: wordStart, end: wordEnd });
          }
          inWord = false;
          gapCount = 0;
        }
      }
    }
  }

  // Handle last word
  if (inWord) {
    const wordEnd = line.width - 1;
    if (wordEnd > wordStart) {
      wordBounds.push({ start: wordStart, end: wordEnd });
    }
  }

  // Filter out tiny segments (noise)
  const minWordWidth = Math.max(3, line.width * 0.003);
  const validBounds = wordBounds.filter((b) => b.end - b.start >= minWordWidth);

  return validBounds.map((bound, idx) => {
    // Add 3px padding
    const padding = 3;
    const x = Math.max(0, line.x + bound.start - padding);
    const y = Math.max(0, line.y - padding);
    const w = Math.min(width - x, bound.end - bound.start + padding * 2);
    const h = Math.min(height - y, line.height + padding * 2);

    return {
      image: Buffer.alloc(0), // Will be filled when cropping from original image
      x,
      y,
      width: w,
      height: h,
      lineIndex: 0, // Will be set by caller
      wordIndex: idx,
    };
  });
}

/**
 * Segment a full page into words
 */
export async function segmentPage(imageBuffer: Buffer): Promise<WordSegment[]> {
  const { binary, width, height, pixels } = await preprocessImage(imageBuffer);

  const lines = findLines(pixels, width, height);

  const allWords: WordSegment[] = [];

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx];
    const wordBounds = segmentWordsFromLine(pixels, width, height, line);

    for (const word of wordBounds) {
      // Crop the word image from the original (preprocessed) image
      const cropX = Math.max(0, word.x);
      const cropY = Math.max(0, word.y);
      const cropW = Math.min(width - cropX, word.width);
      const cropH = Math.min(height - cropY, word.height);

      if (cropW <= 0 || cropH <= 0) continue;

      try {
        const wordImage = await sharp(imageBuffer)
          .extract({ left: cropX, top: cropY, width: cropW, height: cropH })
          .grayscale()
          .png()
          .toBuffer();

        allWords.push({
          image: wordImage,
          x: cropX,
          y: cropY,
          width: cropW,
          height: cropH,
          lineIndex: lineIdx,
          wordIndex: word.wordIndex,
        });
      } catch {
        // Skip if cropping fails
      }
    }
  }

  return allWords;
}
