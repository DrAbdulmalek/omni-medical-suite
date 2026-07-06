'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAppStore, ImageItem, LogItem } from '@/lib/store';
import {
  Upload,
  Crop,
  Eraser,
  RotateCcw,
  Save,
  SkipForward,
  Play,
  X,
  Image as ImageIcon,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Scissors,
  Sparkles,
  CheckCircle2,
  Hash,
  ArrowLeftRight,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import { ComparisonView } from '@/components/ComparisonView';
import { BatchProgress } from '@/components/BatchProgress';
import { QualityPanel } from '@/components/QualityPanel';
import { ThumbnailStrip } from '@/components/ThumbnailStrip';

interface ParsedSettings {
  pageThreshold?: number;
  grayThreshold?: number;
  padding?: number;
  minConfidence?: number;
}

export default function ImageProcessorView() {
  const {
    images,
    setImages,
    selectedImageId,
    setSelectedImageId,
    isProcessing,
    setIsProcessing,
    processingProgress,
    setProcessingProgress,
    logs,
    setLogs,
    settings,
    setSettings,
  } = useAppStore();

  const [cropLeft, setCropLeft] = useState(0);
  const [cropTop, setCropTop] = useState(0);
  const [cropRight, setCropRight] = useState(0);
  const [cropBottom, setCropBottom] = useState(0);
  const [deskewAngle, setDeskewAngle] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [aiParsedSettings, setAiParsedSettings] = useState<ParsedSettings | null>(null);
  const [extractingPageNumber, setExtractingPageNumber] = useState(false);
  const [pageNumber, setPageNumber] = useState<string | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const liveLogRef = useRef<HTMLDivElement>(null);

  const selectedImage = images.find((img) => img.id === selectedImageId);

  // Load images on mount
  useEffect(() => {
    loadImages();
    loadSettings();
  }, []);

  useEffect(() => {
    if (selectedImage) {
      setCropLeft(selectedImage.cropLeft);
      setCropTop(selectedImage.cropTop);
      setCropRight(selectedImage.cropRight);
      setCropBottom(selectedImage.cropBottom);
      setDeskewAngle(selectedImage.deskewAngle);
      setPageNumber(selectedImage.pageNumber || null);
    } else {
      setPageNumber(null);
    }
  }, [selectedImageId]);

  // Auto-scroll logs
  useEffect(() => {
    if (liveLogRef.current) {
      liveLogRef.current.scrollTop = liveLogRef.current.scrollHeight;
    }
  }, [logs]);

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      useAppStore.getState().setSettings(data.settings);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  }

  async function loadImages() {
    try {
      const res = await fetch('/api/images');
      const data = await res.json();
      setImages(data.images);
      if (data.images.length > 0 && !selectedImageId) {
        setSelectedImageId(data.images[0].id);
      }
    } catch (err) {
      console.error('Failed to load images:', err);
    }
  }

  async function loadLogs() {
    try {
      const res = await fetch('/api/logs');
      const data = await res.json();
      setLogs(data.logs);
    } catch (err) {
      console.error('Failed to load logs:', err);
    }
  }

  // Upload handler
  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);

    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append('files', f));

      const res = await fetch('/api/upload', { method: 'POST', body: formData });
      const data = await res.json();

      if (data.success) {
        await loadImages();
        await loadLogs();
        if (data.images.length > 0) {
          setSelectedImageId(data.images[0].id);
        }
      }
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  }, []);

  // Process actions
  async function processAction(action: string) {
    if (!selectedImageId) return;

    try {
      const res = await fetch(`/api/process/${selectedImageId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          cropLeft,
          cropTop,
          cropRight,
          cropBottom,
          deskewAngle,
          grayThreshold: settings?.grayThreshold || 230,
        }),
      });
      const data = await res.json();

      if (data.success) {
        await loadImages();
        await loadLogs();
      }
    } catch (err) {
      console.error('Process error:', err);
    }
  }

  // Process all
  async function processAll() {
    setIsProcessing(true);
    const pendingImages = images.filter((img) => img.status === 'pending');
    setProcessingProgress({ current: 0, total: pendingImages.length });

    try {
      for (let i = 0; i < pendingImages.length; i++) {
        setProcessingProgress({ current: i + 1, total: pendingImages.length });

        await fetch(`/api/process/${pendingImages[i].id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'smart_crop',
            grayThreshold: settings?.grayThreshold || 200,
          }),
        });
      }

      await loadImages();
      await loadLogs();
    } catch (err) {
      console.error('Batch process error:', err);
    } finally {
      setIsProcessing(false);
      setProcessingProgress({ current: 0, total: 0 });
    }
  }

  // AI Suggestion
  async function getAiSuggestion() {
    if (!selectedImage) return;
    setAiSuggesting(true);
    setAiSuggestion(null);
    setAiParsedSettings(null);

    const contextMsg = selectedImage
      ? `لدي صورة بعنوان "${selectedImage.originalName}" بأبعاد ${selectedImage.width}×${selectedImage.height}، حالة: ${selectedImage.status}، جودة قبل المعالجة: ${selectedImage.blurBefore}، جودة بعد المعالجة: ${selectedImage.blurAfter}، مستوى الثقة: ${Math.round(selectedImage.confidence * 100)}%، العمليات السابقة: ${selectedImage.operations.join('، ') || 'لا توجد'}. الإعدادات الحالية: عتبة الصفحة=${settings?.pageThreshold || 200}، عتبة الرمادي=${settings?.grayThreshold || 230}، حشوة=${settings?.padding || 10}px. اقترح أفضل إعدادات وعمليات معالجة لهذه الصورة. تضمين الإعدادات المقترحة في كتلة [SETTINGS].`
      : 'اقترح أفضل إعدادات لمعالجة صور مستندات طبية.';

    try {
      const res = await fetch('/api/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: contextMsg }] }),
      });
      const data = await res.json();
      setAiSuggestion(data.reply);
      setAiParsedSettings(data.parsedSettings || null);
    } catch {
      setAiSuggestion('عذراً، حدث خطأ في الاتصال بالمساعد الذكي.');
    } finally {
      setAiSuggesting(false);
    }
  }

  async function applyAiSuggestion() {
    if (!aiParsedSettings || Object.keys(aiParsedSettings).length === 0) return;

    try {
      const currentSettings = useAppStore.getState().settings || {};
      const payload = {
        pageThreshold: aiParsedSettings.pageThreshold ?? currentSettings.pageThreshold ?? 200,
        grayThreshold: aiParsedSettings.grayThreshold ?? currentSettings.grayThreshold ?? 230,
        padding: aiParsedSettings.padding ?? currentSettings.padding ?? 10,
        minConfidence: aiParsedSettings.minConfidence ?? currentSettings.minConfidence ?? 0.85,
        autoSave: currentSettings.autoSave ?? true,
        autoDeskew: currentSettings.autoDeskew ?? true,
        autoCrop: currentSettings.autoCrop ?? true,
      };

      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (data.success) {
        setSettings(data.settings);
        toast.success('تم تطبيق اقتراح الذكاء الاصطناعي بنجاح', {
          description: 'تم تحديث الإعدادات تلقائياً',
          duration: 3000,
        });
      }
    } catch {
      toast.error('فشل في تطبيق الإعدادات', {
        description: 'حدث خطأ أثناء التحديث',
        duration: 3000,
      });
    }
  }

  // Extract page number via OCR
  async function extractPageNumber() {
    if (!selectedImageId) return;
    setExtractingPageNumber(true);

    try {
      const res = await fetch('/api/extract-page-number', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageId: selectedImageId }),
      });
      const data = await res.json();

      if (data.success) {
        setPageNumber(data.pageNumber || 'لم يتم العثور على رقم صفحة');
        if (data.pageNumber) {
          toast.success(`رقم الصفحة: ${data.pageNumber}`, { duration: 3000 });
        } else {
          toast.info('لم يتم العثور على رقم صفحة في هذه الصورة', { duration: 3000 });
        }
        await loadImages();
      }
    } catch {
      toast.error('فشل في استخراج رقم الصفحة');
    } finally {
      setExtractingPageNumber(false);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case 'processed':
        return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">تمت المعالجة</Badge>;
      case 'pending':
        return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">قيد الانتظار</Badge>;
      case 'skipped':
        return <Badge className="bg-slate-100 text-slate-500 hover:bg-slate-100">تم تخطيها</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  }

  // Navigate between images
  function navigateImage(direction: 'prev' | 'next') {
    const currentIndex = images.findIndex((img) => img.id === selectedImageId);
    if (direction === 'next' && currentIndex < images.length - 1) {
      setSelectedImageId(images[currentIndex + 1].id);
    } else if (direction === 'prev' && currentIndex > 0) {
      setSelectedImageId(images[currentIndex - 1].id);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-0px)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 lg:px-6 border-b bg-white">
        <div>
          <h2 className="text-xl font-bold text-slate-900">معالجة الصور</h2>
          <p className="text-sm text-slate-500">
            {images.length} صورة — {images.filter((i) => i.status === 'pending').length} قيد الانتظار
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="bg-emerald-600 hover:bg-emerald-700"
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin ml-2" />
            ) : (
              <Upload className="h-4 w-4 ml-2" />
            )}
            رفع صور
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
          <Button
            onClick={processAll}
            disabled={isProcessing || images.filter((i) => i.status === 'pending').length === 0}
            variant="outline"
            className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
          >
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin ml-2" />
            ) : (
              <Play className="h-4 w-4 ml-2" />
            )}
            معالجة الكل
          </Button>
        </div>
      </div>

      {/* Processing Progress */}
      {isProcessing && (
        <div className="px-4 lg:px-6 py-2 bg-emerald-50 border-b border-emerald-100">
          <div className="flex items-center gap-3">
            <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
            <span className="text-sm text-emerald-700">
              جارٍ المعالجة... {processingProgress.current} من {processingProgress.total}
            </span>
            <Progress
              value={(processingProgress.current / processingProgress.total) * 100}
              className="flex-1 h-2"
            />
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Image List - Left panel */}
        <div className="w-48 lg:w-64 border-l bg-white flex-shrink-0 flex flex-col">
          <div className="p-3 border-b">
            <h3 className="text-sm font-semibold text-slate-700">قائمة الصور</h3>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {images.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  <ImageIcon className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  لا توجد صور
                  <br />
                  <span className="text-xs">اسحب الصور هنا أو اضغط &quot;رفع صور&quot;</span>
                </div>
              ) : (
                images.map((img) => (
                  <button
                    key={img.id}
                    onClick={() => setSelectedImageId(img.id)}
                    className={`w-full flex items-center gap-2 p-2 rounded-lg text-right transition-all ${
                      selectedImageId === img.id
                        ? 'bg-emerald-50 border border-emerald-200'
                        : 'hover:bg-slate-50 border border-transparent'
                    }`}
                  >
                    <div className="w-10 h-10 rounded bg-slate-100 overflow-hidden flex-shrink-0 flex items-center justify-center">
                      <ImageIcon className="h-4 w-4 text-slate-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-700 truncate">
                        {img.originalName}
                      </p>
                      <div className="text-[10px] text-slate-400">
                        {img.width}×{img.height}
                        {img.pageNumber && <span className="text-emerald-500 mr-1">ص{img.pageNumber}</span>}
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          img.status === 'processed'
                            ? 'bg-emerald-500'
                            : img.status === 'skipped'
                            ? 'bg-slate-300'
                            : 'bg-amber-400'
                        }`}
                      />
                    </div>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Center - Image Preview */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedImage ? (
            <>
              {/* Preview Area */}
              <div className="flex-1 relative bg-slate-100 overflow-hidden">
                {/* Drag and drop overlay */}
                <div
                  className={`absolute inset-0 z-10 transition-all ${
                    dragOver ? 'bg-emerald-100/80 border-4 border-dashed border-emerald-400' : 'hidden'
                  } flex items-center justify-center`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files); }}
                >
                  <div className="text-center">
                    <Upload className="h-12 w-12 text-emerald-500 mx-auto mb-3" />
                    <p className="text-emerald-700 font-semibold">أسقط الصور هنا</p>
                  </div>
                </div>

                {/* Image with crop overlay */}
                <div className="absolute inset-0 flex items-center justify-center p-4">
                  <div className="relative max-w-full max-h-full">
                    <img
                      src={`/api/preview?file=${encodeURIComponent(`/home/z/my-project/uploads/${selectedImage.fileName}`)}`}
                      alt={selectedImage.originalName}
                      className="max-w-full max-h-[calc(100vh-320px)] object-contain rounded shadow-lg"
                      style={{
                        padding: `${cropTop}px ${cropRight}px ${cropBottom}px ${cropLeft}px`,
                        background: 'repeating-conic-gradient(#ddd 0% 25%, white 0% 50%) 50% / 16px 16px',
                      }}
                    />

                    {/* Crop indicators */}
                    {cropLeft > 0 && (
                      <div
                        className="absolute top-0 right-0 bottom-0 bg-red-200/30 border-r-2 border-dashed border-red-400 flex items-center justify-center"
                        style={{ width: `${(cropLeft / (selectedImage.width || 1)) * 100}%`, maxWidth: '60px' }}
                      >
                        <span className="text-xs text-red-600 font-medium writing-mode-vertical" style={{ writingMode: 'vertical-rl' }}>
                          {cropLeft}px
                        </span>
                      </div>
                    )}
                    {cropRight > 0 && (
                      <div
                        className="absolute top-0 left-0 bottom-0 bg-red-200/30 border-l-2 border-dashed border-red-400 flex items-center justify-center"
                        style={{ width: `${(cropRight / (selectedImage.width || 1)) * 100}%`, maxWidth: '60px' }}
                      >
                        <span className="text-xs text-red-600 font-medium" style={{ writingMode: 'vertical-rl' }}>
                          {cropRight}px
                        </span>
                      </div>
                    )}
                    {cropTop > 0 && (
                      <div
                        className="absolute top-0 left-0 right-0 bg-red-200/30 border-b-2 border-dashed border-red-400 flex items-center justify-center"
                        style={{ height: `${(cropTop / (selectedImage.height || 1)) * 100}%`, maxHeight: '60px' }}
                      >
                        <span className="text-xs text-red-600 font-medium">{cropTop}px</span>
                      </div>
                    )}
                    {cropBottom > 0 && (
                      <div
                        className="absolute bottom-0 left-0 right-0 bg-red-200/30 border-t-2 border-dashed border-red-400 flex items-center justify-center"
                        style={{ height: `${(cropBottom / (selectedImage.height || 1)) * 100}%`, maxHeight: '60px' }}
                      >
                        <span className="text-xs text-red-600 font-medium">{cropBottom}px</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Navigation */}
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="icon"
                    onClick={() => navigateImage('next')}
                    disabled={images.findIndex((i) => i.id === selectedImageId) === 0}
                    className="h-8 w-8 rounded-full"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-slate-500 bg-white/80 px-3 py-1 rounded-full">
                    {images.findIndex((i) => i.id === selectedImageId) + 1} / {images.length}
                  </span>
                  <Button
                    variant="secondary"
                    size="icon"
                    onClick={() => navigateImage('prev')}
                    disabled={images.findIndex((i) => i.id === selectedImageId) === images.length - 1}
                    className="h-8 w-8 rounded-full"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* Quality Panel & Thumbnail Strip */}
              <div className="px-4 py-2 bg-white border-t">
                <div className="max-w-md">
                  <QualityPanel />
                </div>
                <div className="mt-2">
                  <ThumbnailStrip />
                </div>
              </div>

              {/* Image Info Bar */}
              <div className="flex items-center justify-between px-4 py-2 bg-white border-t text-xs text-slate-500">
                <div className="flex items-center gap-4">
                  <span>{selectedImage.originalName}</span>
                  <span>{selectedImage.width}×{selectedImage.height}</span>
                  {getStatusBadge(selectedImage.status)}
                  {pageNumber && pageNumber !== 'لم يتم العثور على رقم صفحة' && (
                    <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100">
                      <Hash className="h-3 w-3 ml-1" />
                      صفحة {pageNumber}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  {selectedImage.blurBefore > 0 && (
                    <span>جودة قبل: <strong>{Math.round(selectedImage.blurBefore)}</strong></span>
                  )}
                  {selectedImage.blurAfter > 0 && (
                    <span>جودة بعد: <strong>{Math.round(selectedImage.blurAfter)}</strong></span>
                  )}
                  {selectedImage.operations.length > 0 && (
                    <span>{selectedImage.operations.length} عمليات</span>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div
              className="flex-1 flex items-center justify-center bg-slate-50"
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files); }}
            >
              <div className={`text-center p-8 rounded-2xl border-2 border-dashed transition-colors ${
                dragOver ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200'
              }`}>
                <Upload className="h-16 w-16 text-slate-300 mx-auto mb-4" />
                <p className="text-lg font-medium text-slate-500">اسحب الصور وأفلتها هنا</p>
                <p className="text-sm text-slate-400 mt-2">
                  أو اضغط على زر &quot;رفع صور&quot; لاختيار الملفات
                </p>
                <p className="text-xs text-slate-300 mt-4">
                  يدعم: JPG, PNG, WebP, TIFF
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Controls Panel */}
        <div className="w-64 lg:w-72 border-r bg-white flex-shrink-0 flex flex-col overflow-y-auto">
          <div className="p-4 space-y-6">
            {/* Crop Controls */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <Scissors className="h-4 w-4 text-emerald-600" />
                إعدادات القص
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500">يسار</span>
                    <span className="font-medium text-slate-700">{cropLeft}px</span>
                  </div>
                  <Slider
                    value={[cropLeft]}
                    onValueChange={([v]) => setCropLeft(v)}
                    max={500}
                    step={1}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500">أعلى</span>
                    <span className="font-medium text-slate-700">{cropTop}px</span>
                  </div>
                  <Slider
                    value={[cropTop]}
                    onValueChange={([v]) => setCropTop(v)}
                    max={500}
                    step={1}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500">يمين</span>
                    <span className="font-medium text-slate-700">{cropRight}px</span>
                  </div>
                  <Slider
                    value={[cropRight]}
                    onValueChange={([v]) => setCropRight(v)}
                    max={500}
                    step={1}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500">أسفل</span>
                    <span className="font-medium text-slate-700">{cropBottom}px</span>
                  </div>
                  <Slider
                    value={[cropBottom]}
                    onValueChange={([v]) => setCropBottom(v)}
                    max={500}
                    step={1}
                    className="w-full"
                  />
                </div>
              </div>
            </div>

            {/* Deskew */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
                <RotateCcw className="h-4 w-4 text-emerald-600" />
                الميلان
              </h3>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500">زاوية الميلان</span>
                  <span className="font-medium text-slate-700">{deskewAngle}°</span>
                </div>
                <Slider
                  value={[deskewAngle]}
                  onValueChange={([v]) => setDeskewAngle(v)}
                  min={-15}
                  max={15}
                  step={0.1}
                  className="w-full"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">الإجراءات</h3>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() => processAction('smart_crop')}
                  disabled={!selectedImageId}
                  variant="outline"
                  className="border-emerald-200 text-emerald-700 hover:bg-emerald-50 text-xs h-9"
                >
                  <Crop className="h-3.5 w-3.5 ml-1" />
                  قص ذكي
                </Button>
                <Button
                  onClick={() => processAction('remove_gray')}
                  disabled={!selectedImageId}
                  variant="outline"
                  className="border-orange-200 text-orange-700 hover:bg-orange-50 text-xs h-9"
                >
                  <Eraser className="h-3.5 w-3.5 ml-1" />
                  إزالة رمادي
                </Button>
                <Button
                  onClick={() => processAction('detect_skew_auto')}
                  disabled={!selectedImageId}
                  variant="outline"
                  className="border-blue-200 text-blue-700 hover:bg-blue-50 text-xs h-9"
                >
                  <RotateCcw className="h-3.5 w-3.5 ml-1" />
                  كشف ميلان تلقائي
                </Button>
                <Button
                  onClick={extractPageNumber}
                  disabled={!selectedImageId || extractingPageNumber}
                  variant="outline"
                  className="border-teal-200 text-teal-700 hover:bg-teal-50 text-xs h-9"
                >
                  {extractingPageNumber ? (
                    <Loader2 className="h-3.5 w-3.5 ml-1 animate-spin" />
                  ) : (
                    <Hash className="h-3.5 w-3.5 ml-1" />
                  )}
                  رقم الصفحة
                </Button>
                <Button
                  onClick={() => processAction('auto_crop_smart')}
                  disabled={!selectedImageId}
                  variant="outline"
                  className="border-violet-200 text-violet-700 hover:bg-violet-50 text-xs h-9"
                >
                  <Crop className="h-3.5 w-3.5 ml-1" />
                  قص ذكي (مرحلتين)
                </Button>
              </div>
              <Button
                onClick={() => processAction('manual_crop')}
                disabled={!selectedImageId}
                variant="outline"
                className="w-full border-purple-200 text-purple-700 hover:bg-purple-50 text-xs h-9"
              >
                <Scissors className="h-3.5 w-3.5 ml-1" />
                تطبيق القص
              </Button>
              <Button
                onClick={() => setShowComparison(true)}
                disabled={!selectedImageId}
                variant="outline"
                className="w-full border-cyan-200 text-cyan-700 hover:bg-cyan-50 text-xs h-9"
              >
                <ArrowLeftRight className="h-3.5 w-3.5 ml-1" />
                مقارنة
              </Button>
              <Button
                onClick={() => processAction('remove_shadow')}
                disabled={!selectedImageId}
                variant="outline"
                className="w-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs h-9"
              >
                <Wand2 className="h-3.5 w-3.5 ml-1" />
                إزالة الظلال
              </Button>
              {/* AI Suggestion Button */}
              <div className="pt-2">
                <Button
                  onClick={getAiSuggestion}
                  disabled={!selectedImageId || aiSuggesting}
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-xs h-9"
                >
                  {aiSuggesting ? (
                    <Loader2 className="h-3.5 w-3.5 ml-1 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5 ml-1" />
                  )}
                  {aiSuggesting ? 'جارٍ التحليل...' : 'AI اقتراح'}
                </Button>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Button
                  onClick={() => processAction('save')}
                  disabled={!selectedImageId}
                  className="bg-emerald-600 hover:bg-emerald-700 text-xs h-9"
                >
                  <Save className="h-3.5 w-3.5 ml-1" />
                  حفظ
                </Button>
                <Button
                  onClick={() => processAction('skip')}
                  disabled={!selectedImageId}
                  variant="outline"
                  className="text-xs h-9"
                >
                  <SkipForward className="h-3.5 w-3.5 ml-1" />
                  تخطي
                </Button>
              </div>
            </div>

            {/* AI Suggestion Result */}
            {aiSuggestion && (
              <div className="p-3 rounded-lg bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-emerald-700 flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    اقتراح الذكاء الاصطناعي
                  </h3>
                  <button
                    onClick={() => { setAiSuggestion(null); setAiParsedSettings(null); }}
                    className="text-slate-400 hover:text-slate-600"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                  {aiSuggestion}
                </p>
                {aiParsedSettings && Object.keys(aiParsedSettings).length > 0 && (
                  <div className="mt-2 p-2 rounded-lg bg-white/60 border border-emerald-100">
                    <p className="text-[10px] font-semibold text-emerald-600 mb-1">الإعدادات المقترحة:</p>
                    <div className="flex flex-wrap gap-1">
                      {aiParsedSettings.pageThreshold !== undefined && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          عتبة الصفحة: {aiParsedSettings.pageThreshold}
                        </span>
                      )}
                      {aiParsedSettings.grayThreshold !== undefined && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          عتبة الرمادي: {aiParsedSettings.grayThreshold}
                        </span>
                      )}
                      {aiParsedSettings.padding !== undefined && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          الحشوة: {aiParsedSettings.padding}px
                        </span>
                      )}
                      {aiParsedSettings.minConfidence !== undefined && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">
                          الثقة: {Math.round(aiParsedSettings.minConfidence * 100)}%
                        </span>
                      )}
                    </div>
                  </div>
                )}
                <Button
                  onClick={applyAiSuggestion}
                  size="sm"
                  disabled={!aiParsedSettings || Object.keys(aiParsedSettings).length === 0}
                  className="mt-2 h-7 text-xs bg-emerald-600 hover:bg-emerald-700"
                >
                  <CheckCircle2 className="h-3 w-3 ml-1" />
                  تطبيق الإعدادات تلقائياً
                </Button>
              </div>
            )}

            {/* Page Number Result */}
            {pageNumber && pageNumber !== 'لم يتم العثور على رقم صفحة' && (
              <div className="p-3 rounded-lg bg-gradient-to-br from-teal-50 to-cyan-50 border border-teal-200">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-semibold text-teal-700 flex items-center gap-1.5">
                    <Hash className="h-3.5 w-3.5" />
                    رقم الصفحة
                  </h3>
                </div>
                <p className="text-lg font-bold text-teal-800">{pageNumber}</p>
              </div>
            )}

            {/* Batch Progress */}
            <BatchProgress />

            {/* Operations History */}
            {selectedImage && selectedImage.operations.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-slate-700 mb-2">العمليات</h3>
                <div className="space-y-1">
                  {selectedImage.operations.map((op, i) => (
                    <div key={i} className="text-xs text-slate-500 bg-slate-50 rounded px-2 py-1">
                      {op}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Live Log */}
          <div className="border-t flex-1 flex flex-col min-h-0">
            <div className="p-3 border-b">
              <h3 className="text-sm font-semibold text-slate-700">السجل المباشر</h3>
            </div>
            <div ref={liveLogRef} className="flex-1 overflow-y-auto p-2 space-y-1 max-h-48">
              {logs.slice(0, 30).map((log) => (
                <div key={log.id} className="text-[11px] text-slate-500 flex gap-2">
                  <span className="text-slate-300 flex-shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="truncate">{log.details || log.action}</span>
                </div>
              ))}
              {logs.length === 0 && (
                <div className="text-xs text-slate-300 text-center py-4">لا توجد سجلات</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Comparison Dialog */}
      {showComparison && selectedImage && (
        <ComparisonView
          imageId={selectedImage.id}
          originalName={selectedImage.fileName}
          onClose={() => setShowComparison(false)}
        />
      )}
    </div>
  );
}
