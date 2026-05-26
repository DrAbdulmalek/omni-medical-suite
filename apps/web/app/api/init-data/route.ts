import { NextResponse } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';

export async function POST() {
  try {
    let trainingImported = 0;
    let logImported = 0;

    // Import training data from JSONL
    const trainingPath = '/home/z/my-project/upload/medical_doc_training.jsonl';
    if (fs.existsSync(trainingPath)) {
      const content = fs.readFileSync(trainingPath, 'utf-8');
      const lines = content.trim().split('\n');

      for (const line of lines) {
        try {
          const data = JSON.parse(line);
          if (!data.image_name) continue;

          const existing = await db.trainingRecord.findFirst({
            where: { imageName: data.image_name }
          });

          if (existing) continue;

          await db.trainingRecord.create({
            data: {
              imageName: data.image_name,
              features: JSON.stringify(data.features || {}),
              initialParams: JSON.stringify(data.initial_params || {}),
              finalParams: JSON.stringify(data.final_params || {}),
              operations: JSON.stringify(data.operations || []),
              quality: JSON.stringify(data.quality || {}),
              confidence: data.confidence || 0,
            }
          });

          trainingImported++;
        } catch {
          // Skip invalid lines
        }
      }
    }

    // Import processing log
    const logPath = '/home/z/my-project/upload/processing_log.txt';
    if (fs.existsSync(logPath)) {
      const content = fs.readFileSync(logPath, 'utf-8');
      const lines = content.trim().split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;

        try {
          // Parse log line format: [HH:MM:SS] emoji action
          const match = line.match(/\[(\d{2}:\d{2}:\d{2})\]\s*(.*)/);
          if (!match) continue;

          const timeStr = match[1];
          const rest = match[2];

          // Determine action type from emoji
          let action = 'معلومة';
          let details = rest;

          if (rest.includes('📥') || rest.includes('تم تحميل')) {
            action = 'رفع';
          } else if (rest.includes('💾') || rest.includes('حفظ')) {
            action = 'حفظ';
          } else if (rest.includes('✂️') || rest.includes('قص ذكي')) {
            action = 'قص ذكي';
          } else if (rest.includes('📐') || rest.includes('ميلان')) {
            action = 'ميلان';
          } else if (rest.includes('⏭️') || rest.includes('تخطي')) {
            action = 'تخطي';
          } else if (rest.includes('🖼️') || rest.includes('إزالة رمادي')) {
            action = 'إزالة رمادي';
          } else if (rest.includes('🧠') || rest.includes('تنبؤ')) {
            action = 'تنبؤ';
          }

          // Extract image name
          const imageMatch = rest.match(/(\d+\.jpg|\d+\.png)/);
          const imageName = imageMatch ? imageMatch[1] : '';

          // Extract quality
          const qualityMatch = rest.match(/جودة:\s*(\d+)/);
          const quality = qualityMatch ? parseInt(qualityMatch[1]) : 0;

          // Create a unique key to avoid duplicates
          const uniqueKey = `${timeStr}-${imageName}-${action}`;
          const existing = await db.processingLog.findFirst({
            where: {
              imageName: imageName || 'unknown',
              action,
              details,
            }
          });

          if (!existing) {
            await db.processingLog.create({
              data: {
                imageName: imageName || 'unknown',
                action,
                details: rest,
                quality,
                timestamp: new Date(`2026-05-24T${timeStr}`),
              }
            });

            logImported++;
          }
        } catch {
          // Skip invalid lines
        }
      }
    }

    // Ensure default settings exist
    await db.appSettings.upsert({
      where: { id: 'main' },
      update: {},
      create: {
        id: 'main',
        pageThreshold: 200,
        grayThreshold: 230,
        autoSave: true,
        autoDeskew: true,
        autoCrop: true,
        padding: 10,
        minConfidence: 0.85,
      }
    });

    return NextResponse.json({
      success: true,
      trainingImported,
      logImported,
    });
  } catch (error) {
    console.error('Init data error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
