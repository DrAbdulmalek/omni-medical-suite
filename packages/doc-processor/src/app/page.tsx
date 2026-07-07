'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Brain,
  Activity,
  Target,
  Database,
  Play,
  TrendingUp,
  Layers,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Upload,
  Zap,
  RefreshCw,
  FileText,
  ArrowUpDown,
  Clock,
  BarChart3,
  PieChart as PieChartIcon,
  CircleDot,
  FlaskConical,
  Filter,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Slider } from '@/components/ui/slider';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, Area, AreaChart,
} from 'recharts';
import { toast } from 'sonner';

// ────────────────────────── Types ──────────────────────────

interface OcrModel {
  id: string;
  name: string;
  version: string;
  engine: string;
  language: string;
  status: string;
  isProduction: boolean;
  cer: number;
  wer: number;
  accuracy: number;
  speed: number;
  confidence: number;
}

interface EvaluationComparison {
  modelId: string;
  modelName: string;
  cer: number;
  wer: number;
  accuracy: number;
  avgSpeed: number;
  avgConfidence: number;
  isProduction: boolean;
  arCer: number;
  arWer: number;
  arAccuracy: number;
  enCer: number;
  enWer: number;
  enAccuracy: number;
}

interface CommonError {
  type: string;
  ar: string;
  count: number;
  severity: string;
}

interface Deployment {
  id: string;
  modelId: string;
  strategy: string;
  trafficPercent: number;
  status: string;
  startedAt: string;
  model?: OcrModel;
}

interface DataCollectionStats {
  totalCollected: number;
  realCount: number;
  syntheticCount: number;
  academicCount: number;
  highQuality: number;
  mediumQuality: number;
  lowQuality: number;
  targetSize: number;
  phase: string;
  progress: number;
}

// ────────────────────────── Mock Data ──────────────────────────

const trainingAccuracyData = [
  { epoch: 1, accuracy: 0.65, loss: 1.8 },
  { epoch: 2, accuracy: 0.71, loss: 1.4 },
  { epoch: 3, accuracy: 0.76, loss: 1.1 },
  { epoch: 4, accuracy: 0.80, loss: 0.9 },
  { epoch: 5, accuracy: 0.83, loss: 0.72 },
  { epoch: 6, accuracy: 0.86, loss: 0.58 },
  { epoch: 7, accuracy: 0.89, loss: 0.45 },
  { epoch: 8, accuracy: 0.91, loss: 0.35 },
  { epoch: 9, accuracy: 0.93, loss: 0.28 },
  { epoch: 10, accuracy: 0.95, loss: 0.22 },
];

const sourceDistributionData = [
  { source: 'مستشفيات', count: 4200 },
  { source: 'مختبرات', count: 2800 },
  { source: 'أكاديمي', count: 1900 },
  { source: 'توليد تركيبي', count: 3500 },
  { source: 'مصادر عامة', count: 1600 },
];

const QUALITY_COLORS = ['#22c55e', '#eab308', '#ef4444'];
const CHART_COLORS = ['#8B5CF6', '#6366f1', '#06b6d4', '#f59e0b', '#ef4444'];
const SEVERITY_MAP: Record<string, { label: string; color: string }> = {
  high: { label: 'مرتفع', color: 'text-red-500 bg-red-50 dark:bg-red-950/30' },
  medium: { label: 'متوسط', color: 'text-yellow-600 bg-yellow-50 dark:bg-yellow-950/30' },
  low: { label: 'منخفض', color: 'text-green-600 bg-green-50 dark:bg-green-950/30' },
};

const PHASE_MAP: Record<string, { label: string; color: string }> = {
  idle: { label: 'خامل', color: 'text-muted-foreground' },
  collecting: { label: 'جمع البيانات', color: 'text-blue-500' },
  synthetic: { label: 'توليد تركيبي', color: 'text-violet-500' },
  validation: { label: 'التحقق', color: 'text-amber-500' },
  complete: { label: 'مكتمل', color: 'text-green-500' },
};

const PIPELINE_PHASES = ['idle', 'collecting', 'synthetic', 'validation', 'complete'];
const PIPELINE_LABELS: Record<string, string> = {
  idle: 'خامل',
  collecting: 'جمع البيانات',
  synthetic: 'توليد تركيبي',
  validation: 'التحقق من الجودة',
  complete: 'مكتمل',
};

// ────────────────────────── Helpers ──────────────────────────

