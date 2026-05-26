'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Settings,
  Save,
  RotateCcw,
  Loader2,
  ScanLine,
  Compass,
  Crop,
  BookOpen,
  Gauge,
  Cpu,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';

interface SettingsData {
  pageThreshold: number;
  grayThreshold: number;
  autoSave: boolean;
  autoDeskew: boolean;
  autoCrop: boolean;
  padding: number;
  minConfidence: number;
}

export default function SettingsPanel() {
  const { settings, setSettings } = useAppStore();
  const [localSettings, setLocalSettings] = useState<SettingsData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      setSettings(data.settings);
      setLocalSettings(data.settings);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  }

  async function saveSettings() {
    if (!localSettings) return;
    setSaving(true);
    setSaved(false);

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(localSettings),
      });
      const data = await res.json();

      if (data.success) {
        setSettings(data.settings);
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (err) {
      console.error('Save settings error:', err);
    } finally {
      setSaving(false);
    }
  }

  function resetSettings() {
    setLocalSettings({
      pageThreshold: 200,
      grayThreshold: 230,
      autoSave: true,
      autoDeskew: true,
      autoCrop: true,
      padding: 10,
      minConfidence: 0.85,
    });
  }

  if (!localSettings) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-emerald-600 animate-pulse-emerald">جارٍ تحميل الإعدادات...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 lg:p-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">الإعدادات</h2>
          <p className="text-slate-500 mt-1">تكوين معلمات المعالجة التلقائية</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={resetSettings} variant="outline" size="sm">
            <RotateCcw className="h-4 w-4 ml-2" />
            إعادة ضبط
          </Button>
          <Button
            onClick={saveSettings}
            disabled={saving}
            className="bg-emerald-600 hover:bg-emerald-700"
            size="sm"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin ml-2" />
            ) : (
              <Save className="h-4 w-4 ml-2" />
            )}
            {saved ? 'تم الحفظ ✓' : 'حفظ'}
          </Button>
        </div>
      </div>

      {/* Thresholds */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base flex items-center gap-2">
            <Settings className="h-5 w-5 text-emerald-600" />
            معلمات الكشف
          </CardTitle>
          <CardDescription>إعدادات عتبات الكشف التلقائي</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Page Threshold */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <Label className="text-sm font-medium text-slate-700">عتبة الصفحة</Label>
              <span className="text-sm font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-md">
                {localSettings.pageThreshold}
              </span>
            </div>
            <Slider
              value={[localSettings.pageThreshold]}
              onValueChange={([v]) => setLocalSettings({ ...localSettings, pageThreshold: v })}
              min={150}
              max={250}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>150 (أكثر حساسية)</span>
              <span>250 (أقل حساسية)</span>
            </div>
          </div>

          {/* Gray Threshold */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <Label className="text-sm font-medium text-slate-700">عتبة الرمادي</Label>
              <span className="text-sm font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-md">
                {localSettings.grayThreshold}
              </span>
            </div>
            <Slider
              value={[localSettings.grayThreshold]}
              onValueChange={([v]) => setLocalSettings({ ...localSettings, grayThreshold: v })}
              min={200}
              max={250}
              step={5}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>200 (كشف أوسع)</span>
              <span>250 (كشف أضيق)</span>
            </div>
          </div>

          {/* Padding */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <Label className="text-sm font-medium text-slate-700">الحشوة (هامش إضافي)</Label>
              <span className="text-sm font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-md">
                {localSettings.padding}px
              </span>
            </div>
            <Slider
              value={[localSettings.padding]}
              onValueChange={([v]) => setLocalSettings({ ...localSettings, padding: v })}
              min={0}
              max={50}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>0 (بدون حشوة)</span>
              <span>50px</span>
            </div>
          </div>

          {/* Minimum Confidence */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <Label className="text-sm font-medium text-slate-700">الحد الأدنى للثقة</Label>
              <span className="text-sm font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-md">
                {Math.round(localSettings.minConfidence * 100)}%
              </span>
            </div>
            <Slider
              value={[localSettings.minConfidence]}
              onValueChange={([v]) => setLocalSettings({ ...localSettings, minConfidence: v })}
              min={0.5}
              max={1.0}
              step={0.05}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Auto Processing */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base flex items-center gap-2">
            <Settings className="h-5 w-5 text-emerald-600" />
            المعالجة التلقائية
          </CardTitle>
          <CardDescription>تفعيل أو تعطيل الميزات التلقائية</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors">
            <div>
              <Label className="text-sm font-medium text-slate-700">الحفظ التلقائي</Label>
              <p className="text-xs text-slate-400 mt-0.5">حفظ الصور تلقائياً بعد المعالجة</p>
            </div>
            <Switch
              checked={localSettings.autoSave}
              onCheckedChange={(v) => setLocalSettings({ ...localSettings, autoSave: v })}
            />
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors">
            <div>
              <Label className="text-sm font-medium text-slate-700">كشف الميلان تلقائياً</Label>
              <p className="text-xs text-slate-400 mt-0.5">كشف وإزالة ميلان الصفحة تلقائياً</p>
            </div>
            <Switch
              checked={localSettings.autoDeskew}
              onCheckedChange={(v) => setLocalSettings({ ...localSettings, autoDeskew: v })}
            />
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors">
            <div>
              <Label className="text-sm font-medium text-slate-700">القص التلقائي</Label>
              <p className="text-xs text-slate-400 mt-0.5">قص الحدود الرمادية تلقائياً</p>
            </div>
            <Switch
              checked={localSettings.autoCrop}
              onCheckedChange={(v) => setLocalSettings({ ...localSettings, autoCrop: v })}
            />
          </div>
        </CardContent>
      </Card>

      {/* Info */}
      <Card className="border-0 shadow-sm bg-slate-50">
        <CardContent className="p-4">
          <p className="text-xs text-slate-500 leading-relaxed">
            <strong>ملاحظة:</strong> تغييرات الإعدادات ستُطبق على الصور التي تُعالج بعد الحفظ.
            الصور التي تمت معالجتها مسبقاً لن تتأثر.
          </p>
        </CardContent>
      </Card>

      {/* Algorithms Info Panel */}
      <Card className="border-0 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base flex items-center gap-2">
            <Cpu className="h-5 w-5 text-emerald-600" />
            الخوارزميات المستخدمة
          </CardTitle>
          <CardDescription>
            شرح الخوارزميات الأساسية في نظام معالجة المستندات الطبية
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {/* find_page_bounds_v2 */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="flex-shrink-0 h-9 w-9 rounded-lg bg-teal-100 flex items-center justify-center mt-0.5">
                <ScanLine className="h-4 w-4 text-teal-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-slate-800 font-mono">
                  find_page_bounds_v2
                </h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  كشف حدود الصفحة عبر المسح من الحواف. تفحص الخوارزمية كل صف من الحواف الأربعة
                  بحثاً عن أول بكسل يتجاوز العتبة، مما يحدد حدود المحتوى الفعلي للصفحة
                  ويستبعد الهوامش الفارغة.
                </p>
              </div>
            </div>

            {/* auto_detect_skew_v2 */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="flex-shrink-0 h-9 w-9 rounded-lg bg-amber-100 flex items-center justify-center mt-0.5">
                <Compass className="h-4 w-4 text-amber-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-slate-800 font-mono">
                  auto_detect_skew_v2
                </h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  كشف الميلان باستخدام تقنيتين: minAreaRect لحساب المستطيل المحيط بأقل مساحة،
                  وتحويل هوف (Hough Transform) لكشف الخطوط المستقيمة. تجمع الخوارزمية بين
                  النتائج للحصول على زاوية ميلان دقيقة.
                </p>
              </div>
            </div>

            {/* smart_auto_crop_v2 */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="flex-shrink-0 h-9 w-9 rounded-lg bg-emerald-100 flex items-center justify-center mt-0.5">
                <Crop className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-slate-800 font-mono">
                  smart_auto_crop_v2
                </h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  القص الذكي بمرحلتين: المرحلة الأولى تكشف الحدود الخشنة، والمرحلة الثانية
                  تضبط الحدود بدقة باستخدام تحليل الإسقاطات الأفقية والعمودية لإزالة
                  الحدود الرمادية والهوامش الزائدة.
                </p>
              </div>
            </div>

            {/* is_double_page */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="flex-shrink-0 h-9 w-9 rounded-lg bg-purple-100 flex items-center justify-center mt-0.5">
                <BookOpen className="h-4 w-4 text-purple-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-slate-800 font-mono">
                  is_double_page
                </h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  تقسيم الصفحات المزدوجة عبر تحليل الفجوة العمودية في المنتصف. تفحص
                  الخوارزمية عمود البكسلات المركزي بحثاً عن منطقة فارغة مستمرة، وتحدد ما
                  إذا كانت الصورة تحتوي على صفحتين تحتاجان للفصل.
                </p>
              </div>
            </div>

            {/* estimate_page_threshold */}
            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="flex-shrink-0 h-9 w-9 rounded-lg bg-rose-100 flex items-center justify-center mt-0.5">
                <Gauge className="h-4 w-4 text-rose-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-slate-800 font-mono">
                  estimate_page_threshold
                </h4>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  حساب العتبة التلقائية للصفحة بناءً على تحليل الرسم البياني للألوان (Histogram).
                  تحدد الخوارزمية أفضل قيمة عتبة للتمييز بين المحتوى والخلفية، مما يحسن
                  دقة عمليات القص وإزالة الحدود الرمادية.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
