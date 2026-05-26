'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileText,
  Check,
  SkipForward,
  ChevronLeft,
  ChevronRight,
  Download,
  Trash2,
  Loader2,
  Pencil,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Filter,
  SaveAll,
  Image as ImageIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';

// Types
interface WordItem {
  id: string;
  originalText: string;
  correctedText: string;
  confidence: number;
  imagePath: string;
  x: number;
  y: number;
  width: number;
  height: number;
  lineIndex: number;
  wordIndex: number;
  status: string;
  imageDataUrl?: string;
}

interface PageData {
  pageNumber: number;
  pageImage: string; // base64
  words: WordItem[];
}

interface TrainingStats {
  total: number;
  pending: number;
  corrected: number;
  skipped: number;
}

// ============ PDF Rendering Utility ============

async function loadPdfPages(file: File): Promise<{ pages: string[]; name: string }> {
  // Dynamic import of pdfjs-dist for client-side rendering
  const pdfjsLib = await import('pdfjs-dist');

  // Set up worker
  pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/5.7.284/pdf.worker.min.mjs`;

  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const totalPages = pdf.numPages;

  const pages: string[] = [];

  for (let i = 1; i <= totalPages; i++) {
    const page = await pdf.getPage(i);
    const scale = 2.0; // Render at 2x for quality
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');

    if (!ctx) continue;

    await page.render({
      canvasContext: ctx,
      viewport,
    }).promise;

    pages.push(canvas.toDataURL('image/png'));
  }

  return { pages, name: file.name };
}

// ============ Confidence Badge ============

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 85
      ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
      : pct >= 50
        ? 'bg-amber-100 text-amber-700 border-amber-200'
        : 'bg-red-100 text-red-700 border-red-200';

  return (
    <Badge variant="outline" className={`text-xs font-medium ${color}`}>
      {pct}%
    </Badge>
  );
}

// ============ Status Badge ============

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'corrected':
      return (
        <Badge className="bg-emerald-500 text-white text-xs">مصحح</Badge>
      );
    case 'skipped':
      return (
        <Badge className="bg-gray-400 text-white text-xs">متخطى</Badge>
      );
    default:
      return (
        <Badge className="bg-amber-500 text-white text-xs">معلق</Badge>
      );
  }
}

// ============ Word Card ============

function WordCard({
  word,
  isActive,
  correctedText,
  onCorrectedTextChange,
  onSave,
  onSkip,
  onSelect,
}: {
  word: WordItem;
  isActive: boolean;
  correctedText: string;
  onCorrectedTextChange: (text: string) => void;
  onSave: () => void;
  onSkip: () => void;
  onSelect: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isActive && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isActive]);

  return (
    <Card
      className={`cursor-pointer transition-all duration-200 border-2 ${
        isActive
          ? 'border-emerald-500 shadow-lg shadow-emerald-500/20'
          : 'border-gray-200 hover:border-emerald-300'
      }`}
      onClick={onSelect}
    >
      <CardContent className="p-3">
        <div className="flex items-start gap-3">
          {/* Word Image */}
          <div className="flex-shrink-0 w-24 h-16 bg-gray-50 rounded-md border overflow-hidden flex items-center justify-center">
            {word.imageDataUrl ? (
              <img
                src={word.imageDataUrl}
                alt={word.originalText}
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <ImageIcon className="h-6 w-6 text-gray-300" />
            )}
          </div>

          {/* Word Details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={word.status} />
              <ConfidenceBadge confidence={word.confidence} />
              <span className="text-xs text-gray-400">
                سطر {word.lineIndex + 1} | كلمة {word.wordIndex + 1}
              </span>
            </div>

            <p className="text-xs text-gray-500 mb-1 truncate">
              OCR: {word.originalText || '(فارغ)'}
            </p>

            <div className="flex items-center gap-1">
              <Input
                ref={inputRef}
                value={isActive ? correctedText : word.correctedText || word.originalText}
                onChange={(e) => {
                  if (isActive) onCorrectedTextChange(e.target.value);
                }}
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => {
                  if (isActive) {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      onSave();
                    } else if (e.key === 'Tab') {
                      e.preventDefault();
                      onSkip();
                    }
                  }
                }}
                className="h-8 text-sm border-emerald-200 focus:border-emerald-500"
                placeholder="النص المصحح..."
                dir="rtl"
              />
            </div>
          </div>

          {/* Actions (visible when active) */}
          {isActive && (
            <div className="flex flex-col gap-1 flex-shrink-0">
              <Button
                size="sm"
                className="h-7 px-2 bg-emerald-500 hover:bg-emerald-600"
                onClick={(e) => {
                  e.stopPropagation();
                  onSave();
                }}
              >
                <Check className="h-3 w-3" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-gray-400 hover:text-gray-600"
                onClick={(e) => {
                  e.stopPropagation();
                  onSkip();
                }}
              >
                <SkipForward className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============ Main Component ============

export default function HandwritingTrainerView() {
  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [pdfName, setPdfName] = useState('');
  const [pages, setPages] = useState<PageData[]>([]);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState({ current: 0, total: 0 });
  const [processingMessage, setProcessingMessage] = useState('');

  // Word correction state
  const [allWords, setAllWords] = useState<WordItem[]>([]);
  const [activeWordIndex, setActiveWordIndex] = useState(0);
  const [editedTexts, setEditedTexts] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<string>('all');

  // Stats
  const [stats, setStats] = useState<TrainingStats>({ total: 0, pending: 0, corrected: 0, skipped: 0 });

  // View
  const [zoom, setZoom] = useState(1);
  const [showOverlay, setShowOverlay] = useState(true);

  // Load existing data on mount
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/api/training-words?limit=1000&includeImage=true');
        if (res.ok && !cancelled) {
          const data = await res.json();
          if (data.words && data.words.length > 0) {
            setAllWords(data.words);
            setStats(data.stats);
          }
        }
      } catch {
        // Silent fail
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // Get filtered words for current page
  const currentPageWords = pages.length > 0
    ? (pages[currentPageIndex]?.words || [])
    : allWords.filter(
        (w) =>
          (filter === 'all' || w.status === filter)
      );

  const activeWord = currentPageWords[activeWordIndex];

  // ============ PDF Upload & Processing ============

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('يرجى اختيار ملف PDF');
      return;
    }

    setIsUploading(true);
    setPdfName(file.name);

    try {
      toast.info('جاري تحميل ملف PDF...');

      // Render PDF pages on client side
      const { pages: renderedPages, name } = await loadPdfPages(file);
      setPdfName(name);

      toast.info(`تم تحميل ${renderedPages.length} صفحة. جاري المعالجة...`);

      // Process each page: send to server for segmentation
      const processedPages: PageData[] = [];
      setIsProcessing(true);

      for (let i = 0; i < renderedPages.length; i++) {
        setProcessingProgress({ current: i + 1, total: renderedPages.length });
        setProcessingMessage(`معالجة صفحة ${i + 1} من ${renderedPages.length}...`);

        try {
          const res = await fetch('/api/pdf-pages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              pageIndex: i,
              pdfName: name,
              imageData: renderedPages[i],
            }),
          });

          if (res.ok) {
            const data = await res.json();
            processedPages.push({
              pageNumber: data.pageNumber,
              pageImage: renderedPages[i],
              words: data.words || [],
            });
          } else {
            processedPages.push({
              pageNumber: i,
              pageImage: renderedPages[i],
              words: [],
            });
          }
        } catch {
          processedPages.push({
            pageNumber: i,
            pageImage: renderedPages[i],
            words: [],
          });
        }
      }

      setPages(processedPages);
      setIsProcessing(false);
      setIsUploading(false);
      setCurrentPageIndex(0);
      setActiveWordIndex(0);

      const totalWords = processedPages.reduce((sum, p) => sum + p.words.length, 0);
      toast.success(`تم معالجة ${renderedPages.length} صفحة و ${totalWords} كلمة`);

      // Refresh stats
      try {
        const res = await fetch('/api/training-words?limit=1000');
        if (res.ok) {
          const data = await res.json();
          setStats(data.stats);
        }
      } catch {
        // Silent
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('فشل في تحميل الملف');
      setIsUploading(false);
      setIsProcessing(false);
    }
  };

  // ============ Word Correction ============

  const moveToNextPending = () => {
    const words = currentPageWords;
    // Find next pending word
    for (let i = activeWordIndex + 1; i < words.length; i++) {
      if (words[i].status === 'pending') {
        setActiveWordIndex(i);
        return;
      }
    }
    // If no pending after current, try from start
    for (let i = 0; i < activeWordIndex; i++) {
      if (words[i].status === 'pending') {
        setActiveWordIndex(i);
        return;
      }
    }
    // If all done, move to next page
    if (pages.length > 0 && currentPageIndex < pages.length - 1) {
      setCurrentPageIndex(currentPageIndex + 1);
      setActiveWordIndex(0);
    }
  };

  const handleSaveWord = async () => {
    if (!activeWord) return;

    const text = editedTexts[activeWord.id] ?? activeWord.originalText;
    const wordId = activeWord.id;

    try {
      const res = await fetch('/api/word-correction', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: wordId,
          correctedText: text,
          status: 'corrected',
        }),
      });

      if (res.ok) {
        setAllWords((prev) =>
          prev.map((w) =>
            w.id === wordId
              ? { ...w, correctedText: text, status: 'corrected' }
              : w
          )
        );

        setPages((prev) =>
          prev.map((p) => ({
            ...p,
            words: p.words.map((w) =>
              w.id === wordId
                ? { ...w, correctedText: text, status: 'corrected' }
                : w
            ),
          }))
        );

        setEditedTexts((prev) => {
          const next = { ...prev };
          delete next[wordId];
          return next;
        });

        setStats((prev) => ({
          ...prev,
          corrected: prev.corrected + 1,
          pending: Math.max(0, prev.pending - 1),
        }));

        moveToNextPending();
        toast.success('تم الحفظ');
      }
    } catch {
      toast.error('فشل في الحفظ');
    }
  };

  const handleSkipWord = async () => {
    if (!activeWord) return;

    const wordId = activeWord.id;

    try {
      const res = await fetch('/api/word-correction', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: wordId,
          status: 'skipped',
        }),
      });

      if (res.ok) {
        setAllWords((prev) =>
          prev.map((w) =>
            w.id === wordId ? { ...w, status: 'skipped' } : w
          )
        );

        setPages((prev) =>
          prev.map((p) => ({
            ...p,
            words: p.words.map((w) =>
              w.id === wordId ? { ...w, status: 'skipped' } : w
            ),
          }))
        );

        setStats((prev) => ({
          ...prev,
          skipped: prev.skipped + 1,
          pending: Math.max(0, prev.pending - 1),
        }));

        moveToNextPending();
      }
    } catch {
      toast.error('فشل في التخطي');
    }
  };

  const handleExportTrainingData = async () => {
    try {
      toast.info('جاري تصدير بيانات التدريب...');
      const res = await fetch('/api/export-training', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        toast.success(data.message || 'تم تصدير البيانات بنجاح');
      } else {
        const data = await res.json();
        toast.error(data.error || 'فشل في التصدير');
      }
    } catch {
      toast.error('فشل في التصدير');
    }
  };

  const handleClearData = async () => {
    try {
      const res = await fetch('/api/training-words?all=true', { method: 'DELETE' });
      if (res.ok) {
        setAllWords([]);
        setPages([]);
        setStats({ total: 0, pending: 0, corrected: 0, skipped: 0 });
        toast.success('تم مسح جميع البيانات');
      }
    } catch {
      toast.error('فشل في المسح');
    }
  };

  // Load word images when switching pages
  useEffect(() => {
    if (pages.length === 0) return;
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch('/api/training-words?includeImage=true&limit=1000');
        if (res.ok && !cancelled) {
          const data = await res.json();
          const imgMap = new Map(data.words.map((w: WordItem) => [w.id, w.imageDataUrl]));
          setAllWords((prev) =>
            prev.map((w) => ({
              ...w,
              imageDataUrl: imgMap.get(w.id) || w.imageDataUrl,
            }))
          );
        }
      } catch {
        // Silent
      }
    };
    load();
    return () => { cancelled = true; };
  }, [currentPageIndex, pages]);

  // ============ Render ============

  return (
    <div className="h-full flex flex-col" dir="rtl">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 shadow-sm flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-500 text-white flex items-center justify-center">
              <Pencil className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">تدريب خط اليد</h1>
              <p className="text-xs text-gray-500">
                {pdfName || 'قم برفع ملف PDF لبدء التدريب'}
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs">
                الكل: {stats.total}
              </Badge>
              <Badge className="bg-emerald-500 text-white text-xs">
                مصحح: {stats.corrected}
              </Badge>
              <Badge className="bg-amber-500 text-white text-xs">
                معلق: {stats.pending}
              </Badge>
              <Badge className="bg-gray-400 text-white text-xs">
                متخطى: {stats.skipped}
              </Badge>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {stats.total > 0 && (
          <div className="flex items-center gap-3">
            <Progress
              value={(stats.corrected / stats.total) * 100}
              className="flex-1 h-2"
            />
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {Math.round((stats.corrected / stats.total) * 100)}% مكتمل
            </span>
          </div>
        )}

        {/* Processing progress */}
        {isProcessing && (
          <div className="mt-3">
            <div className="flex items-center gap-2 text-sm text-emerald-600 mb-1">
              <Loader2 className="h-4 w-4 animate-spin" />
              {processingMessage}
            </div>
            <Progress
              value={(processingProgress.current / processingProgress.total) * 100}
              className="h-2"
            />
          </div>
        )}
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        {pages.length === 0 && allWords.length === 0 ? (
          // Upload Phase
          <div className="h-full flex items-center justify-center p-8">
            <div className="max-w-lg w-full">
              <label className="flex flex-col items-center justify-center w-full h-72 border-2 border-dashed border-gray-300 rounded-2xl cursor-pointer hover:border-emerald-400 hover:bg-emerald-50/50 transition-all duration-300 group">
                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                  <div className="h-16 w-16 mb-4 rounded-2xl bg-emerald-100 text-emerald-500 flex items-center justify-center group-hover:bg-emerald-200 group-hover:text-emerald-600 transition-colors">
                    <Upload className="h-8 w-8" />
                  </div>
                  <p className="mb-2 text-sm font-medium text-gray-700">
                    اضغط لرفع ملف PDF
                  </p>
                  <p className="text-xs text-gray-500">
                    سيتم تقسيم النصوص إلى كلمات فردية لتدريب النموذج
                  </p>
                </div>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={isUploading}
                />
              </label>

              {isUploading && (
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-emerald-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  جاري تحميل الملف...
                </div>
              )}
            </div>
          </div>
        ) : (
          // Training Phase
          <div className="h-full flex">
            {/* Left Panel - Page Thumbnails */}
            <aside className="w-48 border-l bg-white flex-shrink-0 flex flex-col">
              <div className="p-3 border-b">
                <h3 className="text-xs font-semibold text-gray-700 mb-2">الصفحات</h3>
                {pages.length > 0 && (
                  <Select
                    value={String(currentPageIndex)}
                    onValueChange={(v) => {
                      setCurrentPageIndex(parseInt(v));
                      setActiveWordIndex(0);
                    }}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {pages.map((p, i) => (
                        <SelectItem key={i} value={String(i)} className="text-xs">
                          صفحة {i + 1} ({p.words.length} كلمة)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                  {pages.map((page, idx) => {
                    const corrected = page.words.filter(
                      (w) => w.status === 'corrected'
                    ).length;
                    const total = page.words.length;
                    return (
                      <button
                        key={idx}
                        onClick={() => {
                          setCurrentPageIndex(idx);
                          setActiveWordIndex(0);
                        }}
                        className={`w-full rounded-lg border-2 overflow-hidden transition-all ${
                          idx === currentPageIndex
                            ? 'border-emerald-500 shadow-md'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="bg-gray-50 h-24 flex items-center justify-center overflow-hidden">
                          <img
                            src={page.pageImage}
                            alt={`Page ${idx + 1}`}
                            className="w-full h-full object-contain"
                          />
                        </div>
                        <div className="p-1.5 text-xs text-center">
                          صفحة {idx + 1}
                          <div className="flex items-center justify-center gap-1 mt-0.5">
                            <div className="flex-1 h-1 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-emerald-500 rounded-full"
                                style={{
                                  width: total > 0 ? `${(corrected / total) * 100}%` : '0%',
                                }}
                              />
                            </div>
                            <span className="text-[10px] text-gray-400">
                              {corrected}/{total}
                            </span>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </ScrollArea>

              {/* Page navigation */}
              {pages.length > 1 && (
                <div className="p-3 border-t flex items-center justify-between">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    disabled={currentPageIndex >= pages.length - 1}
                    onClick={() => {
                      setCurrentPageIndex((p) => p + 1);
                      setActiveWordIndex(0);
                    }}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-xs text-gray-500">
                    {currentPageIndex + 1}/{pages.length}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    disabled={currentPageIndex <= 0}
                    onClick={() => {
                      setCurrentPageIndex((p) => p - 1);
                      setActiveWordIndex(0);
                    }}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </aside>

            {/* Center - Page Image with Overlay */}
            <section className="flex-1 bg-gray-100 relative overflow-hidden">
              {pages.length > 0 && pages[currentPageIndex] && (
                <>
                  {/* Zoom controls */}
                  <div className="absolute top-3 left-3 z-10 flex items-center gap-1 bg-white rounded-lg shadow-md p-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
                    >
                      <ZoomIn className="h-3 w-3" />
                    </Button>
                    <span className="text-xs text-gray-500 w-12 text-center">
                      {Math.round(zoom * 100)}%
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}
                    >
                      <ZoomOut className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setZoom(1)}
                    >
                      <RotateCcw className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setShowOverlay(!showOverlay)}
                    >
                      <Filter className="h-3 w-3" />
                    </Button>
                  </div>

                  {/* Page image with word bounding boxes */}
                  <div className="h-full w-full overflow-auto flex items-start justify-center p-6">
                    <div className="relative" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
                      <img
                        src={pages[currentPageIndex].pageImage}
                        alt={`Page ${currentPageIndex + 1}`}
                        className="max-w-none shadow-lg rounded"
                        style={{ maxHeight: 'none' }}
                      />

                      {/* Word bounding boxes overlay */}
                      {showOverlay &&
                        pages[currentPageIndex].words.map((word) => {
                          const isActiveWord = activeWord && word.id === activeWord.id;
                          const borderColor =
                            word.status === 'corrected'
                              ? 'rgba(16, 185, 129, 0.7)'
                              : word.status === 'skipped'
                                ? 'rgba(156, 163, 175, 0.7)'
                                : 'rgba(245, 158, 11, 0.7)';

                          return (
                            <div
                              key={word.id}
                              className={`absolute border-2 cursor-pointer transition-all ${
                                isActiveWord
                                  ? 'bg-emerald-500/20 border-emerald-500 z-20'
                                  : ''
                              }`}
                              style={{
                                left: `${word.x}px`,
                                top: `${word.y}px`,
                                width: `${word.width}px`,
                                height: `${word.height}px`,
                                borderColor,
                              }}
                              onClick={() => {
                                const idx = pages[currentPageIndex].words.findIndex(
                                  (w) => w.id === word.id
                                );
                                if (idx >= 0) setActiveWordIndex(idx);
                              }}
                            />
                          );
                        })}
                    </div>
                  </div>
                </>
              )}

              {pages.length === 0 && allWords.length > 0 && (
                <div className="h-full flex items-center justify-center p-8">
                  <div className="text-center text-gray-500">
                    <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                    <p className="text-sm">بيانات تدريب سابقة</p>
                    <p className="text-xs mt-1">استخدم القائمة على اليمين لتصحيح الكلمات</p>
                  </div>
                </div>
              )}
            </section>

            {/* Right Panel - Word Correction Cards */}
            <aside className="w-80 border-r bg-white flex-shrink-0 flex flex-col">
              <div className="p-3 border-b">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-semibold text-gray-700">تصحيح الكلمات</h3>
                  <span className="text-xs text-gray-400">
                    كلمة {activeWordIndex + 1} من {currentPageWords.length}
                  </span>
                </div>

                {/* Filter */}
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="تصفية الحالة" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all" className="text-xs">
                      الكل
                    </SelectItem>
                    <SelectItem value="pending" className="text-xs">
                      معلق
                    </SelectItem>
                    <SelectItem value="corrected" className="text-xs">
                      مصحح
                    </SelectItem>
                    <SelectItem value="skipped" className="text-xs">
                      متخطى
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Word navigation */}
              <div className="px-3 py-2 border-b flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  disabled={activeWordIndex <= 0}
                  onClick={() => setActiveWordIndex((i) => Math.max(0, i - 1))}
                >
                  <ChevronRight className="h-3 w-3 ml-1" />
                  السابق
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  disabled={activeWordIndex >= currentPageWords.length - 1}
                  onClick={() =>
                    setActiveWordIndex((i) => Math.min(currentPageWords.length - 1, i + 1))
                  }
                >
                  التالي
                  <ChevronLeft className="h-3 w-3 mr-1" />
                </Button>
              </div>

              {/* Word cards list */}
              <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                  {currentPageWords.map((word, idx) => (
                    <WordCard
                      key={word.id}
                      word={word}
                      isActive={idx === activeWordIndex}
                      correctedText={editedTexts[word.id] ?? word.correctedText ?? word.originalText}
                      onCorrectedTextChange={(text) =>
                        setEditedTexts((prev) => ({ ...prev, [word.id]: text }))
                      }
                      onSave={() => {
                        setActiveWordIndex(idx);
                        const tempActive = activeWord;
                        setActiveWordIndex(idx);
                        // Use timeout to allow state update
                        setTimeout(() => handleSaveWord(), 0);
                      }}
                      onSkip={() => {
                        setActiveWordIndex(idx);
                        const tempActive = activeWord;
                        setActiveWordIndex(idx);
                        setTimeout(() => handleSkipWord(), 0);
                      }}
                      onSelect={() => setActiveWordIndex(idx)}
                    />
                  ))}

                  {currentPageWords.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                      <FileText className="h-8 w-8 mx-auto mb-2" />
                      <p className="text-xs">لا توجد كلمات</p>
                    </div>
                  )}
                </div>
              </ScrollArea>

              {/* Batch actions */}
              <div className="p-3 border-t space-y-2">
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    className="flex-1 h-8 bg-emerald-500 hover:bg-emerald-600 text-xs"
                    onClick={handleSaveWord}
                    disabled={!activeWord || activeWord.status === 'corrected'}
                  >
                    <Check className="h-3 w-3 ml-1" />
                    حفظ
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 h-8 text-xs"
                    onClick={handleSkipWord}
                    disabled={!activeWord || activeWord.status === 'skipped'}
                  >
                    <SkipForward className="h-3 w-3 ml-1" />
                    تخطي
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 h-8 text-xs"
                    onClick={handleExportTrainingData}
                  >
                    <Download className="h-3 w-3 ml-1" />
                    تصدير البيانات
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="flex-1 h-8 text-xs text-red-500 hover:text-red-600 hover:bg-red-50"
                    onClick={handleClearData}
                  >
                    <Trash2 className="h-3 w-3 ml-1" />
                    مسح
                  </Button>
                </div>
                <p className="text-[10px] text-gray-400 text-center">
                  Enter = حفظ | Tab = تخطي
                </p>
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
