/**
 * mobile/android/hooks/useOCR.ts
 * ================================
 * Hook شامل لعملية OCR
 * - رفع + polling + تصحيح
 * - وضع offline باستخدام Tesseract محلي
 * - retry تلقائي عند فشل الاتصال
 * - cancellation support
 */

import { useState, useCallback, useRef } from 'react';
import { OcrService, ApiError } from '../services/api';
import { useOcrStore, useSettingsStore } from '../store';
import type { OcrJobStatus } from '../services/api';

// ─── Types ────────────────────────────────────────────────────

export interface OcrOptions {
  language?: 'ar' | 'en' | 'auto';
  engine?: string;
  highQuality?: boolean;
  maxRetries?: number;
}

export interface OcrState {
  status: 'idle' | 'uploading' | 'processing' | 'done' | 'error' | 'cancelled';
  progress: number;
  stage: 'upload' | 'processing';
  result?: OcrJobStatus['result'];
  error?: string;
  documentId?: string;
}

// ─── Offline Tesseract Fallback ───────────────────────────────

async function runOfflineOcr(imageUri: string, language: string): Promise<string> {
  try {
    // @google-mlkit/text-recognition أو react-native-tesseract-ocr
    const { RNTesseractOcr } = require('react-native-tesseract-ocr');
    const tessLanguage = language === 'ar' ? 'ara' : 'eng';
    const text = await RNTesseractOcr.recognize(imageUri, tessLanguage, {});
    return text || '';
  } catch {
    // ML Kit fallback
    try {
      const TextRecognition = require('@react-native-ml-kit/text-recognition').default;
      const result = await TextRecognition.recognize(imageUri);
      return result.text || '';
    } catch {
      throw new Error('لا يتوفر محرك OCR محلي — يرجى الاتصال بالإنترنت');
    }
  }
}

// ─── Hook ─────────────────────────────────────────────────────

export function useOCR() {
  const [state, setState] = useState<OcrState>({
    status: 'idle',
    progress: 0,
    stage: 'upload',
  });

  const cancelRef = useRef(false);
  const { settings } = useSettingsStore();
  const { startJob, updateJob, completeJob, failJob, clearCurrentJob } = useOcrStore();

  const processImage = useCallback(async (
    imageUri: string,
    fileName: string,
    mimeType: string,
    options?: OcrOptions,
  ): Promise<OcrJobStatus['result'] | null> => {
    cancelRef.current = false;
    const maxRetries = options?.maxRetries ?? 2;

    setState({ status: 'uploading', progress: 0, stage: 'upload' });
    const jobId = startJob(imageUri);

    // ── Offline mode ──────────────────────────────────────────
    if (settings.offlineMode) {
      try {
        setState(s => ({ ...s, status: 'processing', stage: 'processing', progress: 50 }));
        const lang = options?.language || settings.language || 'auto';
        const text = await runOfflineOcr(imageUri, lang);

        const offlineResult: OcrJobStatus['result'] = {
          raw_text: text,
          corrected_text: text,
          confidence: 0.0,    // محرك محلي لا يُعطي confidence موثوقاً
          engine: 'tesseract-offline',
          language: lang,
          processing_ms: 0,
          word_count: text.split(/\s+/).length,
        };

        completeJob(jobId, {
          rawText: text,
          correctedText: text,
          confidence: 0,
          engine: 'tesseract-offline',
          processingMs: 0,
        });
        setState({ status: 'done', progress: 100, stage: 'processing', result: offlineResult });
        return offlineResult;

      } catch (err: any) {
        failJob(jobId, err.message);
        setState({ status: 'error', progress: 0, stage: 'upload', error: err.message });
        return null;
      }
    }

    // ── Online mode with retry ──────────────────────────────
    let lastError = '';
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      if (cancelRef.current) {
        setState({ status: 'cancelled', progress: 0, stage: 'upload' });
        clearCurrentJob();
        return null;
      }

      try {
        const result = await OcrService.processDocument(
          imageUri,
          fileName,
          mimeType,
          {
            engine: options?.engine || (settings.ocrEngine !== 'auto' ? settings.ocrEngine : undefined),
            language: options?.language || (settings.language !== 'auto' ? settings.language : undefined),
            high_quality: options?.highQuality ?? settings.highQualityMode,
          },
          (pct, stage) => {
            if (cancelRef.current) return;
            setState(s => ({ ...s, progress: pct, stage }));
            updateJob(jobId, {
              progress: pct,
              status: stage === 'upload' ? 'uploading' : 'processing',
            });
          }
        );

        if (cancelRef.current) {
          setState({ status: 'cancelled', progress: 0, stage: 'upload' });
          return null;
        }

        if (result.result) {
          completeJob(jobId, {
            rawText: result.result.raw_text,
            correctedText: result.result.corrected_text,
            confidence: result.result.confidence,
            engine: result.result.engine,
            processingMs: result.result.processing_ms,
          });
          setState({
            status: 'done',
            progress: 100,
            stage: 'processing',
            result: result.result,
            documentId: result.document_id,
          });
          return result.result;
        }

        throw new Error('لم يُرجع الخادم نتيجة');

      } catch (err: any) {
        lastError = err?.message || 'خطأ غير معروف';

        // لا تعيد المحاولة عند أخطاء 4xx
        if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
          break;
        }

        if (attempt < maxRetries) {
          // انتظر قبل إعادة المحاولة: 2s، 4s، 8s
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, attempt + 1)));
          setState(s => ({ ...s, status: 'uploading', progress: 0 }));
          continue;
        }
      }
    }

    // فشل كل المحاولات — حاول offline إذا متاح
    if (!settings.offlineMode) {
      try {
        setState(s => ({ ...s, status: 'processing', stage: 'processing', progress: 50, error: undefined }));
        const lang = options?.language || settings.language || 'auto';
        const text = await runOfflineOcr(imageUri, lang);
        if (text) {
          const fallbackResult: OcrJobStatus['result'] = {
            raw_text: text,
            corrected_text: text,
            confidence: 0,
            engine: 'tesseract-fallback',
            language: lang,
            processing_ms: 0,
            word_count: text.split(/\s+/).length,
          };
          completeJob(jobId, {
            rawText: text, correctedText: text,
            confidence: 0, engine: 'tesseract-fallback', processingMs: 0,
          });
          setState({ status: 'done', progress: 100, stage: 'processing', result: fallbackResult });
          return fallbackResult;
        }
      } catch { /* لا يوجد محرك محلي — أكمل للخطأ */ }
    }

    failJob(jobId, lastError);
    setState({ status: 'error', progress: 0, stage: 'upload', error: lastError });
    return null;
  }, [settings, startJob, updateJob, completeJob, failJob, clearCurrentJob]);

  const cancel = useCallback(() => {
    cancelRef.current = true;
  }, []);

  const reset = useCallback(() => {
    cancelRef.current = false;
    setState({ status: 'idle', progress: 0, stage: 'upload' });
    clearCurrentJob();
  }, [clearCurrentJob]);

  return { state, processImage, cancel, reset };
}
