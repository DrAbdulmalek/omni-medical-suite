import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import fs from 'fs';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: 'لا يوجد ملف' }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const content = Buffer.from(bytes).toString('utf-8');
    const lines = content.trim().split('\n');

    let imported = 0;

    for (const line of lines) {
      try {
        const data = JSON.parse(line);
        if (!data.image_name) continue;

        // Check if already exists
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

        imported++;
      } catch {
        // Skip invalid lines
      }
    }

    return NextResponse.json({ success: true, imported });
  } catch (error) {
    console.error('Import training error:', error);
    return NextResponse.json({ error: 'حدث خطأ أثناء الاستيراد' }, { status: 500 });
  }
}
