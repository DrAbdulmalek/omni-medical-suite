import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { db } from '@/lib/db';
import {
  extractFeatures,
  getTrainingEntriesFromDB,
  trainModel,
  saveModel,
  predict,
} from '@/lib/trainable-algorithm';

const UPLOADS_DIR = '/home/z/my-project/uploads';

export async function POST() {
  try {
    // Get all training records from DB
    const dbRecords = await db.trainingRecord.findMany();
    const trainingEntries = await getTrainingEntriesFromDB();

    if (trainingEntries.length === 0) {
      return NextResponse.json({
        success: false,
        error: 'لا توجد بيانات تدريب كافية. قم بمعالجة بعض الصور أولاً.',
        entries: 0,
      });
    }

    // For records that don't have full features, try to extract from images
    const processedImages = await db.processedImage.findMany();

    for (const record of dbRecords) {
      try {
        const features = JSON.parse(record.features);
        // Skip if we already have blurScore (meaning features were extracted properly)
        if (features.blurScore !== undefined) continue;

        // Try to find the image file
        const image = processedImages.find((img) => img.originalName === record.imageName);
        if (!image) continue;

        const filePath = path.join(UPLOADS_DIR, image.fileName);
        if (!fs.existsSync(filePath)) continue;

        const buffer = fs.readFileSync(filePath);
        const extractedFeatures = await extractFeatures(buffer);

        // Update the record with proper features
        await db.trainingRecord.update({
          where: { id: record.id },
          data: {
            features: JSON.stringify(extractedFeatures),
          },
        });
      } catch {
        // Skip records that can't be processed
      }
    }

    // Reload entries after feature extraction
    const finalEntries = await getTrainingEntriesFromDB();

    if (finalEntries.length === 0) {
      return NextResponse.json({
        success: false,
        error: 'فشل في استخراج الخصائص من الصور. تأكد من وجود ملفات الصور.',
        entries: 0,
      });
    }

    // Train the model
    const model = trainModel(finalEntries);

    // Calculate model metrics
    let totalDistance = 0;
    let metricsCount = 0;

    for (const entry of finalEntries) {
      const prediction = predict(entry.features, model);
      const dist = Math.sqrt(
        ((prediction.pageThreshold - entry.settings.pageThreshold) / 50) ** 2 +
        ((prediction.grayThreshold - entry.settings.grayThreshold) / 25) ** 2 +
        ((prediction.padding - entry.settings.padding) / 25) ** 2
      );
      totalDistance += dist;
      metricsCount++;
    }

    const avgDistance = metricsCount > 0 ? totalDistance / metricsCount : 1;

    // Save the model
    saveModel(model);

    return NextResponse.json({
      success: true,
      entries: finalEntries.length,
      avgDistance: Math.round(avgDistance * 100) / 100,
      avgConfidence: model.avgConfidence,
      trainedAt: model.trainedAt,
      message: `تم تدريب النموذج بنجاح باستخدام ${finalEntries.length} سجل تدريب`,
    });
  } catch (error) {
    console.error('Train error:', error);
    return NextResponse.json(
      { error: 'حدث خطأ أثناء تدريب النموذج', success: false },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const { loadModel } = await import('@/lib/trainable-algorithm');
    const model = loadModel();

    if (!model) {
      return NextResponse.json({
        trained: false,
        lastTrained: '',
        entries: 0,
        avgConfidence: 0,
      });
    }

    return NextResponse.json({
      trained: true,
      lastTrained: model.trainedAt,
      entries: model.totalEntries,
      avgConfidence: model.avgConfidence,
    });
  } catch (error) {
    console.error('Get model status error:', error);
    return NextResponse.json({
      trained: false,
      lastTrained: '',
      entries: 0,
      avgConfidence: 0,
    });
  }
}
