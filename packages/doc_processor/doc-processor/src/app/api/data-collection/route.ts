import { PrismaClient } from '@prisma/client';
import { NextResponse } from 'next/server';

const db = new PrismaClient();

export async function GET() {
  try {
    let stats = await db.dataCollectionStats.findUnique({ where: { id: 'main' } });
    if (!stats) {
      stats = await db.dataCollectionStats.create({ data: { id: 'main' } });
    }
    return NextResponse.json(stats);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { action } = body;

    if (action === 'start') {
      let stats = await db.dataCollectionStats.findUnique({ where: { id: 'main' } });
      if (!stats) {
        stats = await db.dataCollectionStats.create({ data: { id: 'main' } });
      }
      await db.dataCollectionStats.update({
        where: { id: 'main' },
        data: { phase: 'collecting', progress: 0 },
      });
      return NextResponse.json({ success: true, message: 'بدأ التجميع' });
    }

    if (action === 'update') {
      const {
        totalCollected,
        realCount,
        syntheticCount,
        academicCount,
        highQuality,
        mediumQuality,
        lowQuality,
        progress,
        phase,
      } = body;
      await db.dataCollectionStats.update({
        where: { id: 'main' },
        data: {
          totalCollected,
          realCount,
          syntheticCount,
          academicCount,
          highQuality,
          mediumQuality,
          lowQuality,
          progress,
          phase,
        },
      });
      return NextResponse.json({ success: true });
    }

    return NextResponse.json({ success: false, message: 'إجراء غير معروف' });
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
