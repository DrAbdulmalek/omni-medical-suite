'use client';

import React from 'react';
import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';
import { ImageIcon } from 'lucide-react';

export function ThumbnailStrip() {
  const images = useAppStore((s) => s.images);
  const selectedImageId = useAppStore((s) => s.selectedImageId);
  const setSelectedImageId = useAppStore((s) => s.setSelectedImageId);

  if (images.length === 0) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
      {images.map((img) => {
        const isSelected = img.id === selectedImageId;
        const isProcessed = img.status === 'processed';

        return (
          <button
            key={img.id}
            onClick={() => setSelectedImageId(img.id)}
            className={cn(
              'relative flex-shrink-0 w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden cursor-pointer border-2 transition-all group',
              isSelected
                ? 'border-emerald-500 shadow-md ring-2 ring-emerald-500/20'
                : 'border-transparent hover:border-muted-foreground/30'
            )}
          >
            <img
              src={`/api/preview?file=${encodeURIComponent(`/home/z/my-project/uploads/${img.fileName}`)}`}
              alt={img.originalName}
              className="w-full h-full object-cover"
            />
            {isProcessed && (
              <div className="absolute bottom-0 inset-x-0 bg-emerald-500 text-white text-[9px] text-center py-0.5 font-medium">
                معالج
              </div>
            )}
            {img.status === 'pending' && (
              <div className="absolute bottom-0 inset-x-0 bg-amber-400 text-white text-[9px] text-center py-0.5 font-medium">
                قيد الانتظار
              </div>
            )}
            <div className="absolute top-0 inset-x-0 bg-gradient-to-b from-black/40 to-transparent h-5 flex items-center justify-center">
              <span className="text-white text-[8px] truncate px-1">{img.originalName}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
