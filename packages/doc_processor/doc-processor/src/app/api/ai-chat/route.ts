import { NextResponse } from 'next/server';
import ZAI from 'z-ai-web-dev-sdk';

const systemPrompt = `أنت مساعد ذكي متخصص في معالجة صور المستندات الطبية.
تتحدث العربية. تساعد المستخدم في:
- ضبط إعدادات القص والمعالجة
- تحليل مشاكل جودة الصور
- اقتراح أفضل إعدادات للمعالجة
- شرح الخوارزميات المستخدمة (Scan Tailor, Briss, Unpaper)
- تقسيم الصفحات المزدوجة
- كشف وتصحيح الميلان
- إزالة الحدود الرمادية
- تقييم جودة الصور المعالجة

مهم جداً: عندما يطلب المستخدم اقتراح إعدادات، أو عندما تحلل صورة وتقترح إعدادات معالجة مثالية، يجب عليك تضمين الإعدادات المقترحة بتنسيق خاص في نهاية ردك بالشكل التالي:

[SETTINGS]
{"pageThreshold": 220, "grayThreshold": 210, "padding": 15}
[/SETTINGS]

الإعدادات المتاحة هي:
- pageThreshold: عتبة الصفحة (150-250)
- grayThreshold: عتبة الرمادي (200-250)
- padding: الحشوة بالبكسل (0-50)
- minConfidence: الحد الأدنى للثقة (0.5-1.0)

إذا كنت لا تقترح تغييرات في الإعدادات، لا تقم بتضمين هذا الكتلة. قم بتضمينها فقط عندما يكون لديك اقتراحات محددة للإعدادات.`;

export async function POST(request: Request) {
  try {
    const { messages } = await request.json();

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json(
        { reply: 'عذراً، لم أتمكن من فهم رسالتك. يرجى المحاولة مرة أخرى.' },
        { status: 400 }
      );
    }

    const zai = await ZAI.create();

    const formattedMessages = [
      { role: 'assistant' as const, content: systemPrompt },
      ...messages.map((msg: { role: string; content: string }) => ({
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
      })),
    ];

    const completion = await zai.chat.completions.create({
      messages: formattedMessages,
      thinking: { type: 'disabled' },
    });

    const reply =
      completion.choices[0]?.message?.content ||
      'عذراً، لم أتمكن من معالجة طلبك. يرجى المحاولة مرة أخرى.';

    // Parse settings from the response
    let parsedSettings: {
      pageThreshold?: number;
      grayThreshold?: number;
      padding?: number;
      minConfidence?: number;
    } | null = null;

    const settingsMatch = reply.match(/\[SETTINGS\]\s*([\s\S]*?)\s*\[\/SETTINGS\]/);
    if (settingsMatch) {
      try {
        const raw = settingsMatch[1].trim();
        const parsed = JSON.parse(raw);
        parsedSettings = {};

        if (typeof parsed.pageThreshold === 'number') {
          parsedSettings.pageThreshold = Math.max(150, Math.min(250, parsed.pageThreshold));
        }
        if (typeof parsed.grayThreshold === 'number') {
          parsedSettings.grayThreshold = Math.max(200, Math.min(250, parsed.grayThreshold));
        }
        if (typeof parsed.padding === 'number') {
          parsedSettings.padding = Math.max(0, Math.min(50, parsed.padding));
        }
        if (typeof parsed.minConfidence === 'number') {
          parsedSettings.minConfidence = Math.max(0.5, Math.min(1.0, parsed.minConfidence));
        }
      } catch {
        // Settings JSON parse failed, ignore
      }
    }

    // Clean the reply: remove the [SETTINGS] block from displayed text
    const cleanReply = reply.replace(/\[SETTINGS\][\s\S]*?\[\/SETTINGS\]/g, '').trim();

    return NextResponse.json({
      reply: cleanReply,
      parsedSettings,
    });
  } catch (error) {
    console.error('AI Chat error:', error);
    return NextResponse.json(
      { reply: 'عذراً، حدث خطأ في الاتصال بالمساعد الذكي. يرجى المحاولة مرة أخرى لاحقاً.' },
      { status: 500 }
    );
  }
}
