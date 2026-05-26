import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';
import { db } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '50');
    const includeImage = searchParams.get('includeImage') === 'true';

    const where: Record<string, unknown> = {};
    if (status && status !== 'all') {
      where.status = status;
    }

    const total = await db.trainingWord.count({ where });
    const words = await db.trainingWord.findMany({
      where,
      orderBy: [
        { sourcePage: 'asc' },
        { lineIndex: 'asc' },
        { wordIndex: 'asc' },
      ],
      skip: (page - 1) * limit,
      take: limit,
    });

    // Optionally include base64 image data
    const wordsWithImages = includeImage
      ? await Promise.all(
          words.map(async (word) => {
            let imageDataUrl: string | null = null;
            if (word.imagePath) {
              try {
                const imgBuffer = await readFile(word.imagePath);
                imageDataUrl = `data:image/png;base64,${imgBuffer.toString('base64')}`;
              } catch {
                // Image not found
              }
            }
            return {
              ...word,
              imageDataUrl,
            };
          })
        )
      : words;

    // Stats
    const pendingCount = await db.trainingWord.count({
      where: { status: 'pending' },
    });
    const correctedCount = await db.trainingWord.count({
      where: { status: 'corrected' },
    });
    const skippedCount = await db.trainingWord.count({
      where: { status: 'skipped' },
    });

    return NextResponse.json({
      words: wordsWithImages,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
      stats: {
        total,
        pending: pendingCount,
        corrected: correctedCount,
        skipped: skippedCount,
      },
    });
  } catch (error) {
    console.error('Get training words error:', error);
    return NextResponse.json(
      { error: 'Failed to get training words' },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const deleteAll = searchParams.get('all') === 'true';

    if (deleteAll) {
      await db.trainingWord.deleteMany({});
      return NextResponse.json({ success: true, message: 'تم حذف جميع بيانات التدريب' });
    }

    return NextResponse.json(
      { error: 'Specify ?all=true to delete all data' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Delete training words error:', error);
    return NextResponse.json(
      { error: 'Failed to delete training words' },
      { status: 500 }
    );
  }
}
