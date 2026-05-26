import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET() {
  try {
    const totalImages = await db.processedImage.count();
    const processed = await db.processedImage.count({ where: { status: 'processed' } });
    const pending = await db.processedImage.count({ where: { status: 'pending' } });
    const skipped = await db.processedImage.count({ where: { status: 'skipped' } });

    // Average blur scores
    const processedImages = await db.processedImage.findMany({
      where: { status: 'processed', blurBefore: { gt: 0 }, blurAfter: { gt: 0 } },
      select: { blurBefore: true, blurAfter: true },
    });

    let avgBlurBefore = 0;
    let avgBlurAfter = 0;
    let avgImprovement = 0;

    if (processedImages.length > 0) {
      const totalBefore = processedImages.reduce((sum, img) => sum + img.blurBefore, 0);
      const totalAfter = processedImages.reduce((sum, img) => sum + img.blurAfter, 0);
      avgBlurBefore = Math.round((totalBefore / processedImages.length) * 100) / 100;
      avgBlurAfter = Math.round((totalAfter / processedImages.length) * 100) / 100;
      avgImprovement = Math.round((avgBlurAfter - avgBlurBefore) * 100) / 100;
    }

    // Recent logs for activity
    const recentLogs = await db.processingLog.findMany({
      orderBy: { timestamp: 'desc' },
      take: 10,
    });

    // Training records count
    const trainingCount = await db.trainingRecord.count();

    return NextResponse.json({
      totalImages,
      processed,
      pending,
      skipped,
      avgBlurBefore,
      avgBlurAfter,
      avgImprovement,
      trainingCount,
      recentLogs: recentLogs.map(l => ({
        id: l.id,
        imageName: l.imageName,
        action: l.action,
        details: l.details,
        quality: l.quality,
        timestamp: l.timestamp.toISOString(),
      })),
    });
  } catch (error) {
    console.error('Stats error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
