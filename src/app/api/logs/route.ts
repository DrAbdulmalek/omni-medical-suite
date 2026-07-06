import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const action = searchParams.get('action');

    const where = action && action !== 'all' ? { action } : {};

    const logs = await db.processingLog.findMany({
      where,
      orderBy: { timestamp: 'desc' },
      take: 200,
    });

    const formatted = logs.map(l => ({
      id: l.id,
      imageName: l.imageName,
      action: l.action,
      details: l.details,
      quality: l.quality,
      timestamp: l.timestamp.toISOString(),
    }));

    return NextResponse.json({ logs: formatted });
  } catch (error) {
    console.error('Get logs error:', error);
    return NextResponse.json({ error: 'حدث خطأ' }, { status: 500 });
  }
}
