'use client';

import React, { useState, useCallback, useRef } from 'react';
import { ArrowLeftRight, Eye, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ComparisonViewProps {
  imageId: string;
  originalName: string;
  onClose: () => void;
}

export function ComparisonView({ imageId, originalName, onClose }: ComparisonViewProps) {
  const [showOriginal, setShowOriginal] = useState(false);
  const [splitPosition, setSplitPosition] = useState(50);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const originalUrl = `/api/preview?file=${encodeURIComponent(`/home/z/my-project/uploads/${originalName}`)}`;
  // For comparison, we show the same image since our system overwrites
  // In a real scenario, original would be stored separately
  const processedUrl = originalUrl;

  const handleMouseMove = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      if (!isDragging.current || !containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      let clientX: number;

      if ('touches' in e) {
        clientX = e.touches[0].clientX;
      } else {
        clientX = e.clientX;
      }

      const x = clientX - rect.left;
      const percentage = (x / rect.width) * 100;
      setSplitPosition(Math.min(Math.max(percentage, 5), 95));
    },
    []
  );

  const handleStart = useCallback(() => {
    isDragging.current = true;
  }, []);

  const handleEnd = useCallback(() => {
    isDragging.current = false;
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-bold text-slate-900">مقارنة قبل/بعد</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
            <ArrowLeftRight className="size-4 text-emerald-600" />
            اسحب الفاصل للمقارنة
          </div>
          <div className="flex gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowOriginal(false)}
              className={cn(
                'h-8 text-xs gap-1.5',
                !showOriginal && 'bg-emerald-50 text-emerald-700 border-emerald-200'
              )}
            >
              <Eye className="size-3.5" />
              مقارنة
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowOriginal(true)}
              className={cn(
                'h-8 text-xs gap-1.5',
                showOriginal && 'bg-emerald-50 text-emerald-700 border-emerald-200'
              )}
            >
              الأصلية
            </Button>
          </div>
        </div>

        {/* Image Area */}
        <div className="p-4">
          {showOriginal ? (
            <div className="rounded-lg border overflow-hidden bg-muted/20">
              <img
                src={originalUrl}
                alt="الصورة الأصلية"
                className="w-full h-auto max-h-[500px] object-contain"
              />
            </div>
          ) : (
            <div
              ref={containerRef}
              className="relative w-full rounded-lg border overflow-hidden bg-muted/20 cursor-col-resize select-none"
              onMouseDown={handleStart}
              onMouseUp={handleEnd}
              onMouseLeave={handleEnd}
              onMouseMove={handleMouseMove}
              onTouchStart={handleStart}
              onTouchEnd={handleEnd}
              onTouchMove={handleMouseMove}
            >
              <img
                src={processedUrl}
                alt="بعد المعالجة"
                className="w-full h-auto max-h-[500px] object-contain"
              />
              <div
                className="absolute inset-0 overflow-hidden"
                style={{
                  clipPath: `inset(0 ${100 - splitPosition}% 0 0)`,
                }}
              >
                <img
                  src={originalUrl}
                  alt="قبل المعالجة"
                  className="w-full h-auto max-h-[500px] object-contain"
                  draggable={false}
                />
              </div>

              <div
                className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg z-10"
                style={{ right: `${splitPosition}%` }}
              >
                <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center">
                  <ArrowLeftRight className="size-4 text-gray-700" />
                </div>
              </div>

              <div className="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                قبل
              </div>
              <div className="absolute top-2 left-2 bg-emerald-600/90 text-white text-xs px-2 py-1 rounded">
                بعد
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
