import asyncio

import streamlit as st
from telethon import TelegramClient
from telethon.errors import FloodWaitError

st.set_page_config(
    page_title="Telegram Channel Copier",
    page_icon="📤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0088cc;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stProgress > div > div > div > div {
        background-color: #0088cc;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        color: #721c24;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📤 Telegram Channel Copier</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">نسخ جميع الملفات والرسائل من قناة عامة إلى قناتك الخاصة</div>', unsafe_allow_html=True)

# Session state
if 'copier_running' not in st.session_state:
    st.session_state.copier_running = False
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'status' not in st.session_state:
    st.session_state.status = ""
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []

# Sidebar for configuration
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")
    st.markdown("---")

    # API Credentials
    st.markdown("### 🔐 بيانات API")
    api_id = st.text_input("API ID", value="29863100", type="password")
    api_hash = st.text_input("API Hash", value="e89ae7171d2872c86b1e9247ef333e2b", type="password")

    st.markdown("---")

    # Channel Settings
    st.markdown("### 📡 القنوات")
    source_channel = st.text_input("القناة المصدر (مثال: @channel_name)", value="@dr_zaky_ortho")
    target_channel = st.text_input("القناة الهدف (معرف رقمي)", value="-100490380746")

    st.markdown("---")

    # Copy Options
    st.markdown("### 📋 خيارات النسخ")
    copy_text = st.checkbox("نسخ الرسائل النصية", value=True)
    copy_media = st.checkbox("نسخ الملفات والصور والفيديوهات", value=True)
    files_only = st.checkbox("ملفات فقط (تجاهل النصوص)", value=False)

    delay = st.slider("التأخير بين الرسائل (ثواني)", 1, 10, 3)
    limit = st.number_input("عدد الرسائل (0 = الكل)", min_value=0, max_value=10000, value=0)

    st.markdown("---")
    st.markdown("### ⚠️ تحذيرات")
    st.info("""
    - تأكد من صلاحيات النشر في القناة الهدف
    - زيادة التأخير للقنوات الكبيرة
    - لا تشارك بيانات API مع أحد
    """)

# Main area
st.markdown("---")

# Status area
cols = st.columns(3)
with cols[0]:
    st.metric("📊 الرسائل", st.session_state.progress)
with cols[1]:
    st.metric("✅ نجح", st.session_state.get('copied', 0))
with cols[2]:
    st.metric("❌ فشل", st.session_state.get('failed', 0))

# Progress bar
progress_bar = st.progress(0)

# Status message
if st.session_state.status:
    if "نجح" in st.session_state.status or "تم" in st.session_state.status:
        st.markdown(f'<div class="success-box">{st.session_state.status}</div>', unsafe_allow_html=True)
    elif "فشل" in st.session_state.status or "خطأ" in st.session_state.status:
        st.markdown(f'<div class="error-box">{st.session_state.status}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="info-box">{st.session_state.status}</div>', unsafe_allow_html=True)

# Log area
st.markdown("### 📋 سجل العمليات")
log_container = st.container()
with log_container:
    for msg in st.session_state.log_messages[-20:]:
        st.text(msg)

# Control buttons
col1, col2 = st.columns(2)

async def run_copier(api_id, api_hash, source, target, delay, limit, copy_text, copy_media, files_only):
    """Run the copier"""
    try:
        st.session_state.copier_running = True
        st.session_state.status = "🔌 جاري الاتصال بتليجرام..."

        client = TelegramClient('session', api_id, api_hash)
        await client.start()

        st.session_state.log_messages.append("✅ تم الاتصال بحساب تليجرام")

        # Get entities
        try:
            source_entity = await client.get_entity(source)
            st.session_state.log_messages.append(f"📥 المصدر: {source_entity.title}")
        except Exception as e:
            st.session_state.status = f"❌ خطأ في الوصول للقناة المصدر: {e}"
            st.session_state.copier_running = False
            await client.disconnect()
            return

        try:
            target_entity = await client.get_entity(int(target))
            st.session_state.log_messages.append(f"📤 الهدف: {target_entity.title}")
        except Exception as e:
            st.session_state.status = f"❌ خطأ في الوصول للقناة الهدف: {e}"
            st.session_state.copier_running = False
            await client.disconnect()
            return

        # Fetch messages
        st.session_state.status = "🔍 جاري قراءة الرسائل..."
        messages = []
        async for message in client.iter_messages(source_entity, limit=limit if limit > 0 else None):
            if files_only and not message.media:
                continue
            messages.append(message)

        total = len(messages)
        st.session_state.log_messages.append(f"📊 إجمالي الرسائل: {total}")

        if total == 0:
            st.session_state.status = "⚠️ لا توجد رسائل للنقل"
            st.session_state.copier_running = False
            await client.disconnect()
            return

        # Copy messages
        copied = 0
        failed = 0
        skipped = 0

        for i, msg in enumerate(reversed(messages), 1):
            if not st.session_state.copier_running:
                break

            try:
                has_media = bool(msg.media)
                has_text = bool(msg.message)

                should_copy = False
                if (has_media and copy_media) or (has_text and copy_text and not has_media):
                    should_copy = True

                if not should_copy:
                    skipped += 1
                    continue

                await client.send_message(
                    target_entity,
                    message=msg.message if has_text else None,
                    file=msg.media if has_media else None,
                    silent=True
                )

                copied += 1
                st.session_state.progress = int((i / total) * 100)
                st.session_state.copied = copied
                st.session_state.failed = failed

                preview = msg.message[:30] if msg.message else '(ملف)'
                st.session_state.log_messages.append(f"✅ [{i}/{total}] {preview}")

                await asyncio.sleep(delay)

            except FloodWaitError as e:
                st.session_state.log_messages.append(f"⏳ انتظار {e.seconds} ثانية...")
                await asyncio.sleep(e.seconds)
                try:
                    await client.send_message(
                        target_entity,
                        message=msg.message if msg.message else None,
                        file=msg.media if msg.media else None,
                        silent=True
                    )
                    copied += 1
                except Exception as e2:
                    failed += 1
                    st.session_state.log_messages.append(f"❌ فشل: {e2}")

            except Exception as e:
                failed += 1
                st.session_state.log_messages.append(f"❌ خطأ: {e}")
                await asyncio.sleep(delay)

        st.session_state.status = f"🎉 تم الانتهاء! ✅ {copied} | ❌ {failed} | ⏭️ {skipped}"
        st.session_state.copier_running = False
        await client.disconnect()

    except Exception as e:
        st.session_state.status = f"❌ خطأ عام: {e}"
        st.session_state.copier_running = False

with col1:
    if st.button("🚀 بدء النسخ", type="primary", disabled=st.session_state.copier_running):
        st.session_state.log_messages = []
        st.session_state.progress = 0
        st.session_state.copied = 0
        st.session_state.failed = 0

        asyncio.run(run_copier(
            int(api_id), api_hash, source_channel, target_channel,
            delay, limit, copy_text, copy_media, files_only
        ))
        st.rerun()

with col2:
    if st.button("⏹️ إيقاف", type="secondary", disabled=not st.session_state.copier_running):
        st.session_state.copier_running = False
        st.session_state.status = "⏹️ تم الإيقاف"
        st.rerun()

st.markdown("---")
st.markdown("<div style='text-align: center; color: #666;'>Made with ❤️ for Telegram users</div>", unsafe_allow_html=True)
