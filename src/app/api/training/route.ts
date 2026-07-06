import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET() {
  try {
    const records = await db.trainingRecord.findMany({
      orderBy: { createdAt: 'desc' },
      take: 100,
    });

    const formatted = records.map(r => {
      let quality = {};
      try { quality = JSON.parse(r.quality); } catch { /* empty */ }
      return {
        id: r.id,
        imageName: r.imageName,
        confidence: r.confidence,
        operations: JSON.parse(r.operations || '[]'),
        blurBefore: (quality as { blur_before?: number }).blur_before || 0,
        blurAfter: (quality as { blur_after?: number }).blur_after || 0,
        improvement: ((quality as { improvement?: number }).improvement) || ((quality as { blur_after?: number }).blur_after || 0) - ((quality as { blur_before?: number }).blur_before || 0),
        createdAt: r.createdAt.toISOString(),
      };
    });

    return NextResponse.json({ records: formatted });
  } catch (error) {
    console.error('Get training error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
