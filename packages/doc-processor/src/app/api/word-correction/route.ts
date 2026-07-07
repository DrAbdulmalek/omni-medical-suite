import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, correctedText, status } = body;

    if (!id) {
      return NextResponse.json(
        { error: 'Missing required field: id' },
        { status: 400 }
      );
    }

    // Update the training word
    const updated = await db.trainingWord.update({
      where: { id },
      data: {
        correctedText: correctedText || '',
        status: status || (correctedText ? 'corrected' : 'pending'),
      },
    });

    return NextResponse.json({
      success: true,
      word: updated,
    });
  } catch (error) {
    console.error('Word correction error:', error);
    return NextResponse.json(
      { error: 'Failed to update word correction' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const words = await db.trainingWord.findMany({
      orderBy: [
        { sourcePage: 'asc' },
        { lineIndex: 'asc' },
        { wordIndex: 'asc' },
      ],
    });

    return NextResponse.json({ words });
  } catch (error) {
    console.error('Get words error:', error);
    return NextResponse.json(
      { error: 'Failed to get training words' },
      { status: 500 }
    );
  }
}
