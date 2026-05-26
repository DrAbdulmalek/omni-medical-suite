'use client';

import React, { useCallback, useRef, useState } from 'react';
import { Loader2, X, Layers } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useAppStore, ImageItem } from '@/lib/store';
import { toast } from 'sonner';

export function BatchProgress() {
  const images = useAppStore((s) => s.images);
  const setIsProcessing = useAppStore((s) => s.setIsProcessing);
  const setProcessingProgress = useAppStore((s) => s.setProcessingProgress);
  const isProcessing = useAppStore((s) => s.isProcessing);
  const processingProgress = useAppStore((s) => s.processingProgress);
  const [currentFile, setCurrentFile] = useState('');
  const abortRef = useRef(false);

  const handleBatchProcess = useCallback(async () => {
    if (images.length === 0) return;

    const pendingImages = images.filter((img) => img.status === 'pending');
    if (pendingImages.length === 0) {
      toast.error('لا توجد صور قيد الانتظار للمعالجة');
      return;
    }

    abortRef.current = false;
    setIsProcessing(true);
    setProcessingProgress({ current: 0, total: pendingImages.length });

    try {
      const response = await fetch('/api/batch-process-sse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imageIds: pendingImages.map((img) => img.id),
          grayThreshold: 200,
        }),
      });

      if (!response.ok) {
        throw new Error('فشل في بدء المعالجة الدفعية');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('لا يمكن قراءة الاستجابة');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        if (abortRef.current) {
          reader.cancel();
          toast.info('تم إلغاء المعالجة');
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === 'progress') {
              setProcessingProgress({ current: event.index + 1, total: event.total });
              setCurrentFile(event.fileName);
            } else if (event.type === 'error') {
              toast.error(`خطأ في ${event.fileName}: ${event.error}`);
            }
          } catch {
            // Skip malformed events
          }
        }
      }

      if (!abortRef.current) {
        toast.success(`تمت معالجة ${pendingImages.length} صورة بنجاح`);
        // Reload images
        const res = await fetch('/api/images');
        const data = await res.json();
        useAppStore.getState().setImages(data.images);
        // Reload logs
        const logRes = await fetch('/api/logs');
        const logData = await logRes.json();
        useAppStore.getState().setLogs(logData.logs);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'حدث خطأ في المعالجة');
    } finally {
      setIsProcessing(false);
      setProcessingProgress({ current: 0, total: 0 });
      setCurrentFile('');
    }
  }, [images, setIsProcessing, setProcessingProgress]);

  const handleCancel = useCallback(() => {
    abortRef.current = true;
  }, []);

  const pendingCount = images.filter((img) => img.status === 'pending').length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Layers className="size-4 text-emerald-600" />
          معالجة دفعية SSE
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isProcessing && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground truncate max-w-[200px]">{currentFile}</span>
              <span className="font-medium">
                {processingProgress.current} / {processingProgress.total}
              </span>
            </div>
            <Progress value={(processingProgress.current / processingProgress.total) * 100} className="h-2" />
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCancel}
              className="w-full gap-2 h-9"
            >
              <X className="size-4" />
              إلغاء المعالجة
            </Button>
          </div>
        )}

        {!isProcessing && (
          <Button
            onClick={handleBatchProcess}
            disabled={pendingCount === 0}
            className="w-full gap-2 h-9 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Layers className="size-4" />
            معالجة الكل ({pendingCount})
          </Button>
        )}

        {pendingCount > 0 && !isProcessing && (
          <p className="text-xs text-muted-foreground text-center">
            {pendingCount} صورة قيد الانتظار
          </p>
        )}
      </CardContent>
    </Card>
  );
}
