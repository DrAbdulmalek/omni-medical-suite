'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Upload,
  Brain,
  Search,
  FileText,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  CheckCircle2,
  XCircle,
  Database,
} from 'lucide-react';
import { toast } from 'sonner';

interface TrainingRecordData {
  id: string;
  imageName: string;
  confidence: number;
  operations: string[];
  blurBefore: number;
  blurAfter: number;
  improvement: number;
  createdAt: string;
  imageId?: string;
}

interface ModelStatusData {
  trained: boolean;
  lastTrained: string;
  entries: number;
  avgConfidence: number;
}

interface PredictionResult {
  pageThreshold: number;
  grayThreshold: number;
  padding: number;
  confidence: number;
  similarRecords: number;
}

export default function TrainingDataView() {
  const [records, setRecords] = useState<TrainingRecordData[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [search, setSearch] = useState('');
  const [training, setTraining] = useState(false);
  const [modelStatus, setModelStatus] = useState<ModelStatusData | null>(null);
  const [predictingId, setPredictingId] = useState<string | null>(null);
  const [predictions, setPredictions] = useState<Record<string, PredictionResult>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadRecords();
    loadModelStatus();
  }, []);

  async function loadRecords() {
    try {
      const res = await fetch('/api/training');
      const data = await res.json();
      setRecords(data.records || []);
    } catch (err) {
      console.error('Failed to load training records:', err);
    } finally {
      setLoading(false);
    }
  }

  async function loadModelStatus() {
    try {
      const res = await fetch('/api/train');
      const data = await res.json();
      setModelStatus(data);
    } catch {
      // Model not trained
    }
  }

  async function trainModel() {
    setTraining(true);
    try {
      const res = await fetch('/api/train', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        toast.success(data.message || 'تم تدريب النموذج بنجاح', {
          description: `عدد السجلات: ${data.entries} | متوسط المسافة: ${data.avgDistance}`,
          duration: 5000,
        });
        await loadModelStatus();
      } else {
        toast.error('فشل في تدريب النموذج', {
          description: data.error || 'تحقق من وجود بيانات كافية',
          duration: 5000,
        });
      }
    } catch {
      toast.error('حدث خطأ أثناء التدريب');
    } finally {
      setTraining(false);
    }
  }

  async function smartPredict(recordId: string, imageName: string) {
    setPredictingId(recordId);
    try {
      // Find the image ID by looking up images
      const imagesRes = await fetch('/api/images');
      const imagesData = await imagesRes.json();
      const matchingImage = imagesData.images?.find(
        (img: { originalName: string; id: string }) => img.originalName === imageName
      );

      if (!matchingImage) {
        toast.error('لم يتم العثور على الصورة المرتبطة', { duration: 3000 });
        return;
      }

      const res = await fetch(`/api/predict/${matchingImage.id}`);
      const data = await res.json();

      if (data.success && data.prediction) {
        setPredictions((prev) => ({
          ...prev,
          [recordId]: data.prediction,
        }));
        toast.success(`تنبؤ ذكي: عتبة=${data.prediction.pageThreshold}, رمادي=${data.prediction.grayThreshold}`, {
          description: `الثقة: ${Math.round(data.prediction.confidence * 100)}% | سجلات مشابهة: ${data.prediction.similarRecords}`,
          duration: 5000,
        });
      } else if (data.modelNotTrained) {
        toast.error('النموذج غير مدرب بعد. قم بتدريب النموذج أولاً.', { duration: 4000 });
      }
    } catch {
      toast.error('فشل في التنبؤ');
    } finally {
      setPredictingId(null);
    }
  }

  async function importTraining() {
    if (!fileInputRef.current?.files?.length) return;
    setImporting(true);

    try {
      const formData = new FormData();
      formData.append('file', fileInputRef.current.files[0]);

      const res = await fetch('/api/training/import', { method: 'POST', body: formData });
      const data = await res.json();

      if (data.success) {
        await loadRecords();
        toast.success(`تم استيراد ${data.imported} سجل بنجاح`);
      }
    } catch (err) {
      console.error('Import error:', err);
    } finally {
      setImporting(false);
    }
  }

  async function autoImportFromSource() {
    setImporting(true);
    try {
      const res = await fetch('/api/init-data', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await loadRecords();
      }
    } catch (err) {
      console.error('Auto import error:', err);
    } finally {
      setImporting(false);
    }
  }

  const filteredRecords = records.filter((r) =>
    r.imageName.toLowerCase().includes(search.toLowerCase())
  );

  function getImprovementIcon(improvement: number) {
    if (improvement > 50) return <TrendingUp className="h-4 w-4 text-emerald-500" />;
    if (improvement < -50) return <TrendingDown className="h-4 w-4 text-red-500" />;
    return <Minus className="h-4 w-4 text-slate-400" />;
  }

  function getConfidenceBadge(confidence: number) {
    if (confidence >= 0.95) return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">{Math.round(confidence * 100)}%</Badge>;
    if (confidence >= 0.85) return <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100">{Math.round(confidence * 100)}%</Badge>;
    return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">{Math.round(confidence * 100)}%</Badge>;
  }

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">بيانات التدريب</h2>
          <p className="text-slate-500 mt-1">{records.length} سجل تدريب</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={trainModel}
            disabled={training || records.length === 0}
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
          >
            {training ? (
              <Loader2 className="h-4 w-4 animate-spin ml-2" />
            ) : (
              <Brain className="h-4 w-4 ml-2" />
            )}
            {training ? 'جارٍ التدريب...' : 'تدريب النموذج'}
          </Button>
          <Button
            onClick={autoImportFromSource}
            disabled={importing}
            variant="outline"
            className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
          >
            {importing ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Database className="h-4 w-4 ml-2" />}
            استيراد تلقائي
          </Button>
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            variant="outline"
          >
            <Upload className="h-4 w-4 ml-2" />
            استيراد JSONL
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jsonl,.json"
            className="hidden"
            onChange={importTraining}
          />
        </div>
      </div>

      {/* Model Status Card */}
      <Card className="border-0 shadow-sm bg-gradient-to-br from-slate-50 to-slate-100">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                modelStatus?.trained ? 'bg-emerald-100' : 'bg-slate-200'
              }`}>
                <Brain className={`h-5 w-5 ${modelStatus?.trained ? 'text-emerald-600' : 'text-slate-400'}`} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                  حالة النموذج
                  {modelStatus?.trained ? (
                    <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">
                      <CheckCircle2 className="h-3 w-3 ml-1" />
                      مدرب
                    </Badge>
                  ) : (
                    <Badge className="bg-slate-200 text-slate-500 hover:bg-slate-200">
                      <XCircle className="h-3 w-3 ml-1" />
                      غير مدرب
                    </Badge>
                  )}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {modelStatus?.trained
                    ? `آخر تدريب: ${new Date(modelStatus.lastTrained).toLocaleDateString('ar-EG')} | ${modelStatus.entries} سجل`
                    : 'قم بتدريب النموذج لتفعيل التنبؤ الذكي'}
                </p>
              </div>
            </div>
            {modelStatus?.trained && (
              <div className="flex items-center gap-6 text-xs text-slate-500">
                <div className="text-center">
                  <p className="font-bold text-lg text-emerald-600">{modelStatus.entries}</p>
                  <p>سجل تدريب</p>
                </div>
                <div className="text-center">
                  <p className="font-bold text-lg text-teal-600">{Math.round(modelStatus.avgConfidence * 100)}%</p>
                  <p>متوسط الثقة</p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input
          placeholder="البحث في السجلات..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pr-10"
        />
      </div>

      {/* Table */}
      <Card className="border-0 shadow-sm">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="text-emerald-600 animate-pulse-emerald">جارٍ التحميل...</div>
            </div>
          ) : filteredRecords.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <FileText className="h-12 w-12 mb-3 opacity-40" />
              <p className="text-sm">لا توجد سجلات تدريب</p>
              <p className="text-xs mt-1">استورد بيانات JSONL أو استخدم الاستيراد التلقائي</p>
            </div>
          ) : (
            <ScrollArea className="max-h-[calc(100vh-400px)]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-right">الصورة</TableHead>
                    <TableHead className="text-right">الثقة</TableHead>
                    <TableHead className="text-right">التحسين</TableHead>
                    <TableHead className="text-right">قبل</TableHead>
                    <TableHead className="text-right">بعد</TableHead>
                    <TableHead className="text-right">العمليات</TableHead>
                    <TableHead className="text-right">التنبؤ</TableHead>
                    <TableHead className="text-right">التاريخ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRecords.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell className="font-medium text-sm">{record.imageName}</TableCell>
                      <TableCell>{getConfidenceBadge(record.confidence)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {getImprovementIcon(record.improvement)}
                          <span className={`text-xs font-medium ${
                            record.improvement > 50 ? 'text-emerald-600' :
                            record.improvement < -50 ? 'text-red-600' : 'text-slate-500'
                          }`}>
                            {record.improvement > 0 ? '+' : ''}{Math.round(record.improvement)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">{Math.round(record.blurBefore)}</TableCell>
                      <TableCell className="text-xs text-slate-500">{Math.round(record.blurAfter)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {record.operations.slice(0, 3).map((op, i) => (
                            <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0">
                              {op}
                            </Badge>
                          ))}
                          {record.operations.length > 3 && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                              +{record.operations.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {predictions[record.id] ? (
                          <div className="flex flex-col gap-0.5">
                            <div className="flex gap-1">
                              <span className="text-[10px] px-1 py-0 rounded bg-emerald-50 text-emerald-700">
                                ع:{predictions[record.id].pageThreshold}
                              </span>
                              <span className="text-[10px] px-1 py-0 rounded bg-emerald-50 text-emerald-700">
                                ر:{predictions[record.id].grayThreshold}
                              </span>
                              <span className="text-[10px] px-1 py-0 rounded bg-emerald-50 text-emerald-700">
                                ح:{predictions[record.id].padding}
                              </span>
                            </div>
                            <span className="text-[9px] text-slate-400">
                              ثقة {Math.round(predictions[record.id].confidence * 100)}%
                            </span>
                          </div>
                        ) : (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-xs text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                            disabled={predictingId === record.id || !modelStatus?.trained}
                            onClick={() => smartPredict(record.id, record.imageName)}
                          >
                            {predictingId === record.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Sparkles className="h-3 w-3 ml-1" />
                            )}
                            تنبؤ ذكي
                          </Button>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {new Date(record.createdAt).toLocaleDateString('ar-EG')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
