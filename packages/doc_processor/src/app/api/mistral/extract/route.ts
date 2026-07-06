import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;
    const docType = formData.get('doc_type') as string || 'unknown';
    const patientId = formData.get('patient_id') as string || 'unknown';

    if (!file) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    const pythonApiUrl = process.env.PYTHON_CORE_URL || 'http://localhost:8000';

    try {
      const pythonFormData = new FormData();
      pythonFormData.append('file', file);
      pythonFormData.append('doc_type', docType);
      pythonFormData.append('patient_id', patientId);

      const res = await fetch(`${pythonApiUrl}/mistral/extract`, {
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
    console.error('Mistral extract error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
