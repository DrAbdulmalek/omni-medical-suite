'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useAppStore } from '@/lib/store';
import {
  Images,
  CheckCircle2,
  Clock,
  SkipForward,
  TrendingUp,
  Activity,
  Brain,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';

interface StatsResponse {
  totalImages: number;
  processed: number;
  pending: number;
  skipped: number;
  avgBlurBefore: number;
  avgBlurAfter: number;
  avgImprovement: number;
  trainingCount: number;
  recentLogs: Array<{
    id: string;
    imageName: string;
    action: string;
    details: string;
    quality: number;
    timestamp: string;
  }>;
}

const statCards = [
  {
    key: 'totalImages' as const,
    label: 'إجمالي الصور',
    icon: <Images className="h-6 w-6" />,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
  },
  {
    key: 'processed' as const,
    label: 'تمت معالجتها',
    icon: <CheckCircle2 className="h-6 w-6" />,
    color: 'text-teal-600',
    bg: 'bg-teal-50',
  },
  {
    key: 'pending' as const,
    label: 'قيد الانتظار',
    icon: <Clock className="h-6 w-6" />,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
  },
  {
    key: 'skipped' as const,
    label: 'تم تخطيها',
    icon: <SkipForward className="h-6 w-6" />,
    color: 'text-slate-500',
    bg: 'bg-slate-50',
  },
];

function getActionBadge(action: string) {
  switch (action) {
    case 'رفع':
      return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">رفع</Badge>;
    case 'حفظ':
      return <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100">حفظ</Badge>;
    case 'تخطي':
      return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">تخطي</Badge>;
    case 'قص ذكي':
      return <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100">قص ذكي</Badge>;
    case 'ميلان':
      return <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">ميلان</Badge>;
    case 'إزالة رمادي':
      return <Badge className="bg-orange-100 text-orange-700 hover:bg-orange-100">إزالة رمادي</Badge>;
    case 'تنبؤ':
      return <Badge className="bg-pink-100 text-pink-700 hover:bg-pink-100">تنبؤ</Badge>;
    default:
      return <Badge variant="secondary">{action}</Badge>;
  }
}

export default function DashboardView() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [qualityData, setQualityData] = useState<Array<{ name: string; before: number; after: number }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      setStats(data);

      // Load training data for chart
      const trainingRes = await fetch('/api/training');
      const trainingData = await trainingRes.json();

      const chartData = trainingData.records?.slice(0, 20).map((r: { imageName: string; blurBefore: number; blurAfter: number }) => ({
        name: r.imageName.replace(/\.[^.]+$/, ''),
        before: Math.round(r.blurBefore),
        after: Math.round(r.blurAfter),
      })) || [];

      setQualityData(chartData);
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-emerald-600 animate-pulse-emerald text-lg">جارٍ تحميل الإحصائيات...</div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-500">لا توجد بيانات متاحة</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 lg:p-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">لوحة التحكم</h2>
        <p className="text-slate-500 mt-1">نظرة عامة على حالة المعالجة</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <Card key={card.key} className="border-0 shadow-sm hover:shadow-md transition-shadow">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500 mb-1">{card.label}</p>
                  <p className="text-3xl font-bold text-slate-900">
                    {stats[card.key].toLocaleString('ar-EG')}
                  </p>
                </div>
                <div className={`p-3 rounded-xl ${card.bg}`}>
                  <div className={card.color}>{card.icon}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quality Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-0 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-50">
                <TrendingUp className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">متوسط جودة قبل المعالجة</p>
                <p className="text-xl font-bold text-slate-900">{stats.avgBlurBefore}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-teal-50">
                <Activity className="h-5 w-5 text-teal-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">متوسط جودة بعد المعالجة</p>
                <p className="text-xl font-bold text-slate-900">{stats.avgBlurAfter}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50">
                <Brain className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-xs text-slate-500">سجلات التدريب</p>
                <p className="text-xl font-bold text-slate-900">{stats.trainingCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quality Comparison Chart */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">مقارنة جودة الصور</CardTitle>
          </CardHeader>
          <CardContent>
            {qualityData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={qualityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-45} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: '8px',
                        border: 'none',
                        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                        direction: 'rtl',
                      }}
                      formatter={(value: number, name: string) => [
                        value,
                        name === 'before' ? 'قبل المعالجة' : 'بعد المعالجة',
                      ]}
                    />
                    <Bar dataKey="before" fill="#94a3b8" name="قبل" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="after" fill="#10b981" name="بعد" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-slate-400">
                لا توجد بيانات كافية لعرض الرسم البياني
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">النشاط الأخير</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-72 overflow-y-auto space-y-3">
              {stats.recentLogs && stats.recentLogs.length > 0 ? (
                stats.recentLogs.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    {getActionBadge(log.action)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {log.imageName}
                      </p>
                      <p className="text-xs text-slate-400 truncate">{log.details}</p>
                    </div>
                    {log.quality > 0 && (
                      <span className="text-xs text-emerald-600 font-medium whitespace-nowrap">
                        {log.quality}
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center text-slate-400 py-8">
                  لا يوجد نشاط حديث
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
