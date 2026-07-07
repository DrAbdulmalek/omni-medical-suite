import { PrismaClient } from '@prisma/client';
import { NextResponse } from 'next/server';

const db = new PrismaClient();

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { modelId, strategy, config } = body;

    await db.ocrDeployment.updateMany({
      where: { status: 'active' },
      data: { status: 'inactive', rollbackAt: new Date() },
    });
    await db.ocrModel.updateMany({
      where: { isProduction: true },
      data: { isProduction: false },
    });

    const deployment = await db.ocrDeployment.create({
      data: {
        modelId,
        strategy,
        trafficPercent: strategy === 'canary' ? (config?.trafficPercent ?? 10) : 100,
        status: 'active',
        canaryConfig: config ? JSON.stringify(config) : '{}',
      },
    });

    await db.ocrModel.update({
      where: { id: modelId },
      data: { isProduction: true },
    });

    const message =
      strategy === 'canary'
        ? `بدء نشر تدريجي بنسبة ${config?.trafficPercent ?? 10}%`
        : strategy === 'bluegreen'
        ? 'تم النشر بنجاح (Blue-Green)'
        : 'تم النشر المباشر بنجاح';

    return NextResponse.json({ success: true, deployment, message });
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}

export async function GET() {
  try {
    const deployments = await db.ocrDeployment.findMany({
      where: { status: 'active' },
      include: { model: true },
      orderBy: { startedAt: 'desc' },
      take: 10,
    });
    return NextResponse.json(deployments);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
