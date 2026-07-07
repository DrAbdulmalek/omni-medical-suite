import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const ocrText = formData.get('ocr_text') as string | null;

    if (!file && !ocrText) {
      return NextResponse.json({ error: 'No file or OCR text provided' }, { status: 400 });
    }

    const pythonApiUrl = process.env.PYTHON_CORE_URL || 'http://localhost:8000';

    try {
      const pythonFormData = new FormData();
      if (file) pythonFormData.append('file', file);
      if (ocrText) pythonFormData.append('ocr_text', ocrText);

      const res = await fetch(`${pythonApiUrl}/mistral/classify`, {
        method: 'POST',
        body: pythonFormData,
      });

      if (res.ok) {
        const data = await res.json();
        return NextResponse.json(data);
      }
    } catch {
      // Python core not available
    }

    return NextResponse.json({
      available: false,
      error: 'Python Core API not available. Start: cd packages/core && python api_server.py',
    });
  } catch (error) {
    console.error('Mistral classify error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
