'use client';

import React from 'react';
import { Monitor, Download, Terminal, CheckCircle2, AlertCircle, Layers, RotateCcw, Crop, Eye, Sparkles, Hash, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function DesktopAppView() {
  const features = [
    { icon: <Crop className="h-5 w-5" />, title: 'قص ذكي', desc: 'كشف تلقائي لحواف الصفحة وإزالة الحدود الرمادية' },
    { icon: <RotateCcw className="h-5 w-5" />, title: 'تصحيح الميلان', desc: 'كشف وتصحيح ميلان الصور الممسوحة ضوئياً' },
    { icon: <Eye className="h-5 w-5" />, title: 'تحسين الوضوح', desc: 'تحسين حدة النصوص باستخدام Unsharp Mask' },
    { icon: <Layers className="h-5 w-5" />, title: 'إزالة الظلال', desc: 'تطبيع الإضاءة وإزالة الظلال من الصور' },
    { icon: <Sparkles className="h-5 w-5" />, title: 'نظام تعلم تكيفي', desc: 'KNN مع 30 خاصية للتنبؤ بأفضل إعدادات المعالجة' },
    { icon: <Hash className="h-5 w-5" />, title: 'تحليل ذكي للصفحات', desc: 'OCR لاستخراج أرقام الصفحات وكشف المكررات' },
    { icon: <FileText className="h-5 w-5" />, title: 'تصدير CSV وتقارير JSON', desc: 'تصدير نتائج التحليل والبيانات بصيغ متعددة' },
    { icon: <Terminal className="h-5 w-5" />, title: 'اختصارات لوحة المفاتيح', desc: 'Ctrl+Z تراجع، Ctrl+D كشف ميلان، Ctrl+G قص ذكي' },
  ];

  const requirements = [
    { name: 'Python 3.8+', met: true },
    { name: 'PyQt5 >= 5.15', met: true },
    { name: 'OpenCV >= 4.5', met: true },
    { name: 'NumPy >= 1.21', met: true },
    { name: 'pytesseract (اختياري)', met: false },
    { name: 'Tesseract OCR (اختياري)', met: false },
  ];

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="p-6 lg:px-8 border-b bg-white">
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center h-14 w-14 rounded-xl bg-emerald-100 text-emerald-600">
            <Monitor className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">تطبيق سطح المكتب</h1>
            <p className="text-sm text-slate-500 mt-1">
              تطبيق Python سطح المكتب لمعالجة المستندات الطبية — PyQt5 + OpenCV
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 p-6 lg:px-8 space-y-6 bg-slate-50">
        {/* Description */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-5 w-5 text-emerald-600" />
              وصف التطبيق
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600 leading-relaxed space-y-3">
            <p>
              تطبيق تفاعلي لمعالجة الوثائق الطبية الممسوحة ضوئياً، مبني بـ PyQt5 و OpenCV.
              يدعم تصحيح الميلان، القص الذكي، تحسين الوضوح، إزالة الظلال، كشف المكررات، والتحليل الذكي للصفحات.
            </p>
            <p>
              يتضمن نظام تعلم تكيفي (KNN مع 30 خاصية مستخلصة) يتعلم من إعداداتك السابقة ويقترح أفضل معالجة تلقائياً.
            </p>
          </CardContent>
        </Card>

        {/* Features Grid */}
        <div>
          <h2 className="text-lg font-bold text-slate-900 mb-4">الميزات الرئيسية</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {features.map((feature, i) => (
              <Card key={i} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="text-emerald-600">{feature.icon}</div>
                    <h3 className="font-semibold text-sm text-slate-800">{feature.title}</h3>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">{feature.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Requirements */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-500" />
              المتطلبات
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {requirements.map((req, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-b-0">
                  <div className="flex items-center gap-2 text-sm">
                    {req.met ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-amber-400" />
                    )}
                    <span className="text-slate-700">{req.name}</span>
                  </div>
                  <Badge variant={req.met ? 'default' : 'secondary'} className="text-xs">
                    {req.met ? 'مطلوب' : 'اختياري'}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Installation */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5 text-emerald-600" />
              التعليمات
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-700 mb-2">1. تثبيت المكتبات</h4>
              <div className="bg-slate-900 text-emerald-400 rounded-lg p-3 font-mono text-sm overflow-x-auto">
                <code>pip install -r requirements.txt</code>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-700 mb-2">2. تثبيت Tesseract OCR (اختياري)</h4>
              <div className="bg-slate-900 text-slate-300 rounded-lg p-3 font-mono text-sm overflow-x-auto space-y-1">
                <div><code className="text-slate-500"># Ubuntu/Debian:</code></div>
                <div><code>sudo apt install tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng</code></div>
                <div className="mt-2"><code className="text-slate-500"># macOS:</code></div>
                <div><code>brew install tesseract</code></div>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-700 mb-2">3. تشغيل التطبيق</h4>
              <div className="bg-slate-900 text-emerald-400 rounded-lg p-3 font-mono text-sm overflow-x-auto">
                <code>python medical_doc_scanner.py</code>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Download */}
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-bold text-lg text-slate-900">تحميل التطبيق</h3>
                <p className="text-sm text-slate-500 mt-1">تنزيل ملف Python ومتطلباته</p>
              </div>
              <div className="flex gap-3">
                <Button variant="outline" size="lg" className="gap-2">
                  <Download className="h-4 w-4" />
                  medical_doc_scanner.py
                </Button>
                <Button variant="outline" size="lg" className="gap-2">
                  <Download className="h-4 w-4" />
                  requirements.txt
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
