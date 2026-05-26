import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';
import { extractPageNumber } from '@/lib/ocr';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function POST(request: NextRequest) {
  try {
    const { imageId } = await request.json();

    if (!imageId) {
      return NextResponse.json({ error: 'معرف الصورة مطلوب' }, { status: 400 });
    }

    const image = await db.processedImage.findUnique({ where: { id: imageId } });

    if (!image) {
      return NextResponse.json({ error: 'الصورة غير موجودة' }, { status: 404 });
    }

    const filePath = path.join(UPLOADS_DIR, image.fileName);
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'الملف غير موجود على الخادم' }, { status: 404 });
    }

    const buffer = fs.readFileSync(filePath);

    // Extract page number via OCR
    const { pageNumber, fullText } = await extractPageNumber(buffer);

    // Update the database record
    await db.processedImage.update({
      where: { id: imageId },
      data: {
        pageNumber: pageNumber || '',
      },
    });

    return NextResponse.json({
      success: true,
      pageNumber,
      fullText,
      imageId,
    });
  } catch (error) {
    console.error('Extract page number error:', error);
    return NextResponse.json({ error: 'حدث خطأ أثناء استخراج رقم الصفحة' }, { status: 500 });
  }
}
