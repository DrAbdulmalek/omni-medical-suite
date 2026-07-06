import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    // Forward to Python Core API if available, otherwise use placeholder
    const pythonApiUrl = process.env.PYTHON_CORE_URL || 'http://localhost:8000';

    try {
      const pythonFormData = new FormData();
      pythonFormData.append('file', file);

      const res = await fetch(`${pythonApiUrl}/mistral/ocr`, {
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

    // Fallback: Return placeholder response
    return NextResponse.json({
      available: false,
      error: 'Python Core API not available. Start the Python server: cd packages/core && python api_server.py',
      hint: 'Set PYTHON_CORE_URL environment variable if running on a different port.',
    });
  } catch (error) {
    console.error('Mistral OCR error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
