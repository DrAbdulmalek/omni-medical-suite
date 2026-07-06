import { PrismaClient } from '@prisma/client';
import { NextResponse } from 'next/server';

const db = new PrismaClient();

export async function GET() {
  try {
    const models = await db.ocrModel.findMany({
      orderBy: { createdAt: 'desc' },
    });
    return NextResponse.json(models);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
