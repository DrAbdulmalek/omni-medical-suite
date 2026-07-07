import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');

    const where = status && status !== 'all' ? { status } : {};

    const images = await db.processedImage.findMany({
      where,
      orderBy: { createdAt: 'desc' },
    });

    const imagesWithUrls = images.map(img => ({
      ...img,
      operations: JSON.parse(img.operations || '[]'),
      previewUrl: `/api/preview?file=${encodeURIComponent(`/home/z/my-project/uploads/${img.fileName}`)}`,
      thumbnailUrl: `/api/preview?file=${encodeURIComponent(`/home/z/my-project/uploads/thumbnails/thumb_${img.fileName.replace(/\.[^.]+$/, '.png')}`)}`,
    }));

    return NextResponse.json({ images: imagesWithUrls });
  } catch (error) {
    console.error('Get images error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
