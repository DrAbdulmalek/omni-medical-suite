'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LogItem } from '@/lib/store';
import {
  Search,
  RefreshCw,
  ClipboardList,
  CheckCircle2,
  SkipForward,
  AlertCircle,
  Upload,
  Crop,
  RotateCcw,
  Eraser,
} from 'lucide-react';

const actionFilters = [
  { value: 'all', label: 'الكل' },
  { value: 'رفع', label: 'رفع' },
  { value: 'حفظ', label: 'حفظ' },
  { value: 'تخطي', label: 'تخطي' },
  { value: 'قص ذكي', label: 'قص ذكي' },
  { value: 'ميلان', label: 'ميلان' },
  { value: 'إزالة رمادي', label: 'إزالة رمادي' },
  { value: 'تنبؤ', label: 'تنبؤ' },
  { value: 'معالجة تلقائية', label: 'معالجة تلقائية' },
];

function getActionIcon(action: string) {
  switch (action) {
    case 'رفع':
      return <Upload className="h-4 w-4 text-emerald-500" />;
    case 'حفظ':
      return <CheckCircle2 className="h-4 w-4 text-teal-500" />;
    case 'تخطي':
      return <SkipForward className="h-4 w-4 text-amber-500" />;
    case 'قص ذكي':
    case 'قص يدوي':
    case 'تعديل يدوي':
      return <Crop className="h-4 w-4 text-purple-500" />;
    case 'ميلان':
    case 'كشف ميلان':
      return <RotateCcw className="h-4 w-4 text-blue-500" />;
    case 'إزالة رمادي':
      return <Eraser className="h-4 w-4 text-orange-500" />;
    case 'تنبؤ':
      return <AlertCircle className="h-4 w-4 text-pink-500" />;
    default:
      return <ClipboardList className="h-4 w-4 text-slate-400" />;
  }
}

function getActionColor(action: string) {
  switch (action) {
    case 'رفع':
      return 'border-emerald-200 bg-emerald-50/50';
    case 'حفظ':
      return 'border-teal-200 bg-teal-50/50';
    case 'تخطي':
      return 'border-amber-200 bg-amber-50/50';
    case 'قص ذكي':
    case 'قص يدوي':
      return 'border-purple-200 bg-purple-50/50';
    case 'ميلان':
    case 'كشف ميلان':
      return 'border-blue-200 bg-blue-50/50';
    case 'إزالة رمادي':
      return 'border-orange-200 bg-orange-50/50';
    default:
      return 'border-slate-200 bg-slate-50/50';
  }
}

function getActionBadge(action: string) {
  switch (action) {
    case 'رفع':
      return <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 text-xs">{action}</Badge>;
    case 'حفظ':
      return <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100 text-xs">{action}</Badge>;
    case 'تخطي':
      return <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 text-xs">{action}</Badge>;
    case 'قص ذكي':
    case 'قص يدوي':
      return <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100 text-xs">{action}</Badge>;
    case 'ميلان':
    case 'كشف ميلان':
      return <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100 text-xs">{action}</Badge>;
    case 'إزالة رمادي':
      return <Badge className="bg-orange-100 text-orange-700 hover:bg-orange-100 text-xs">{action}</Badge>;
    case 'تنبؤ':
      return <Badge className="bg-pink-100 text-pink-700 hover:bg-pink-100 text-xs">{action}</Badge>;
    default:
      return <Badge variant="secondary" className="text-xs">{action}</Badge>;
  }
}

export default function ProcessingLogView() {
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadLogs();
  }, []);

  async function loadLogs() {
    try {
      const params = filter !== 'all' ? `?action=${filter}` : '';
      const res = await fetch(`/api/logs${params}`);
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLogs();
  }, [filter]);

  const filteredLogs = logs.filter(
    (log) =>
      log.imageName.toLowerCase().includes(search.toLowerCase()) ||
      log.details.toLowerCase().includes(search.toLowerCase())
  );

  // Group logs by date
  const groupedLogs = filteredLogs.reduce(
    (acc, log) => {
      const date = new Date(log.timestamp).toLocaleDateString('ar-EG', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
      if (!acc[date]) acc[date] = [];
      acc[date].push(log);
      return acc;
    },
    {} as Record<string, LogItem[]>
  );

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">سجل المعالجة</h2>
          <p className="text-slate-500 mt-1">{filteredLogs.length} سجل</p>
        </div>
        <Button onClick={loadLogs} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 ml-2" />
          تحديث
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="البحث في السجلات..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pr-10"
          />
        </div>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="نوع الإجراء" />
          </SelectTrigger>
          <SelectContent>
            {actionFilters.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Log List */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="text-emerald-600 animate-pulse-emerald">جارٍ التحميل...</div>
        </div>
      ) : filteredLogs.length === 0 ? (
        <Card className="border-0 shadow-sm">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <ClipboardList className="h-12 w-12 text-slate-300 mb-3" />
            <p className="text-slate-500">لا توجد سجلات</p>
            <p className="text-xs text-slate-400 mt-1">ابدأ برفع ومعالجة الصور لتظهر السجلات هنا</p>
          </CardContent>
        </Card>
      ) : (
        <div ref={logRef} className="space-y-6 max-h-[calc(100vh-280px)] overflow-y-auto">
          {Object.entries(groupedLogs).map(([date, dateLogs]) => (
            <div key={date}>
              <div className="sticky top-0 bg-slate-50 z-10 py-2 mb-2">
                <h3 className="text-sm font-semibold text-slate-600">{date}</h3>
              </div>
              <div className="space-y-2">
                {dateLogs.map((log) => (
                  <Card key={log.id} className={`border ${getActionColor(log.action)} shadow-none`}>
                    <CardContent className="p-3">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5">{getActionIcon(log.action)}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium text-slate-800">{log.imageName}</span>
                            {getActionBadge(log.action)}
                          </div>
                          <p className="text-xs text-slate-500 mt-1 truncate">{log.details}</p>
                        </div>
                        <div className="text-left flex-shrink-0">
                          <span className="text-xs text-slate-400">
                            {new Date(log.timestamp).toLocaleTimeString('ar-EG', {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </span>
                          {log.quality > 0 && (
                            <div className="text-xs text-emerald-600 font-medium mt-0.5">
                              جودة: {log.quality}
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
