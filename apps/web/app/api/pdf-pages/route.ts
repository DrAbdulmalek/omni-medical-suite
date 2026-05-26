import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';
import { db } from '@/lib/db';
import { segmentPage } from '@/lib/word-segmentation';
import Tesseract from 'tesseract.js';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { pageIndex, pdfName, imageData } = body;

    if (pageIndex === undefined || !pdfName || !imageData) {
      return NextResponse.json(
        { error: 'Missing required fields: pageIndex, pdfName, imageData' },
        { status: 400 }
      );
    }

    // Decode base64 image
    const base64Data = imageData.replace(/^data:image\/\w+;base64,/, '');
    const imageBuffer = Buffer.from(base64Data, 'base64');

    // Ensure directories exist
    const pagesDir = path.join(process.cwd(), 'uploads', 'pdf-pages');
    const wordsDir = path.join(process.cwd(), 'uploads', 'words');
    await mkdir(pagesDir, { recursive: true });
    await mkdir(wordsDir, { recursive: true });

    // Save page image
    const pageFilename = `${pdfName.replace(/[^a-zA-Z0-9_-]/g, '_')}_page_${pageIndex}.png`;
    const pagePath = path.join(pagesDir, pageFilename);
    await writeFile(pagePath, imageBuffer);

    // Segment the page into words
    const segments = await segmentPage(imageBuffer);

    if (segments.length === 0) {
      return NextResponse.json({
        pageNumber: pageIndex,
        pageImage: pageFilename,
        words: [],
        message: 'لم يتم العثور على كلمات في هذه الصفحة',
      });
    }

    // Run OCR on each word segment
    let worker: Tesseract.Worker | null = null;
    try {
      worker = await Tesseract.createWorker('ara+eng', undefined, {
        logger: () => {},
      });
    } catch {
      // Fallback if worker creation fails
    }

    const words = [];

    for (const segment of segments) {
      let ocrText = '';
      let confidence = 0;

      if (worker && segment.image.length > 0) {
        try {
          const result = await worker.recognize(segment.image);
          ocrText = result.data.text.replace(/\s+/g, ' ').trim();
          confidence = result.data.confidence / 100;
        } catch {
          // OCR failed for this word
        }
      }

      // Save word image
      const wordFilename = `${pdfName.replace(/[^a-zA-Z0-9_-]/g, '_')}_page${pageIndex}_word${segment.wordIndex}.png`;
      const wordPath = path.join(wordsDir, wordFilename);
      if (segment.image.length > 0) {
        await writeFile(wordPath, segment.image);
      }

      // Create database record
      const record = await db.trainingWord.create({
        data: {
          sourcePdf: pdfName,
          sourcePage: pageIndex,
          wordIndex: segment.wordIndex,
          lineIndex: segment.lineIndex,
          originalText: ocrText,
          correctedText: '',
          confidence,
          imagePath: wordPath,
          status: 'pending',
        },
      });

      words.push({
        id: record.id,
        originalText: ocrText,
        confidence: Math.round(confidence * 100) / 100,
        imagePath: wordPath,
        x: segment.x,
        y: segment.y,
        width: segment.width,
        height: segment.height,
        lineIndex: segment.lineIndex,
        wordIndex: segment.wordIndex,
        status: 'pending',
      });
    }

    // Terminate worker
    if (worker) {
      await worker.terminate();
    }

    return NextResponse.json({
      pageNumber: pageIndex,
      pageImage: pageFilename,
      words,
      totalWords: words.length,
    });
  } catch (error) {
    console.error('PDF page processing error:', error);
    return NextResponse.json(
      { error: 'Failed to process PDF page' },
      { status: 500 }
    );
  }
}
