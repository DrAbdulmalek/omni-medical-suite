'use client';

import React, { useState } from 'react';
import {
  Brain, Upload, FileText, Tag, BarChart3, Activity, Loader2,
  CheckCircle, AlertCircle, Copy, Download, ChevronDown, ChevronUp,
  Sparkles, Shield, Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

interface MistralResult {
  ocr?: {
    pages: Array<{
      index: number;
      markdown: string;
    }>;
    total_pages: number;
  };
  classification?: {
    document_type: string;
    confidence: number;
    routing_department?: string;
    urgency?: string;
    summary?: string;
  };
  extraction?: Record<string, unknown>;
  fhir?: {
    resourceType: string;
    type: string;
    total: number;
    entry: Array<{ resource: Record<string, unknown> }>;
  };
  error?: string;
}

const docTypeLabels: Record<string, string> = {
  admission_form: 'نموذج قبول',
  vitals: 'علامات حيوية',
  lab_results: 'نتائج مختبر',
  prescription: 'وصفة طبية',
  radiology_report: 'تقرير أشعة',
  discharge_summary: 'ملخص خروج',
  referral: 'إحالة',
  consent_form: 'موافقة',
  insurance_claim: 'مطالبة تأمين',
  pathology_report: 'تقرير pathology',
  unknown: 'غير معروف',
};

const urgencyColors: Record<string, string> = {
  routine: 'bg-blue-100 text-blue-800',
  urgent: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

export default function MistralIntegrationView() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MistralResult | null>(null);
  const [activeSection, setActiveSection] = useState<string>('ocr');
  const [ocrText, setOcrText] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleOCR = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/mistral/ocr', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ error: 'فشل الاتصال بالخادم' });
    } finally {
      setLoading(false);
    }
  };

  const handleClassify = async () => {
    if (!file && !ocrText) return;
    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      if (file) formData.append('file', file);
      if (ocrText) formData.append('ocr_text', ocrText);

      const res = await fetch('/api/mistral/classify', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      setResult((prev) => ({ ...prev, ...data }));
    } catch {
      setResult({ error: 'فشل التصنيف' });
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('doc_type', result?.classification?.document_type || 'unknown');

      const res = await fetch('/api/mistral/extract', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      setResult((prev) => ({ ...prev, ...data }));
    } catch {
      setResult({ error: 'فشل الاستخراج' });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const downloadJSON = (data: Record<string, unknown>, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-purple-100 dark:bg-purple-900/30">
          <Brain className="h-7 w-7 text-purple-600 dark:text-purple-400" />
        </div>
        <div>
          <h2 className="text-2xl font-bold">تكامل Mistral AI</h2>
          <p className="text-sm text-muted-foreground">
            OCR متقدم + تصنيف + استخراج بيانات + FHIR
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Panel - Upload & Controls */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Upload className="h-4 w-4" />
                رفع المستند
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="border-2 border-dashed rounded-lg p-6 text-center hover:border-primary/50 transition-colors">
                <input
                  type="file"
                  accept="image/*,.pdf"
                  onChange={handleFileChange}
                  className="hidden"
                  id="mistral-file-input"
                />
                <label htmlFor="mistral-file-input" className="cursor-pointer">
                  <FileText className="h-10 w-10 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    {file ? file.name : 'اسحب الملف هنا أو انقر للاختيار'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    PDF, PNG, JPG - حد أقصى 50 ميجا
                  </p>
                </label>
              </div>

              <div className="space-y-2">
                <Label htmlFor="ocr-text">أو الصق نص OCR:</Label>
                <Textarea
                  id="ocr-text"
                  placeholder="الصق النص المستخرج هنا..."
                  value={ocrText}
                  onChange={(e) => setOcrText(e.target.value)}
                  rows={4}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Zap className="h-4 w-4" />
                العمليات
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                onClick={handleOCR}
                disabled={!file || loading}
                className="w-full"
                variant="default"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Sparkles className="h-4 w-4 ml-2" />}
                تشغيل OCR
              </Button>

              <Button
                onClick={handleClassify}
                disabled={(!file && !ocrText) || loading}
                className="w-full"
                variant="secondary"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Tag className="h-4 w-4 ml-2" />}
                تصنيف المستند
              </Button>

              <Button
                onClick={handleExtract}
                disabled={!file || loading}
                className="w-full"
                variant="outline"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <BarChart3 className="h-4 w-4 ml-2" />}
                استخراج + FHIR
              </Button>
            </CardContent>
          </Card>

          {/* Features Info */}
          <Card className="bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20">
            <CardContent className="pt-4 space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4 text-green-600" />
                <span>دعم العربية والإنجليزية</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4 text-green-600" />
                <span>كشف الجداول والصور</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4 text-green-600" />
                <span>تصنيف تلقائي بالذكاء الاصطناعي</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4 text-green-600" />
                <span>تحويل FHIR R4 تلقائي</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Panel - Results */}
        <div className="lg:col-span-2">
          {!result && !loading && (
            <Card className="h-full flex items-center justify-center">
              <CardContent className="text-center py-20">
                <Brain className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-medium text-muted-foreground">
                  ارفع مستندًا لبدء المعالجة
                </h3>
                <p className="text-sm text-muted-foreground/60 mt-2">
                  يدعم Mistral OCR 3 الصور وملفات PDF
                </p>
              </CardContent>
            </Card>
          )}

          {loading && (
            <Card className="h-full flex items-center justify-center">
              <CardContent className="text-center py-20">
                <Loader2 className="h-12 w-12 mx-auto animate-spin text-purple-600 mb-4" />
                <h3 className="text-lg font-medium">جارٍ المعالجة...</h3>
                <p className="text-sm text-muted-foreground mt-2">
                  يتم تحليل المستند باستخدام Mistral AI
                </p>
              </CardContent>
            </Card>
          )}

          {result && result.error && (
            <Card className="border-red-200 dark:border-red-900">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-5 w-5" />
                  <h3 className="font-medium">حدث خطأ</h3>
                </div>
                <p className="text-sm text-muted-foreground mt-2">{result.error}</p>
              </CardContent>
            </Card>
          )}

          {result && !result.error && (
            <Tabs value={activeSection} onValueChange={setActiveSection}>
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="ocr">
                  <FileText className="h-4 w-4 ml-1" />
                  OCR
                </TabsTrigger>
                <TabsTrigger value="classify">
                  <Tag className="h-4 w-4 ml-1" />
                  تصنيف
                </TabsTrigger>
                <TabsTrigger value="extract">
                  <BarChart3 className="h-4 w-4 ml-1" />
                  بيانات
                </TabsTrigger>
                <TabsTrigger value="fhir">
                  <Activity className="h-4 w-4 ml-1" />
                  FHIR
                </TabsTrigger>
              </TabsList>

              {/* OCR Tab */}
              <TabsContent value="ocr">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-base">النص المستخرج</CardTitle>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => result?.ocr && copyToClipboard(result.ocr.pages.map(p => p.markdown).join('\n\n'))}>
                        <Copy className="h-3 w-3 ml-1" /> نسخ
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {result.ocr?.pages ? (
                      <div className="space-y-4">
                        {result.ocr.pages.map((page, i) => (
                          <div key={i}>
                            <div className="flex items-center justify-between mb-2">
                              <Badge variant="outline">صفحة {page.index + 1}</Badge>
                            </div>
                            <div className="bg-muted rounded-lg p-4 max-h-96 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap font-mono">
                              {page.markdown || 'لا يوجد نص'}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-sm">لم يتم تشغيل OCR بعد</p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Classification Tab */}
              <TabsContent value="classify">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">نتيجة التصنيف</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {result.classification ? (
                      <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-muted rounded-lg p-4 text-center">
                            <p className="text-xs text-muted-foreground mb-1">نوع المستند</p>
                            <p className="text-lg font-bold">
                              {docTypeLabels[result.classification.document_type] || result.classification.document_type}
                            </p>
                          </div>
                          <div className="bg-muted rounded-lg p-4 text-center">
                            <p className="text-xs text-muted-foreground mb-1">الثقة</p>
                            <p className="text-lg font-bold">{(result.classification.confidence * 100).toFixed(1)}%</p>
                          </div>
                        </div>

                        <div className="flex gap-2 flex-wrap">
                          {result.classification.urgency && (
                            <Badge className={urgencyColors[result.classification.urgency]}>
                              {result.classification.urgency === 'routine' ? 'عادي' :
                               result.classification.urgency === 'urgent' ? 'عاجل' : 'حرج'}
                            </Badge>
                          )}
                          {result.classification.routing_department && (
                            <Badge variant="outline">
                              القسم: {result.classification.routing_department}
                            </Badge>
                          )}
                        </div>

                        {result.classification.summary && (
                          <div>
                            <p className="text-sm font-medium mb-1">ملخص:</p>
                            <p className="text-sm text-muted-foreground bg-muted rounded-lg p-3">
                              {result.classification.summary}
                            </p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-sm">لم يتم التصنيف بعد</p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Extraction Tab */}
              <TabsContent value="extract">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-base">البيانات المستخرجة</CardTitle>
                    {result.extraction && (
                      <Button size="sm" variant="ghost" onClick={() => downloadJSON(result.extraction!, 'extraction.json')}>
                        <Download className="h-3 w-3 ml-1" /> تحميل JSON
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent>
                    {result.extraction ? (
                      <pre className="bg-muted rounded-lg p-4 max-h-96 overflow-auto text-xs font-mono whitespace-pre-wrap" dir="ltr">
                        {JSON.stringify(result.extraction, null, 2)}
                      </pre>
                    ) : (
                      <p className="text-muted-foreground text-sm">لم يتم الاستخراج بعد</p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* FHIR Tab */}
              <TabsContent value="fhir">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Activity className="h-4 w-4" />
                      FHIR R4 Bundle
                    </CardTitle>
                    {result.fhir && (
                      <Button size="sm" variant="ghost" onClick={() => downloadJSON(result.fhir!, 'fhir_bundle.json')}>
                        <Download className="h-3 w-3 ml-1" /> تحميل FHIR
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent>
                    {result.fhir ? (
                      <div className="space-y-3">
                        <div className="flex gap-4 text-sm">
                          <Badge>ResourceType: {result.fhir.resourceType}</Badge>
                          <Badge variant="outline">الموارد: {result.fhir.total}</Badge>
                        </div>
                        <pre className="bg-muted rounded-lg p-4 max-h-96 overflow-auto text-xs font-mono whitespace-pre-wrap" dir="ltr">
                          {JSON.stringify(result.fhir, null, 2)}
                        </pre>
                      </div>
                    ) : (
                      <p className="text-muted-foreground text-sm">لم يتم إنشاء FHIR بعد</p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
}
