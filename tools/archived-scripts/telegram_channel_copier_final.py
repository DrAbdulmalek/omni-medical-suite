#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Channel Archive Copier - نسخ آلي لجميع الملفات من قناة عامة إلى قناة خاصة
تم تخصيصه لقناة: dr_zaky_ortho → قناتك الخاصة
"""

import os
import time
import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# =================== إعداداتك ===================
API_ID = 29863100
API_HASH = 'e89ae7171d2872c86b1e9247ef333e2b'

# معرف القناة المصدر (العامة)
SOURCE_CHANNEL = '@dr_zaky_ortho'

# معرف القناة الهدف (خاصتك) - المعرف الصحيح: 490380746
# للقنوات الخاصة نضيف بادئة -100
TARGET_CHANNEL = -100490380746

# تأخير بين كل رسالة (بالثواني) - ابدأ بـ 3-5 ثوانٍ
DELAY = 3

# هل تريد نقل الرسائل النصية أيضاً؟
COPY_TEXT = True

# هل تريد نقل الملفات والصور والفيديوهات؟
COPY_MEDIA = True

# هل تريد نقل فقط رسائل تحتوي على ملفات؟
FILES_ONLY = False

# عدد الرسائل للنقل (0 = كل الرسائل)
LIMIT = 0

# =================================================

SESSION_NAME = 'channel_copier_session'

async def copy_channel_archive():
    """الدالة الرئيسية لنسخ الأرشيف"""

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    print("✅ تم الاتصال بحساب تليجرام")

    # التحقق من القناة المصدر
    try:
        source = await client.get_entity(SOURCE_CHANNEL)
        print(f"📥 القناة المصدر: {source.title} (ID: {source.id})")
    except Exception as e:
        print(f"❌ خطأ في الوصول للقناة المصدر: {e}")
        await client.disconnect()
        return

    # التحقق من القناة الهدف
    try:
        target = await client.get_entity(TARGET_CHANNEL)
        print(f"📤 القناة الهدف: {target.title} (ID: {target.id})")
    except Exception as e:
        print(f"❌ خطأ في الوصول للقناة الهدف: {e}")
        print("💡 تأكد أنك عضو في القناة الخاصة وأن المعرف صحيح")
        await client.disconnect()
        return

    # جلب جميع الرسائل
    print("🔍 جاري قراءة الرسائل من القناة المصدر...")
    messages = []
    async for message in client.iter_messages(source, limit=LIMIT if LIMIT > 0 else None):
        if FILES_ONLY and not message.media:
            continue
        messages.append(message)

    total = len(messages)
    print(f"📊 إجمالي الرسائل للنقل: {total}")

    if total == 0:
        print("⚠️ لا توجد رسائل للنقل")
        await client.disconnect()
        return

    # بدء النقل من الأقدم للأحدث
    copied = 0
    failed = 0
    skipped = 0

    for i, msg in enumerate(reversed(messages), 1):
        try:
            has_media = bool(msg.media)
            has_text = bool(msg.message)

            should_copy = False
            if has_media and COPY_MEDIA:
                should_copy = True
            elif has_text and COPY_TEXT and not has_media:
                should_copy = True

            if not should_copy:
                skipped += 1
                continue

            # نسخ الرسالة كرسالة جديدة (بدون علامة "تم التوجيه")
            await client.send_message(
                target,
                message=msg.message if has_text else None,
                file=msg.media if has_media else None,
                buttons=msg.buttons if hasattr(msg, 'buttons') else None,
                silent=True
            )

            copied += 1
            preview = msg.message[:40] if msg.message else '(ملف/صورة/فيديو)'
            print(f"✅ [{i}/{total}] تم النسخ: {msg.id} - {preview}")

            if i < total:
                await asyncio.sleep(DELAY)

        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"⏳ تليجرام طلب الانتظار {wait_time} ثانية...")
            await asyncio.sleep(wait_time)
            try:
                await client.send_message(
                    target,
                    message=msg.message if msg.message else None,
                    file=msg.media if msg.media else None,
                    silent=True
                )
                copied += 1
            except Exception as e2:
                print(f"❌ فشل إعادة المحاولة: {e2}")
                failed += 1

        except Exception as e:
            print(f"❌ [{i}/{total}] فشل النسخ: {msg.id} - {e}")
            failed += 1
            await asyncio.sleep(DELAY)

    print("\n" + "="*50)
    print(f"🎉 تم الانتهاء!")
    print(f"✅ نجح: {copied}")
    print(f"❌ فشل: {failed}")
    print(f"⏭️ تم تخطيه: {skipped}")
    print("="*50)

    await client.disconnect()


if __name__ == '__main__':
    print("🚀 بدء نسخ أرشيف القناة...")
    print(f"📥 من: {SOURCE_CHANNEL}")
    print(f"📤 إلى: قناتك الخاصة (ID: {TARGET_CHANNEL})")
    print(f"⏱️ التأخير بين كل رسالة: {DELAY} ثانية")
    print("-" * 50)

    asyncio.run(copy_channel_archive())
