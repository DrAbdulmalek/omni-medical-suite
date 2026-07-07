'use client';

import React, { useCallback, useRef, useState } from 'react';
import { Upload, ImageIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { toast } from 'sonner';

interface ImageUploaderProps {
  onUpload: (files: FileList | null) => void;
  uploading?: boolean;
}

export function ImageUploader({ onUpload, uploading = false }: ImageUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    onUpload(e.dataTransfer.files);
  }, [onUpload]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  return (
    <Card className="border-dashed">
      <CardContent className="p-4">
        <div
          className={`relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-6 transition-colors min-h-[140px] ${
            isDragOver
              ? 'border-emerald-500 bg-emerald-50'
              : 'border-muted-foreground/25 hover:border-muted-foreground/50'
          }`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="flex items-center gap-2 text-muted-foreground">
            {uploading ? (
              <Upload className="size-8 animate-pulse" />
            ) : (
              <Upload className="size-8" />
            )}
          </div>
          <div className="text-center">
            <p className="text-sm font-medium">اسحب الصور وأفلتها هنا</p>
            <p className="text-xs text-muted-foreground mt-1">
              PNG, JPG, TIFF, BMP, WebP
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            className="gap-2"
          >
            <ImageIcon className="size-4" />
            اختيار ملفات
          </Button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp"
            multiple
            className="hidden"
            onChange={(e) => onUpload(e.target.files)}
          />
        </div>
      </CardContent>
    </Card>
  );
}