function getCerColor(cer: number) {
  if (cer < 5) return 'text-green-600 dark:text-green-400';
  if (cer < 10) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function getCerBadge(cer: number) {
  if (cer < 5) return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300';
  if (cer < 10) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300';
  return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
}

function formatPercent(val: number) {
  return `${(val * 100).toFixed(1)}%`;
}

function formatNum(n: number) {
  return new Intl.NumberFormat('ar-EG').format(n);
}

function getStatusDot(status: string) {
  const map: Record<string, string> = {
    active: 'bg-green-500',
    production: 'bg-green-500',
    archived: 'bg-gray-400',
    training: 'bg-blue-500 animate-pulse',
    idle: 'bg-gray-400',
    deploying: 'bg-amber-500 animate-pulse',
  };
  return map[status] || 'bg-gray-400';
}

function getStrategyLabel(s: string) {
  const map: Record<string, string> = {
    direct: 'نشر مباشر',
    canary: 'Canary',
    blueGreen: 'Blue-Green',
  };
  return map[s] || s;
}

// ────────────────────────── Sub-components ──────────────────────────

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  accent = 'violet',
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  description?: string;
  accent?: string;
}) {
  const accentMap: Record<string, string> = {
    violet: 'from-violet-500/10 to-violet-600/5 border-violet-200 dark:border-violet-800',
    blue: 'from-blue-500/10 to-blue-600/5 border-blue-200 dark:border-blue-800',
    emerald: 'from-emerald-500/10 to-emerald-600/5 border-emerald-200 dark:border-emerald-800',
    amber: 'from-amber-500/10 to-amber-600/5 border-amber-200 dark:border-amber-800',
  };
  const iconBg: Record<string, string> = {
    violet: 'bg-violet-100 text-violet-600 dark:bg-violet-900/50 dark:text-violet-300',
    blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-300',
    emerald: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-300',
    amber: 'bg-amber-100 text-amber-600 dark:bg-amber-900/50 dark:text-amber-300',
  };

  return (
    <Card className={cn('bg-gradient-to-br border', accentMap[accent], 'rounded-xl shadow-sm hover:shadow-md transition-shadow')}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <div className={cn('p-2.5 rounded-lg', iconBg[accent])}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <p className="text-3xl font-bold tracking-tight">{value}</p>
        {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
      </CardContent>
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="rounded-xl">
            <CardContent className="p-6">
              <Skeleton className="h-4 w-24 mb-3" />
              <Skeleton className="h-9 w-20" />
              <Skeleton className="h-3 w-32 mt-2" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <Card key={i} className="rounded-xl">
            <CardHeader>
              <Skeleton className="h-5 w-36" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-[300px] w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────── Main Component ──────────────────────────

export default function OcrDashboard() {
  // Data state
  const [models, setModels] = useState<OcrModel[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [collectionStats, setCollectionStats] = useState<DataCollectionStats | null>(null);

  // Evaluation state
  const [selectedModelIds, setSelectedModelIds] = useState<Set<string>>(new Set());
  const [evalResults, setEvalResults] = useState<EvaluationComparison[]>([]);
  const [commonErrors, setCommonErrors] = useState<CommonError[]>([]);
  const [isEvaluating, setIsEvaluating] = useState(false);

  // Deployment state
  const [canaryTraffic, setCanaryTraffic] = useState<number>(10);
  const [isDeploying, setIsDeploying] = useState<string | null>(null);

  // Collection state
  const [isCollecting, setIsCollecting] = useState(false);

  // Loading state
  const [isLoading, setIsLoading] = useState(true);

  // ── Data Fetching ──

  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch('/api/ocr/models');
      if (res.ok) {
        const data = await res.json();
        setModels(data);
        // Auto-select models for evaluation
        setSelectedModelIds(new Set(data.slice(0, 3).map((m: OcrModel) => m.id)));
      }
    } catch {
      // silent fail
    }
  }, []);

  const fetchDeployments = useCallback(async () => {
    try {
      const res = await fetch('/api/ocr/deploy');
      if (res.ok) {
        const data = await res.json();
        setDeployments(data);
      }
    } catch {
      // silent fail
    }
  }, []);

  const fetchCollectionStats = useCallback(async () => {
    try {
      const res = await fetch('/api/data-collection');
      if (res.ok) {
        const data = await res.json();
        setCollectionStats(data);
      }
    } catch {
      // silent fail
    }
  }, []);

  useEffect(() => {
    async function loadAll() {
      setIsLoading(true);
      await Promise.all([fetchModels(), fetchDeployments(), fetchCollectionStats()]);
      setIsLoading(false);
    }
    loadAll();
  }, [fetchModels, fetchDeployments, fetchCollectionStats]);

  // ── Handlers ──

  const toggleModelSelection = (id: string) => {
    setSelectedModelIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleEvaluate = async () => {
    if (selectedModelIds.size === 0) {
      toast.error('يرجى اختيار نموذج واحد على الأقل');
      return;
    }
    setIsEvaluating(true);
    try {
      const res = await fetch('/api/ocr/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelIds: Array.from(selectedModelIds) }),
      });
      if (res.ok) {
        const data = await res.json();
        setEvalResults(data.comparisons);
        setCommonErrors(data.commonErrors);
        toast.success('تم التقييم بنجاح');
      } else {
        toast.error('فشل في التقييم');
      }
    } catch {
      toast.error('خطأ في الاتصال');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleDeploy = async (strategy: string, config?: Record<string, unknown>) => {
    const prodModel = models.find((m) => m.isProduction);
    if (!prodModel) {
      toast.error('لا يوجد نموذج إنتاج متاح');
      return;
    }
    setIsDeploying(strategy);
    try {
      const res = await fetch('/api/ocr/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelId: prodModel.id, strategy, config }),
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(data.message || 'تم النشر بنجاح');
        fetchDeployments();
      } else {
        toast.error('فشل في النشر');
      }
    } catch {
      toast.error('خطأ في الاتصال');
    } finally {
      setIsDeploying(null);
    }
  };

  const handleStartCollection = async () => {
    setIsCollecting(true);
    try {
      const res = await fetch('/api/data-collection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start' }),
      });
      if (res.ok) {
        toast.success('بدأ التجميع');
        fetchCollectionStats();
      }
    } catch {
      toast.error('خطأ في بدء التجميع');
    } finally {
      setIsCollecting(false);
    }
  };

  // ── Computed values ──

  const activeModel = models.find((m) => m.isProduction);
  const avgCer = models.length > 0 ? models.reduce((s, m) => s + m.cer, 0) / models.length : 0;
  const modelComparisonData = models.slice(0, 6).map((m) => ({
    name: `${m.name} v${m.version.slice(0, 4)}`,
    cer: Number((m.cer * 100).toFixed(1)),
    wer: Number((m.wer * 100).toFixed(1)),
  }));

  const qualityPieData = collectionStats
    ? [
        { name: 'عالية الجودة', value: collectionStats.highQuality },
        { name: 'متوسطة الجودة', value: collectionStats.mediumQuality },
        { name: 'منخفضة الجودة', value: collectionStats.lowQuality },
      ].filter((d) => d.value > 0)
    : [];

  const collectionProgress = collectionStats
    ? Math.min(100, (collectionStats.totalCollected / collectionStats.targetSize) * 100)
    : 0;

  // ──────────────────────── Render ────────────────────────

  if (isLoading) {
    return (
      <div dir="rtl" className="min-h-screen bg-background p-4 md:p-8">
        <div className="mb-8">
          <Skeleton className="h-8 w-64 mb-2" />
          <Skeleton className="h-4 w-96" />
        </div>
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <div dir="rtl" className="min-h-screen bg-background p-4 md:p-8">
      {/* ── Header ── */}
      <header className="mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-violet-100 dark:bg-violet-900/40 rounded-xl">
              <Brain className="h-7 w-7 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-l from-violet-600 to-indigo-600 dark:from-violet-400 dark:to-indigo-400 bg-clip-text text-transparent">
                منصة إدارة OCR الطبي
              </h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                إدارة النماذج والتقييم والنشر وجمع البيانات
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="gap-1.5 px-3 py-1">
              <span className={cn('w-2 h-2 rounded-full', models.length > 0 ? 'bg-green-500' : 'bg-gray-400')} />
              {models.length} نموذج
            </Badge>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => { fetchModels(); fetchDeployments(); fetchCollectionStats(); }}>
              <RefreshCw className="h-3.5 w-3.5" />
              تحديث
            </Button>
          </div>
        </div>
      </header>

      {/* ── Tabs ── */}
      <Tabs defaultValue="dashboard" className="space-y-6">
        <TabsList className="bg-muted/60 p-1 h-auto flex-wrap gap-1 rounded-xl">
          <TabsTrigger value="dashboard" className="rounded-lg gap-1.5 data-[state=active]:bg-violet-600 data-[state=active]:text-white">
            <Activity className="h-4 w-4" />
            <span className="hidden sm:inline">لوحة التحكم</span>
          </TabsTrigger>
          <TabsTrigger value="evaluation" className="rounded-lg gap-1.5 data-[state=active]:bg-violet-600 data-[state=active]:text-white">
            <FlaskConical className="h-4 w-4" />
            <span className="hidden sm:inline">التقييم</span>
          </TabsTrigger>
          <TabsTrigger value="deployment" className="rounded-lg gap-1.5 data-[state=active]:bg-violet-600 data-[state=active]:text-white">
            <Zap className="h-4 w-4" />
            <span className="hidden sm:inline">النشر</span>
          </TabsTrigger>
          <TabsTrigger value="data-collection" className="rounded-lg gap-1.5 data-[state=active]:bg-violet-600 data-[state=active]:text-white">
            <Database className="h-4 w-4" />
            <span className="hidden sm:inline">جمع البيانات</span>
          </TabsTrigger>
        </TabsList>

        {/* ═══════════════════ Tab 1: Dashboard ═══════════════════ */}
        <TabsContent value="dashboard" className="space-y-6">
          {/* Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="إجمالي النماذج"
              value={String(models.length)}
              icon={Brain}
              description={`${models.filter((m) => m.status === 'training').length} قيد التدريب`}
              accent="violet"
            />
            <StatCard
              title="النموذج النشط"
              value={activeModel ? `${activeModel.name} v${activeModel.version}` : '—'}
              icon={Activity}
              description={activeModel ? `الدقة: ${formatPercent(activeModel.accuracy)}` : 'لا يوجد نموذج نشط'}
              accent="emerald"
            />
            <StatCard
              title="متوسط CER"
              value={formatPercent(avgCer)}
              icon={Target}
              description={avgCer < 0.05 ? 'أداء ممتاز' : avgCer < 0.1 ? 'أداء جيد' : 'يحتاج تحسين'}
              accent="blue"
            />
            <StatCard
              title="مجموع البيانات"
              value={collectionStats ? formatNum(collectionStats.totalCollected) : '0'}
              icon={Database}
              description={collectionStats ? `الهدف: ${formatNum(collectionStats.targetSize)}` : ''}
              accent="amber"
            />
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Training Accuracy LineChart */}
            <Card className="rounded-xl shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-violet-500" />
                  دقة التدريب عبر الحقب
                </CardTitle>
                <CardDescription>تطور دقة النموذج خلال 10 حقب تدريبية</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={trainingAccuracyData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                    <defs>
                      <linearGradient id="accuracyGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
                    <XAxis dataKey="epoch" label={{ value: 'الحقبة', position: 'insideBottom', offset: -2, className: 'fill-muted-foreground text-xs' }} />
                    <YAxis domain={[0.5, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
                    <Tooltip
                      formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, 'الدقة']}
                      labelFormatter={(label: number) => `الحقبة ${label}`}
                      contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }}
                    />
                    <Area type="monotone" dataKey="accuracy" stroke="#8B5CF6" strokeWidth={2.5} fill="url(#accuracyGrad)" dot={{ fill: '#8B5CF6', r: 4 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Model Comparison BarChart */}
            <Card className="rounded-xl shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-violet-500" />
                  مقارنة النماذج — CER / WER
                </CardTitle>
                <CardDescription>معدل خطأ الأحرف (CER) ومعدل خطأ الكلمات (WER)</CardDescription>
              </CardHeader>
              <CardContent>
                {modelComparisonData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={modelComparisonData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
                      <XAxis dataKey="name" className="text-xs" />
                      <YAxis unit="%" />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }}
                      />
                      <Legend />
                      <Bar dataKey="cer" name="CER %" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="wer" name="WER %" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                    لا توجد بيانات نماذج
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Models Overview */}
          <Card className="rounded-xl shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <FileText className="h-5 w-5 text-violet-500" />
                نظرة عامة على النماذج
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>الحالة</TableHead>
                    <TableHead>النموذج</TableHead>
                    <TableHead className="hidden md:table-cell">المحرك</TableHead>
                    <TableHead>CER</TableHead>
                    <TableHead>WER</TableHead>
                    <TableHead>الدقة</TableHead>
                    <TableHead className="hidden lg:table-cell">الثقة</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                        لا توجد نماذج مسجلة
                      </TableCell>
                    </TableRow>
                  ) : (
                    models.map((model) => (
                      <TableRow key={model.id} className="hover:bg-muted/50 transition-colors">
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className={cn('w-2 h-2 rounded-full', getStatusDot(model.status))} />
                            {model.isProduction && (
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
                                إنتاج
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">{model.name} <span className="text-muted-foreground text-xs">v{model.version}</span></TableCell>
                        <TableCell className="hidden md:table-cell">
                          <Badge variant="outline" className="font-mono text-xs">{model.engine}</Badge>
                        </TableCell>
                        <TableCell className={getCerColor(model.cer)}>{formatPercent(model.cer)}</TableCell>
                        <TableCell>{formatPercent(model.wer)}</TableCell>
                        <TableCell>{formatPercent(model.accuracy)}</TableCell>
                        <TableCell className="hidden lg:table-cell">{formatPercent(model.confidence)}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ═══════════════════ Tab 2: Evaluation ═══════════════════ */}
        <TabsContent value="evaluation" className="space-y-6">
          {/* Model Selection Grid */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold">اختيار النماذج للتقييم</h3>
                <p className="text-sm text-muted-foreground">اختر النماذج التي تريد تقييمها ومقارنتها</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline">{selectedModelIds.size} محدد</Badge>
                <Button
                  onClick={handleEvaluate}
                  disabled={isEvaluating || selectedModelIds.size === 0}
                  className="bg-violet-600 hover:bg-violet-700 text-white gap-2"
                >
                  {isEvaluating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  تشغيل التقييم
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {models.length === 0 ? (
                <Card className="rounded-xl col-span-full">
                  <CardContent className="flex items-center justify-center py-12 text-muted-foreground">
                    لا توجد نماذج متاحة للتقييم
                  </CardContent>
                </Card>
              ) : (
                models.map((model) => (
                  <Card
                    key={model.id}
                    className={cn(
                      'rounded-xl cursor-pointer transition-all hover:shadow-md border-2',
                      selectedModelIds.has(model.id)
                        ? 'border-violet-500 bg-violet-50/50 dark:bg-violet-950/20'
                        : 'border-transparent hover:border-muted'
                    )}
                    onClick={() => toggleModelSelection(model.id)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={selectedModelIds.has(model.id)}
                          onCheckedChange={() => toggleModelSelection(model.id)}
                          className="mt-1"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-sm truncate">{model.name}</span>
                            <span className="text-xs text-muted-foreground">v{model.version}</span>
                            {model.isProduction && (
                              <Badge className="text-[10px] px-1.5 py-0 bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">
                                إنتاج
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1 mb-2">
                            <span className={cn('w-1.5 h-1.5 rounded-full', getStatusDot(model.status))} />
                            <span className="text-xs text-muted-foreground">{model.engine}</span>
                          </div>
                          <div className="flex items-center gap-3 text-xs">
                            <span className={getCerColor(model.cer)}>CER: {formatPercent(model.cer)}</span>
                            <span className="text-muted-foreground">WER: {formatPercent(model.wer)}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </div>

          {/* Evaluation Results */}
          {evalResults.length > 0 && (
            <>
              <Separator />
              <div className="space-y-6">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  نتائج التقييم
                </h3>

                {/* Results Table */}
                <Card className="rounded-xl shadow-sm">
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>النموذج</TableHead>
                          <TableHead>CER</TableHead>
                          <TableHead>WER</TableHead>
                          <TableHead>الدقة</TableHead>
                          <TableHead className="hidden md:table-cell">السرعة</TableHead>
                          <TableHead className="hidden md:table-cell">الثقة</TableHead>
                          <TableHead>الحالة</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {evalResults.map((r) => (
                          <TableRow key={r.modelId} className="hover:bg-muted/50 transition-colors">
                            <TableCell className="font-medium">
                              {r.modelName}
                              {r.isProduction && (
                                <Badge variant="secondary" className="mr-2 text-[10px] px-1.5 py-0 bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300">
                                  إنتاج
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge className={cn('font-mono', getCerBadge(r.cer))}>
                                {(r.cer * 100).toFixed(1)}%
                              </Badge>
                            </TableCell>
                            <TableCell className={getCerColor(r.wer)}>{formatPercent(r.wer)}</TableCell>
                            <TableCell>{formatPercent(r.accuracy)}</TableCell>
                            <TableCell className="hidden md:table-cell">{r.avgSpeed.toFixed(0)} ms</TableCell>
                            <TableCell className="hidden md:table-cell">{formatPercent(r.avgConfidence)}</TableCell>
                            <TableCell>
                              {r.isProduction ? (
                                <Badge variant="outline" className="gap-1 border-green-300 text-green-600 dark:border-green-700 dark:text-green-400">
                                  <CheckCircle2 className="h-3 w-3" /> نشط
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="gap-1">
                                  <XCircle className="h-3 w-3" /> غير نشط
                                </Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>

                {/* Language Comparison Charts */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Arabic Performance */}
                  <Card className="rounded-xl shadow-sm">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base font-semibold flex items-center gap-2">
                        <span className="text-lg">🇸🇦</span>
                        أداء اللغة العربية
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={evalResults.map((r) => ({
                          name: r.modelName.split(' ')[0],
                          cer: Number((r.arCer * 100).toFixed(1)),
                          wer: Number((r.arWer * 100).toFixed(1)),
                          accuracy: Number((r.arAccuracy * 100).toFixed(1)),
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
                          <XAxis dataKey="name" className="text-xs" />
                          <YAxis unit="%" />
                          <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }} />
                          <Legend />
                          <Bar dataKey="cer" name="CER %" fill="#ef4444" radius={[3, 3, 0, 0]} />
                          <Bar dataKey="wer" name="WER %" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                          <Bar dataKey="accuracy" name="الدقة %" fill="#22c55e" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  {/* English Performance */}
                  <Card className="rounded-xl shadow-sm">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base font-semibold flex items-center gap-2">
                        <span className="text-lg">🇬🇧</span>
                        أداء اللغة الإنجليزية
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={evalResults.map((r) => ({
                          name: r.modelName.split(' ')[0],
                          cer: Number((r.enCer * 100).toFixed(1)),
                          wer: Number((r.enWer * 100).toFixed(1)),
                          accuracy: Number((r.enAccuracy * 100).toFixed(1)),
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
                          <XAxis dataKey="name" className="text-xs" />
                          <YAxis unit="%" />
                          <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }} />
                          <Legend />
                          <Bar dataKey="cer" name="CER %" fill="#ef4444" radius={[3, 3, 0, 0]} />
                          <Bar dataKey="wer" name="WER %" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                          <Bar dataKey="accuracy" name="الدقة %" fill="#22c55e" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                {/* Common Errors */}
                {commonErrors.length > 0 && (
                  <Card className="rounded-xl shadow-sm">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg font-semibold flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-amber-500" />
                        الأخطاء الشائعة
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>نوع الخطأ</TableHead>
                            <TableHead>الوصف</TableHead>
                            <TableHead>العدد</TableHead>
                            <TableHead>الشدة</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {commonErrors.map((err, idx) => {
                            const sev = SEVERITY_MAP[err.severity] || SEVERITY_MAP.low;
                            return (
                              <TableRow key={idx} className="hover:bg-muted/50 transition-colors">
                                <TableCell className="font-mono text-sm">{err.type}</TableCell>
                                <TableCell>{err.ar}</TableCell>
                                <TableCell className="font-semibold">{err.count}</TableCell>
                                <TableCell>
                                  <Badge className={cn('text-xs', sev.color)}>{sev.label}</Badge>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                )}
              </div>
            </>
          )}

          {/* Empty state for results */}
          {evalResults.length === 0 && !isEvaluating && (
            <Card className="rounded-xl border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <FlaskConical className="h-12 w-12 mb-4 opacity-30" />
                <p className="text-base font-medium">اختر النماذج وشغّل التقييم</p>
                <p className="text-sm mt-1">ستظهر النتائج والمقارنات هنا</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ═══════════════════ Tab 3: Deployment ═══════════════════ */}
        <TabsContent value="deployment" className="space-y-6">
          {/* Strategy Cards */}
          <div>
            <h3 className="text-lg font-semibold mb-4">استراتيجيات النشر</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Direct Deployment */}
              <Card className="rounded-xl shadow-sm hover:shadow-md transition-all border-2 border-transparent hover:border-violet-200 dark:hover:border-violet-800">
                <CardContent className="p-6 flex flex-col items-center text-center gap-4">
                  <div className="p-3 bg-violet-100 dark:bg-violet-900/40 rounded-xl">
                    <Play className="h-7 w-7 text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-base mb-1">نشر مباشر</h4>
                    <p className="text-sm text-muted-foreground">
                      استبدال النموذج الحالي مباشرة بالنسخة الجديدة
                    </p>
                  </div>
                  <Button
                    onClick={() => handleDeploy('direct')}
                    disabled={!activeModel || isDeploying === 'direct'}
                    className="w-full bg-violet-600 hover:bg-violet-700 text-white gap-2"
                  >
                    {isDeploying === 'direct' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4" />
                    )}
                    نشر
                  </Button>
                  {!activeModel && (
                    <p className="text-xs text-muted-foreground">لا يوجد نموذج إنتاج</p>
                  )}
                </CardContent>
              </Card>

              {/* Canary Deployment */}
              <Card className="rounded-xl shadow-sm hover:shadow-md transition-all border-2 border-transparent hover:border-blue-200 dark:hover:border-blue-800">
                <CardContent className="p-6 flex flex-col items-center text-center gap-4">
                  <div className="p-3 bg-blue-100 dark:bg-blue-900/40 rounded-xl">
                    <TrendingUp className="h-7 w-7 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-base mb-1">Canary — نشر تدريجي</h4>
                    <p className="text-sm text-muted-foreground">
                      توجيه نسبة محددة من حركة المرور للنموذج الجديد
                    </p>
                  </div>
                  <div className="w-full space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">نسبة الحركة</span>
                      <Badge variant="outline" className="font-mono">{canaryTraffic}%</Badge>
                    </div>
                    <Slider
                      value={[canaryTraffic]}
                      onValueChange={(v) => setCanaryTraffic(v[0])}
                      min={1}
                      max={50}
                      step={1}
                      className="w-full"
                    />
                  </div>
                  <Button
                    onClick={() => handleDeploy('canary', { trafficPercent: canaryTraffic })}
                    disabled={!activeModel || isDeploying === 'canary'}
                    variant="outline"
                    className="w-full gap-2 border-blue-300 text-blue-600 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/30"
                  >
                    {isDeploying === 'canary' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <TrendingUp className="h-4 w-4" />
                    )}
                    بدء Canary
                  </Button>
                </CardContent>
              </Card>

              {/* Blue-Green Deployment */}
              <Card className="rounded-xl shadow-sm hover:shadow-md transition-all border-2 border-transparent hover:border-emerald-200 dark:hover:border-emerald-800">
                <CardContent className="p-6 flex flex-col items-center text-center gap-4">
                  <div className="p-3 bg-emerald-100 dark:bg-emerald-900/40 rounded-xl">
                    <Layers className="h-7 w-7 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-base mb-1">Blue-Green</h4>
                    <p className="text-sm text-muted-foreground">
                      تشغيل بيئتين بالتوازي والتبديل الفوري عند التأكد من الجاهزية
                    </p>
                  </div>
                  <Button
                    onClick={() => handleDeploy('blueGreen')}
                    disabled={!activeModel || isDeploying === 'blueGreen'}
                    variant="outline"
                    className="w-full gap-2 border-emerald-300 text-emerald-600 hover:bg-emerald-50 dark:border-emerald-700 dark:text-emerald-400 dark:hover:bg-emerald-950/30"
                  >
                    {isDeploying === 'blueGreen' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Layers className="h-4 w-4" />
                    )}
                    نشر
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>

          <Separator />

          {/* Active Deployments */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <CircleDot className="h-5 w-5 text-violet-500" />
                عمليات النشر النشطة
              </h3>
              <Button variant="ghost" size="sm" className="gap-1.5" onClick={fetchDeployments}>
                <RefreshCw className="h-3.5 w-3.5" />
                تحديث
              </Button>
            </div>

            {deployments.length === 0 ? (
              <Card className="rounded-xl border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Layers className="h-10 w-10 mb-3 opacity-30" />
                  <p className="text-base font-medium">لا توجد عمليات نشر نشطة</p>
                  <p className="text-sm mt-1">اختر استراتيجية نشر من الأعلى للبدء</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {deployments.map((dep) => (
                  <Card key={dep.id} className="rounded-xl shadow-sm">
                    <CardContent className="p-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            'p-2 rounded-lg',
                            dep.strategy === 'direct' ? 'bg-violet-100 dark:bg-violet-900/40' :
                            dep.strategy === 'canary' ? 'bg-blue-100 dark:bg-blue-900/40' :
                            'bg-emerald-100 dark:bg-emerald-900/40'
                          )}>
                            {dep.strategy === 'direct' && <Play className="h-4 w-4 text-violet-600 dark:text-violet-400" />}
                            {dep.strategy === 'canary' && <TrendingUp className="h-4 w-4 text-blue-600 dark:text-blue-400" />}
                            {dep.strategy === 'blueGreen' && <Layers className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />}
                          </div>
                          <div>
                            <p className="font-semibold text-sm">
                              {getStrategyLabel(dep.strategy)}
                              <span className="text-muted-foreground font-normal mr-2">
                                {dep.model?.name ? `${dep.model.name} v${dep.model.version}` : dep.modelId.slice(0, 8)}
                              </span>
                            </p>
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(dep.startedAt).toLocaleDateString('ar-EG', { dateStyle: 'medium', timeStyle: 'short' })}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          {dep.strategy === 'canary' && (
                            <Badge variant="outline" className="font-mono">
                              {dep.trafficPercent}% حركة
                            </Badge>
                          )}
                          <Badge className="gap-1 bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                            نشط
                          </Badge>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        {/* ═══════════════════ Tab 4: Data Collection ═══════════════════ */}
        <TabsContent value="data-collection" className="space-y-6">
          {/* Progress Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Collection Progress Card */}
            <Card className="rounded-xl shadow-sm lg:col-span-1">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Upload className="h-5 w-5 text-violet-500" />
                  تقدم التجميع
                </CardTitle>
                <CardDescription>
                  {collectionStats ? `${formatNum(collectionStats.totalCollected)} من ${formatNum(collectionStats.targetSize)}` : '—'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Circular Progress Visualization */}
                <div className="flex items-center justify-center">
                  <div className="relative">
                    <svg width="160" height="160" className="-rotate-90">
                      <circle cx="80" cy="80" r="70" fill="none" stroke="currentColor" className="text-muted/30" strokeWidth="10" />
                      <circle
                        cx="80" cy="80" r="70" fill="none"
                        stroke="#8B5CF6"
                        strokeWidth="10"
                        strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 70}
                        strokeDashoffset={2 * Math.PI * 70 * (1 - collectionProgress / 100)}
                        className="transition-all duration-700"
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold">{collectionProgress.toFixed(1)}%</span>
                      <span className="text-xs text-muted-foreground">مكتمل</span>
                    </div>
                  </div>
                </div>

                {/* Phase indicator */}
                {collectionStats && (
                  <div className="flex items-center justify-center gap-2">
                    <Badge
                      variant="outline"
                      className={cn('gap-1.5 px-3 py-1', PHASE_MAP[collectionStats.phase]?.color)}
                    >
                      <span className={cn(
                        'w-2 h-2 rounded-full',
                        collectionStats.phase === 'idle' ? 'bg-gray-400' :
                        collectionStats.phase === 'complete' ? 'bg-green-500' : 'animate-pulse bg-violet-500'
                      )} />
                      {PHASE_MAP[collectionStats.phase]?.label || collectionStats.phase}
                    </Badge>
                  </div>
                )}

                <Button
                  onClick={handleStartCollection}
                  disabled={isCollecting || collectionStats?.phase === 'collecting'}
                  className="w-full bg-violet-600 hover:bg-violet-700 text-white gap-2"
                >
                  {isCollecting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  بدء التجميع
                </Button>
              </CardContent>
            </Card>

            {/* Stats Grid */}
            <div className="lg:col-span-2">
              <div className="grid grid-cols-2 gap-4 mb-6">
                <StatCard
                  title="إجمالي العينات"
                  value={collectionStats ? formatNum(collectionStats.totalCollected) : '0'}
                  icon={Database}
                  accent="violet"
                />
                <StatCard
                  title="حقيقية"
                  value={collectionStats ? formatNum(collectionStats.realCount) : '0'}
                  icon={FileText}
                  description="مستندات حقيقية من مصادر طبية"
                  accent="blue"
                />
                <StatCard
                  title="تركيبية"
                  value={collectionStats ? formatNum(collectionStats.syntheticCount) : '0'}
                  icon={RefreshCw}
                  description="بيانات مولّدة اصطناعياً"
                  accent="amber"
                />
                <StatCard
                  title="أكاديمية"
                  value={collectionStats ? formatNum(collectionStats.academicCount) : '0'}
                  icon={BarChart3}
                  description="من أوراق بحثية"
                  accent="emerald"
                />
              </div>

              {/* Quality Breakdown Bar (inline) */}
              <Card className="rounded-xl shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-semibold">توزيع الجودة</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {collectionStats ? (
                    <>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(collectionStats.highQuality / Math.max(1, collectionStats.totalCollected)) * 100}
                          className="h-3 flex-1 [&>div]:bg-green-500"
                        />
                        <span className="text-sm font-medium w-20 text-left">عالية {collectionStats.highQuality}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(collectionStats.mediumQuality / Math.max(1, collectionStats.totalCollected)) * 100}
                          className="h-3 flex-1 [&>div]:bg-yellow-500"
                        />
                        <span className="text-sm font-medium w-20 text-left">متوسطة {collectionStats.mediumQuality}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(collectionStats.lowQuality / Math.max(1, collectionStats.totalCollected)) * 100}
                          className="h-3 flex-1 [&>div]:bg-red-500"
                        />
                        <span className="text-sm font-medium w-20 text-left">منخفضة {collectionStats.lowQuality}</span>
                      </div>
                    </>
                  ) : (
                    <p className="text-muted-foreground text-sm">لا توجد بيانات</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Quality Pie Chart */}
            <Card className="rounded-xl shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <PieChartIcon className="h-5 w-5 text-violet-500" />
                  توزيع جودة البيانات
                </CardTitle>
              </CardHeader>
              <CardContent>
                {qualityPieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie
                        data={qualityPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={4}
                        dataKey="value"
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      >
                        {qualityPieData.map((_, idx) => (
                          <Cell key={idx} fill={QUALITY_COLORS[idx]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[280px] text-muted-foreground text-sm">
                    لا توجد بيانات جودة
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Source Distribution Bar Chart */}
            <Card className="rounded-xl shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-violet-500" />
                  توزيع المصادر
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={sourceDistributionData} layout="vertical" margin={{ top: 5, right: 10, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" />
                    <XAxis type="number" />
                    <YAxis dataKey="source" type="category" className="text-sm" width={90} />
                    <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid hsl(var(--border))' }} />
                    <Bar dataKey="count" name="عدد العينات" fill="#8B5CF6" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Pipeline Phases Visualization */}
          <Card className="rounded-xl shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <ArrowUpDown className="h-5 w-5 text-violet-500" />
                مراحل خط التجميع
              </CardTitle>
              <CardDescription>مرور البيانات عبر مراحل خط الأنابيب</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between gap-2 overflow-x-auto pb-2">
                {PIPELINE_PHASES.map((phase, idx) => {
                  const currentPhaseIdx = collectionStats
                    ? PIPELINE_PHASES.indexOf(collectionStats.phase)
                    : -1;
                  const isActive = idx <= currentPhaseIdx;
                  const isCurrent = idx === currentPhaseIdx;

                  return (
                    <div key={phase} className="flex items-center gap-2 min-w-0 flex-shrink-0">
                      {idx > 0 && (
                        <div className={cn(
                          'w-8 h-0.5 flex-shrink-0 transition-colors',
                          idx <= currentPhaseIdx ? 'bg-violet-500' : 'bg-muted'
                        )} />
                      )}
                      <div className={cn(
                        'flex flex-col items-center gap-2 px-4 py-3 rounded-xl border-2 transition-all min-w-[100px]',
                        isCurrent
                          ? 'border-violet-500 bg-violet-50 dark:bg-violet-950/30 shadow-lg shadow-violet-500/10 scale-105'
                          : isActive
                          ? 'border-green-300 bg-green-50/50 dark:bg-green-950/20 dark:border-green-800'
                          : 'border-muted bg-muted/30'
                      )}>
                        <div className={cn(
                          'w-10 h-10 rounded-full flex items-center justify-center',
                          isCurrent
                            ? 'bg-violet-500 text-white'
                            : isActive
                            ? 'bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-300'
                            : 'bg-muted text-muted-foreground'
                        )}>
                          {isActive ? (
                            isCurrent ? (
                              <Loader2 className="h-5 w-5 animate-spin" />
                            ) : (
                              <CheckCircle2 className="h-5 w-5" />
                            )
                          ) : (
                            <CircleDot className="h-5 w-5" />
                          )}
                        </div>
                        <span className={cn(
                          'text-xs font-medium text-center whitespace-nowrap',
                          isCurrent ? 'text-violet-700 dark:text-violet-300' :
                          isActive ? 'text-green-700 dark:text-green-300' : 'text-muted-foreground'
                        )}>
                          {PIPELINE_LABELS[phase]}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
