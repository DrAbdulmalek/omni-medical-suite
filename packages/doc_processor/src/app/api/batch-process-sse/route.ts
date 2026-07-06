import { NextRequest } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';
import sharp from 'sharp';
import { smartCrop, calculateBlurScore } from '@/lib/image-processing';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { imageIds, grayThreshold = 200 } = body;

    if (!imageIds || !Array.isArray(imageIds) || imageIds.length === 0) {
      return new Response(JSON.stringify({ error: 'لم يتم توفير معرفات الصور' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const images = await db.processedImage.findMany({
      where: { id: { in: imageIds } },
      orderBy: { createdAt: 'asc' },
    });

    if (images.length === 0) {
      return new Response(JSON.stringify({ error: 'لم يتم العثور على صور' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          for (let i = 0; i < images.length; i++) {
            const image = images[i];
            const filePath = path.join(UPLOADS_DIR, image.fileName);

            if (!fs.existsSync(filePath)) {
              const skipEvent = {
                type: 'error',
                index: i,
                total: images.length,
                fileName: image.originalName,
                error: 'الملف غير موجود',
              };
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(skipEvent)}\n\n`));
              continue;
            }

            const buffer = fs.readFileSync(filePath);
            const cropResult = await smartCrop(buffer, grayThreshold);
            const blurAfter = await calculateBlurScore(cropResult.cropped);

            // Save processed
            fs.writeFileSync(filePath, cropResult.cropped);

            const ops: string[] = [...JSON.parse(image.operations || '[]')];
            ops.push('معالجة دفعية (SSE)');

            await db.processedImage.update({
              where: { id: image.id },
              data: {
                cropLeft: cropResult.cropLeft,
                cropTop: cropResult.cropTop,
                cropRight: cropResult.cropRight,
                cropBottom: cropResult.cropBottom,
                blurAfter,
                status: 'processed',
                operations: JSON.stringify(ops),
              },
            });

            await db.processingLog.create({
              data: {
                imageId: image.id,
                imageName: image.originalName,
                action: 'معالجة دفعية SSE',
                details: `L=${cropResult.cropLeft} T=${cropResult.cropTop} R=${cropResult.cropRight} B=${cropResult.cropBottom}`,
                quality: Math.round(blurAfter),
              },
            });

            const progressEvent = {
              type: 'progress',
              index: i,
              total: images.length,
              fileName: image.originalName,
              quality: { blurScore: Math.round(blurAfter) },
            };

            controller.enqueue(encoder.encode(`data: ${JSON.stringify(progressEvent)}\n\n`));
          }

          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', total: images.length })}\n\n`));
          controller.close();
        } catch (error) {
          const message = error instanceof Error ? error.message : 'خطأ في المعالجة';
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', error: message })}\n\n`));
          controller.close();
        }
      },
    });

    return new Response(stream, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error: unknown) {
    console.error('SSE Batch processing error:', error);
    const message = error instanceof Error ? error.message : 'خطأ في المعالجة الدفعية';
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
