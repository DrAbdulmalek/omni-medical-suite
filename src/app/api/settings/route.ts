import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET() {
  try {
    let settings = await db.appSettings.findUnique({ where: { id: 'main' } });

    if (!settings) {
      settings = await db.appSettings.create({
        data: {
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
    }

    return NextResponse.json({ settings });
  } catch (error) {
    console.error('Get settings error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { pageThreshold, grayThreshold, autoSave, autoDeskew, autoCrop, padding, minConfidence } = body;

    const settings = await db.appSettings.upsert({
      where: { id: 'main' },
      update: {
        pageThreshold: pageThreshold ?? 200,
        grayThreshold: grayThreshold ?? 230,
        autoSave: autoSave ?? true,
        autoDeskew: autoDeskew ?? true,
        autoCrop: autoCrop ?? true,
        padding: padding ?? 10,
        minConfidence: minConfidence ?? 0.85,
      },
      create: {
        id: 'main',
        pageThreshold: pageThreshold ?? 200,
        grayThreshold: grayThreshold ?? 230,
        autoSave: autoSave ?? true,
        autoDeskew: autoDeskew ?? true,
        autoCrop: autoCrop ?? true,
        padding: padding ?? 10,
        minConfidence: minConfidence ?? 0.85,
      }
    });

    return NextResponse.json({ success: true, settings });
  } catch (error) {
    console.error('Update settings error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
