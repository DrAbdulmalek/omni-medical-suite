import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { db } from '@/lib/db';
import { extractFeatures, loadModel, predict } from '@/lib/trainable-algorithm';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const image = await db.processedImage.findUnique({ where: { id } });

    if (!image) {
      return NextResponse.json({ error: 'الصورة غير موجودة' }, { status: 404 });
    }

    const filePath = path.join(UPLOADS_DIR, image.fileName);
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'الملف غير موجود على الخادم' }, { status: 404 });
    }

    // Load the trained model
    const model = loadModel();
    if (!model) {
      return NextResponse.json({
        error: 'النموذج غير مدرب بعد. يرجى تدريب النموذج أولاً من صفحة بيانات التدريب.',
        modelNotTrained: true,
      }, { status: 400 });
    }

    // Extract features from the image
    const buffer = fs.readFileSync(filePath);
    const features = await extractFeatures(buffer);

    // Predict settings
    const prediction = predict(features, model);

    return NextResponse.json({
      success: true,
      imageId: id,
      features,
      prediction,
    });
  } catch (error) {
    console.error('Predict error:', error);
    return NextResponse.json({ error: 'حدث خطأ أثناء التنبؤ' }, { status: 500 });
  }
}
