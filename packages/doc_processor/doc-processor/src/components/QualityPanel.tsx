'use client';

import React from 'react';
import {
  Eye,
  Sun,
  Contrast,
  Gauge,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';

export function QualityPanel() {
  const images = useAppStore((s) => s.images);
  const selectedImageId = useAppStore((s) => s.selectedImageId);
  const selectedImage = images.find((img) => img.id === selectedImageId);

  if (!selectedImage) {
    return null;
  }

  const blurBefore = selectedImage.blurBefore;
  const blurAfter = selectedImage.blurAfter;

  const getQualityLabel = (score: number): string => {
    if (score > 300) return 'ممتاز';
    if (score > 100) return 'مقبول';
    return 'ضبابي';
  };

  const getQualityIcon = (label: string) => {
    switch (label) {
      case 'ممتاز':
        return <CheckCircle2 className="size-5" />;
      case 'مقبول':
        return <AlertTriangle className="size-5" />;
      case 'ضبابي':
        return <XCircle className="size-5" />;
      default:
        return <Eye className="size-5" />;
    }
  };

  const getQualityColor = (label: string): string => {
    switch (label) {
      case 'ممتاز':
        return 'text-emerald-600';
      case 'مقبول':
        return 'text-amber-600';
      case 'ضبابي':
        return 'text-red-600';
      default:
        return 'text-muted-foreground';
    }
  };

  const getQualityBgColor = (label: string): string => {
    switch (label) {
      case 'ممتاز':
        return 'bg-emerald-100';
      case 'مقبول':
        return 'bg-amber-100';
      case 'ضبابي':
        return 'bg-red-100';
      default:
        return 'bg-muted';
    }
  };

  const currentLabel = getQualityLabel(blurAfter > 0 ? blurAfter : blurBefore);
  const improvement = blurBefore > 0 && blurAfter > 0
    ? Math.round(((blurAfter - blurBefore) / Math.max(blurBefore, 1)) * 100)
    : 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Eye className="size-4 text-emerald-600" />
          تقييم الجودة
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className={cn(
            'flex items-center gap-3 rounded-lg p-3',
            getQualityBgColor(currentLabel)
          )}
        >
          <div className={getQualityColor(currentLabel)}>
            {getQualityIcon(currentLabel)}
          </div>
          <div>
            <div className={cn('font-bold text-sm', getQualityColor(currentLabel))}>
              {currentLabel}
            </div>
            <div className="text-xs text-muted-foreground">تقييم عام للجودة</div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-2">
          {/* Blur Score Before */}
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-muted/50">
            <div className="flex items-center gap-2 text-sm">
              <Gauge className="size-4 text-muted-foreground" />
              جودة قبل المعالجة
            </div>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min((blurBefore / 500) * 100, 100)}%`,
                    backgroundColor:
                      blurBefore > 300 ? '#16a34a' : blurBefore > 100 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
              <span className="text-xs font-mono w-12 text-left">{Math.round(blurBefore)}</span>
            </div>
          </div>

          {/* Blur Score After */}
          {blurAfter > 0 && (
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-muted/50">
              <div className="flex items-center gap-2 text-sm">
                <Gauge className="size-4 text-emerald-500" />
                جودة بعد المعالجة
              </div>
              <div className="flex items-center gap-2">
                <div className="w-20 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min((blurAfter / 500) * 100, 100)}%`,
                      backgroundColor:
                        blurAfter > 300 ? '#16a34a' : blurAfter > 100 ? '#f59e0b' : '#ef4444',
                    }}
                  />
                </div>
                <span className="text-xs font-mono w-12 text-left">{Math.round(blurAfter)}</span>
              </div>
            </div>
          )}

          {/* Improvement */}
          {improvement !== 0 && (
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-muted/50">
              <div className="flex items-center gap-2 text-sm">
                <Contrast className="size-4 text-muted-foreground" />
                التحسن
              </div>
              <span className={cn('text-xs font-mono font-bold', improvement > 0 ? 'text-emerald-600' : 'text-red-600')}>
                {improvement > 0 ? '+' : ''}{improvement}%
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
