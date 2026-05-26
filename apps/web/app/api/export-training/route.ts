import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir, readFile } from 'fs/promises';
import path from 'path';
import { db } from '@/lib/db';

export async function POST(request: NextRequest) {
  try {
    // Get all corrected training words
    const correctedWords = await db.trainingWord.findMany({
      where: { status: 'corrected' },
      orderBy: [
        { sourcePage: 'asc' },
        { lineIndex: 'asc' },
        { wordIndex: 'asc' },
      ],
    });

    if (correctedWords.length === 0) {
      return NextResponse.json(
        { error: 'لا توجد بيانات تدريب مصححة للتصدير' },
        { status: 400 }
      );
    }

    const exportDir = path.join(process.cwd(), 'training-data');
    await mkdir(exportDir, { recursive: true });

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

    // Build JSONL content
    const jsonlLines: string[] = [];

    for (const word of correctedWords) {
      let imageBase64 = '';
      if (word.imagePath) {
        try {
          const imgBuffer = await readFile(word.imagePath);
          imageBase64 = imgBuffer.toString('base64');
        } catch {
          // Image not found, skip image data
        }
      }

      const record = {
        word_id: word.id,
        corrected_text: word.correctedText,
        original_text: word.originalText,
        image_base64: imageBase64,
        source_pdf: word.sourcePdf,
        source_page: word.sourcePage,
        line_index: word.lineIndex,
        word_index: word.wordIndex,
        confidence: word.confidence,
      };

      jsonlLines.push(JSON.stringify(record));
    }

    // Save JSONL file
    const jsonlFilename = `export_${timestamp}.jsonl`;
    const jsonlPath = path.join(exportDir, jsonlFilename);
    await writeFile(jsonlPath, jsonlLines.join('\n'), 'utf-8');

    // Also save word images as separate PNGs in a subdirectory
    const imagesDir = path.join(exportDir, `images_${timestamp}`);
    await mkdir(imagesDir, { recursive: true });

    for (const word of correctedWords) {
      if (word.imagePath) {
        try {
          const imgBuffer = await readFile(word.imagePath);
          const imgFilename = `${word.id}.png`;
          await writeFile(path.join(imagesDir, imgFilename), imgBuffer);
        } catch {
          // Skip missing images
        }
      }
    }

    // Save a summary JSON
    const summary = {
      exportDate: new Date().toISOString(),
      totalWords: correctedWords.length,
      sourcePdfs: [...new Set(correctedWords.map((w) => w.sourcePdf))],
      avgConfidence:
        correctedWords.reduce((sum, w) => sum + w.confidence, 0) /
        correctedWords.length,
      jsonlFile: jsonlFilename,
      imagesDir: `images_${timestamp}`,
    };

    const summaryPath = path.join(exportDir, `summary_${timestamp}.json`);
    await writeFile(summaryPath, JSON.stringify(summary, null, 2), 'utf-8');

    return NextResponse.json({
      success: true,
      message: `تم تصدير ${correctedWords.length} كلمة`,
      export: {
        jsonlPath,
        summaryPath,
        imagesDir,
        totalWords: correctedWords.length,
        summary,
      },
    });
  } catch (error) {
    console.error('Export training data error:', error);
    return NextResponse.json(
      { error: 'Failed to export training data' },
      { status: 500 }
    );
  }
}
