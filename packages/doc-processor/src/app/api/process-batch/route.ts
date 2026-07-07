import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function POST() {
  try {
    const pendingImages = await db.processedImage.findMany({
      where: { status: 'pending' },
      orderBy: { createdAt: 'asc' },
    });

    const results = [];

    for (const image of pendingImages) {
      try {
        // Process image - auto-detect operations
        const ops: string[] = [...JSON.parse(image.operations || '[]')];

        // Auto smart crop
        const { smartCrop, calculateBlurScore } = await import('@/lib/image-processing');
        const fs = await import('fs');
        const path = await import('path');

        const filePath = path.join('/home/z/my-project/uploads', image.fileName);

        if (fs.existsSync(filePath)) {
          const buffer = fs.readFileSync(filePath);
          const cropResult = await smartCrop(buffer, 200);
          const blurAfter = await calculateBlurScore(cropResult.cropped);

          // Save processed
          fs.writeFileSync(filePath, cropResult.cropped);

          ops.push('قص ذكي تلقائي');

          const updated = await db.processedImage.update({
            where: { id: image.id },
            data: {
              cropLeft: cropResult.cropLeft,
              cropTop: cropResult.cropTop,
              cropRight: cropResult.cropRight,
              cropBottom: cropResult.cropBottom,
              blurAfter,
              status: 'processed',
              operations: JSON.stringify(ops),
            }
          });

          await db.processingLog.create({
            data: {
              imageId: image.id,
              imageName: image.originalName,
              action: 'معالجة تلقائية',
              details: `L=${cropResult.cropLeft} T=${cropResult.cropTop} R=${cropResult.cropRight} B=${cropResult.cropBottom}`,
              quality: Math.round(blurAfter),
            }
          });

          results.push({ id: image.id, status: 'processed' });
        } else {
          await db.processedImage.update({
            where: { id: image.id },
            data: { status: 'skipped' }
          });
          results.push({ id: image.id, status: 'skipped' });
        }
      } catch (err) {
        results.push({ id: image.id, status: 'error', error: String(err) });
      }
    }

    return NextResponse.json({
      success: true,
      processed: results.length,
      results,
    });
  } catch (error) {
    console.error('Batch process error:', error);
    return NextResponse.json({ error: 'حدث خطأ أثناء المعالجة' }, { status: 500 });
  }
}
