/**
 * mobile/android/screens/ImagePreviewScreen.tsx
 * ================================================
 * شاشة معاينة الصورة قبل إرسالها للـ OCR
 * - تدوير + اقتصاص
 * - فحص جودة نهائي
 * - رفع مع progress bar
 * - polling حتى اكتمال OCR
 */

import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, Image,
  TouchableOpacity, Alert, ScrollView,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { useOcrStore, useSettingsStore, useDocumentsStore } from '../store';
import { OcrService } from '../services/api';

// ─── Progress Bar ─────────────────────────────────────────────

function ProgressBar({ value, stage }: { value: number; stage: 'upload' | 'processing' }) {
  const color = stage === 'upload' ? '#2E86C1' : '#27AE60';
  const label = stage === 'upload'
    ? `جارٍ رفع الملف… ${value}%`
    : `جارٍ استخراج النص… ${value}%`;

  return (
    <View style={styles.progressContainer}>
      <Text style={styles.progressLabel}>{label}</Text>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${value}%`, backgroundColor: color }]} />
      </View>
    </View>
  );
}

// ─── Main Screen ────────────────────────────────────────────

export default function ImagePreviewScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { imageUri, isPdf = false } = route.params || {};

  const { settings } = useSettingsStore();
  const { startJob, updateJob, completeJob, failJob } = useOcrStore();
  const { addDocument } = useDocumentsStore();

  const [rotation, setRotation] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<'upload' | 'processing'>('upload');

  const rotate = useCallback(() => {
    setRotation(r => (r + 90) % 360);
  }, []);

  const handleProcess = useCallback(async () => {
    if (!imageUri || processing) return;
    setProcessing(true);

    const jobId = startJob(imageUri);

    try {
      const fileName = isPdf
        ? `document_${Date.now()}.pdf`
        : `scan_${Date.now()}.jpg`;
      const mimeType = isPdf ? 'application/pdf' : 'image/jpeg';

      const result = await OcrService.processDocument(
        imageUri,
        fileName,
        mimeType,
        {
          engine: settings.ocrEngine === 'auto' ? undefined : settings.ocrEngine,
          language: settings.language === 'auto' ? undefined : settings.language,
          high_quality: settings.highQualityMode,
        },
        (pct, s) => {
          setProgress(pct);
          setStage(s);
          updateJob(jobId, { progress: pct, status: s === 'upload' ? 'uploading' : 'processing' });
        }
      );

      if (result.result) {
        completeJob(jobId, {
          rawText: result.result.raw_text,
          correctedText: result.result.corrected_text,
          confidence: result.result.confidence,
          engine: result.result.engine,
          processingMs: result.result.processing_ms,
        });

        // أضف للمستندات
        addDocument({
          id: result.document_id,
          filename: fileName,
          fileType: isPdf ? 'pdf' : 'image',
          status: result.result.confidence >= 0.7 ? 'completed' : 'review',
          rawText: result.result.raw_text,
          correctedText: result.result.corrected_text,
          confidence: Math.round(result.result.confidence * 100),
          engine: result.result.engine,
          language: result.result.language as any,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          localUri: imageUri,
        });

        navigation.navigate('OCRResult', { documentId: result.document_id, imageUri });
      } else {
        throw new Error('لم يُرجع الخادم نتيجة');
      }

    } catch (err: any) {
      failJob(jobId, err?.message || 'فشل المعالجة');
      Alert.alert(
        'فشل المعالجة',
        err?.message || 'تعذّر استخراج النص. تحقق من الاتصال وأعد المحاولة.',
        [{ text: 'حسناً' }]
      );
    } finally {
      setProcessing(false);
    }
  }, [imageUri, isPdf, processing, settings]);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>

      {/* Image Preview */}
      <View style={styles.imageContainer}>
        {imageUri ? (
          <Image
            source={{ uri: imageUri }}
            style={[styles.previewImage, { transform: [{ rotate: `${rotation}deg` }] }]}
            resizeMode="contain"
          />
        ) : (
          <View style={styles.pdfPlaceholder}>
            <Text style={styles.pdfIcon}>📄</Text>
            <Text style={styles.pdfLabel}>ملف PDF</Text>
          </View>
        )}
      </View>

      {/* Quality Hints */}
      <View style={styles.hintsContainer}>
        <Text style={styles.hintsTitle}>قبل الإرسال تأكد من:</Text>
        {[
          'النص واضح وقابل للقراءة',
          'الصورة مستقيمة (استخدم التدوير إذا لزم)',
          'الإضاءة كافية',
          'لا يوجد ظل يحجب النص',
        ].map((hint, i) => (
          <Text key={i} style={styles.hint}>✓ {hint}</Text>
        ))}
      </View>

      {/* Progress */}
      {processing && (
        <ProgressBar value={progress} stage={stage} />
      )}

      {/* Actions */}
      <View style={styles.actions}>
        {!processing && (
          <TouchableOpacity style={styles.rotateButton} onPress={rotate}>
            <Text style={styles.rotateButtonText}>↻ تدوير</Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity
          style={[styles.processButton, processing && styles.processButtonDisabled]}
          onPress={handleProcess}
          disabled={processing}
        >
          {processing
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.processButtonText}>🚀 استخراج النص</Text>
          }
        </TouchableOpacity>

        {!processing && (
          <TouchableOpacity
            style={styles.retakeButton}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.retakeButtonText}>📷 إعادة التقاط</Text>
          </TouchableOpacity>
        )}
      </View>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#F4F6F7' },
  content: { padding: 16, paddingBottom: 40 },

  imageContainer: {
    backgroundColor: '#1a1a2e',
    borderRadius: 12, overflow: 'hidden',
    height: 340, marginBottom: 16,
    alignItems: 'center', justifyContent: 'center',
  },
  previewImage: { width: '100%', height: '100%' },
  pdfPlaceholder: { alignItems: 'center' },
  pdfIcon: { fontSize: 72, marginBottom: 8 },
  pdfLabel: { color: '#fff', fontSize: 16 },

  hintsContainer: {
    backgroundColor: '#fff', borderRadius: 10,
    padding: 14, marginBottom: 16,
    borderLeftWidth: 4, borderLeftColor: '#2E86C1',
  },
  hintsTitle: {
    fontSize: 13, fontWeight: '600',
    color: '#2E86C1', marginBottom: 8, textAlign: 'right',
  },
  hint: { fontSize: 12, color: '#5D6D7E', marginBottom: 4, textAlign: 'right' },

  progressContainer: {
    backgroundColor: '#fff', borderRadius: 10,
    padding: 14, marginBottom: 16,
  },
  progressLabel: {
    fontSize: 13, color: '#1A252F',
    marginBottom: 8, textAlign: 'right',
  },
  progressTrack: {
    height: 8, backgroundColor: '#D5D8DC',
    borderRadius: 4, overflow: 'hidden',
  },
  progressFill: { height: '100%', borderRadius: 4 },

  actions: { gap: 10 },
  rotateButton: {
    backgroundColor: '#fff', borderRadius: 10,
    padding: 14, alignItems: 'center',
    borderWidth: 1.5, borderColor: '#2E86C1',
  },
  rotateButtonText: { color: '#2E86C1', fontSize: 15, fontWeight: '600' },
  processButton: {
    backgroundColor: '#1B4F72', borderRadius: 10,
    padding: 18, alignItems: 'center',
  },
  processButtonDisabled: { opacity: 0.6 },
  processButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  retakeButton: {
    backgroundColor: '#F4F6F7', borderRadius: 10,
    padding: 14, alignItems: 'center',
    borderWidth: 1, borderColor: '#D5D8DC',
  },
  retakeButtonText: { color: '#5D6D7E', fontSize: 15 },
});
