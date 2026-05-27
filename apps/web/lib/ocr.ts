import sharp from 'sharp';
import Tesseract from 'tesseract.js';

/**
 * OCR Worker Singleton
 *
 * Instead of creating a new Tesseract worker for every page number extraction
 * (which is expensive in production), we maintain a singleton worker that is
 * reused across calls. The worker is initialized lazily on first use and
 * supports language configuration.
 */

let _worker: Tesseract.Worker | null = null;
let _workerInitPromise: Promise<Tesseract.Worker> | null = null;

/**
 * Get or create a singleton Tesseract worker.
 * The worker is shared across all requests to avoid the overhead of
 * initializing a new worker for every OCR call.
 */
async function getWorker(): Promise<Tesseract.Worker> {
  if (_worker) return _worker;

  if (_workerInitPromise) return _workerInitPromise;

  _workerInitPromise = Tesseract.createWorker('ara+eng', undefined, {
    logger: () => {},
  }).then((worker) => {
    _worker = worker;
    _workerInitPromise = null;
    return worker;
  });

  return _workerInitPromise;
}

/**
 * Terminate the singleton worker. Call this on server shutdown.
 */
export async function terminateOcrWorker(): Promise<void> {
  if (_worker) {
    await _worker.terminate();
    _worker = null;
    _workerInitPromise = null;
  }
}

/**
 * Extract text from the bottom-right region of an image and find page numbers.
 *
 * Uses a singleton Tesseract worker for efficiency. In a high-throughput
 * environment, consider moving OCR to a backend queue (Celery/Redis).
 */
export async function extractPageNumber(imageBuffer: Buffer): Promise<{
  pageNumber: string | null;
  fullText: string;
}> {
  const metadata = await sharp(imageBuffer).metadata();
  const w = metadata.width || 0;
  const h = metadata.height || 0;

  if (w === 0 || h === 0) {
    return { pageNumber: null, fullText: '' };
  }

  // Extract the bottom 20% right 50% region where page numbers typically appear
  const regionWidth = Math.floor(w * 0.5);
  const regionHeight = Math.floor(h * 0.2);
  const regionLeft = Math.floor(w * 0.5);
  const regionTop = h - regionHeight;

  let regionBuffer: Buffer;
  try {
    regionBuffer = await sharp(imageBuffer)
      .extract({
        left: regionLeft,
        top: regionTop,
        width: regionWidth,
        height: regionHeight,
      })
      .grayscale()
      .png()
      .toBuffer();
  } catch {
    // If extract fails, try full image
    regionBuffer = await sharp(imageBuffer)
      .grayscale()
      .png()
      .toBuffer();
  }

  // Reuse the singleton worker instead of creating a new one per call
  const worker = await getWorker();
  const { data: { text } } = await worker.recognize(regionBuffer);

  const fullText = text.replace(/\s+/g, ' ').trim();

  // Try to find a page number from the text
  const pageNumber = detectPageNumber(fullText);

  return { pageNumber, fullText };
}

/**
 * Detect page number patterns from extracted text.
 */
function detectPageNumber(text: string): string | null {
  if (!text || text.trim().length === 0) return null;

  // Clean up text
  const clean = text.trim();

  // Pattern 1: "5/20" or "5 / 20" (page X of Y)
  const pageOfMatch = clean.match(/(\d+)\s*\/\s*(\d+)/);
  if (pageOfMatch) {
    return pageOfMatch[1]; // Return just the page number
  }

  // Pattern 2: Arabic "صفحة 5" or "صفحة  5" or "ص 5"
  const arabicPageMatch = clean.match(/(?:صفحة|ص)\s*(\d+)/);
  if (arabicPageMatch) {
    return arabicPageMatch[1];
  }

  // Pattern 3: English "Page 5" or "page 5" or "P. 5" or "p.5"
  const englishPageMatch = clean.match(/(?:Page|page|P\.?|p\.)\s*(\d+)/);
  if (englishPageMatch) {
    return englishPageMatch[1];
  }

  // Pattern 4: Standalone number (likely a page number if it's the main/only content)
  const standaloneMatch = clean.match(/(\d+)\s*$/);
  if (standaloneMatch) {
    const num = standaloneMatch[1];
    if (num.length <= 4 && parseInt(num) > 0 && parseInt(num) < 10000) {
      return num;
    }
  }

  // Pattern 5: Number at the start of text
  const startMatch = clean.match(/^(\d+)/);
  if (startMatch) {
    const num = startMatch[1];
    if (num.length <= 4 && parseInt(num) > 0 && parseInt(num) < 10000) {
      return num;
    }
  }

  // Pattern 6: Roman numerals (I, II, III, IV, V, etc.)
  const romanMatch = clean.match(/\b([IVXLCDM]+)\b/);
  if (romanMatch) {
    const roman = romanMatch[1];
    const romanValue = romanToNumber(roman);
    if (romanValue > 0 && romanValue < 1000) {
      return roman;
    }
  }

  return null;
}

/**
 * Convert Roman numeral to number
 */
function romanToNumber(roman: string): number {
  const romanMap: Record<string, number> = {
    I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000,
  };
  let result = 0;
  for (let i = 0; i < roman.length; i++) {
    const current = romanMap[roman[i]] || 0;
    const next = romanMap[roman[i + 1]] || 0;
    if (current < next) {
      result -= current;
    } else {
      result += current;
    }
  }
  return result;
}
