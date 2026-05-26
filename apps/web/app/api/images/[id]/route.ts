import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';
import { applyCrop, calculateBlurScore } from '@/lib/image-processing';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const { cropLeft, cropTop, cropRight, cropBottom, deskewAngle } = body;

    const image = await db.processedImage.findUnique({ where: { id } });
    if (!image) {
      return NextResponse.json({ error: 'الصورة غير موجودة' }, { status: 404 });
    }

    const filePath = path.join(UPLOADS_DIR, image.fileName);
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'الملف غير موجود' }, { status: 404 });
    }

    const buffer = fs.readFileSync(filePath);
    const ops: string[] = [...JSON.parse(image.operations || '[]')];

    // Apply crop if values changed
    let resultBuffer = buffer;
    let newWidth = image.width;
    let newHeight = image.height;

    if (cropLeft !== undefined && cropTop !== undefined && cropRight !== undefined && cropBottom !== undefined) {
      resultBuffer = await applyCrop(buffer, cropLeft, cropTop, cropRight, cropBottom);
      const meta = await import('sharp').then(s => s.default(resultBuffer).metadata());
      newWidth = (await meta).width || image.width;
      newHeight = (await meta).height || image.height;
      ops.push('تعديل يدوي');
      fs.writeFileSync(filePath, resultBuffer);
    }

    const blurAfter = await calculateBlurScore(resultBuffer);

    const updated = await db.processedImage.update({
      where: { id },
      data: {
        cropLeft: cropLeft !== undefined ? cropLeft : image.cropLeft,
        cropTop: cropTop !== undefined ? cropTop : image.cropTop,
        cropRight: cropRight !== undefined ? cropRight : image.cropRight,
        cropBottom: cropBottom !== undefined ? cropBottom : image.cropBottom,
        deskewAngle: deskewAngle !== undefined ? deskewAngle : image.deskewAngle,
        blurAfter,
        width: newWidth,
        height: newHeight,
        operations: JSON.stringify(ops),
      }
    });

    await db.processingLog.create({
      data: {
        imageId: id,
        imageName: image.originalName,
        action: 'تحديث',
        details: `تحديث معلمات الصورة يدوياً`,
        quality: Math.round(blurAfter),
      }
    });

    return NextResponse.json({ success: true, image: updated });
  } catch (error) {
    console.error('Update image error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
