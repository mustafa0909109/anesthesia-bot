import io
import os
import threading
from flask import Flask
from google import genai
from google.genai import types
from pypdf import PdfReader
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ================= خادم ويب وهمي لتفعيل الخطة المجانية =================
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot is running online 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ================= الإعدادات والمفاتيح =================
TELEGRAM_BOT_TOKEN = "7973450118:AAEvn8ub7AvSE_Swbl9mHn4vch4TmGLwXQE"
GEMINI_API_KEY = "AQ.Ab8RN6L0UFIyPvdK3Kg0WlFj4qHBIk7II2IeBz57s0D91asZPg"

ai_client = genai.Client(api_key=GEMINI_API_KEY)

FAST_FREE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash",
]

SYSTEM_INSTRUCTION = """
أنت 'مساعد تقنيات التخدير والعناية المركزة الذكي'.
تعليمات صارمة:
1. ممنوع نهائياً كتابة أي مقدمات أو تحيات أو جمل تعريفية.
2. ادخل في صلب الجواب أو الأسئلة أو التلخيص مباشرة من أول كلمة.
3. التزم بلغة الإخراج المحددة (إنجليزي فقط، أو إنجليزي متبوعاً بترجمة وشرح عربي).
4. استخدم التنسيق الأكاديمي المرتب بالنقاط والعناوين الواضحة.
"""

uploaded_docs = {}

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("📑 تلخيص الملزمة"),
            KeyboardButton("📝 أسئلة MCQ (اختيارات)"),
        ],
        [
            KeyboardButton("✍️ أسئلة Short Answer"),
            KeyboardButton("❓ أسئلة شاملة للمحاضرة"),
        ],
        [
            KeyboardButton("🗑 مسح الملزمة الحالية"),
            KeyboardButton("ℹ️ مساعدة"),
        ],
    ],
    resize_keyboard=True,
)

def generate_fast_ai_response(prompt: str) -> str:
    last_error = None
    for model_name in FAST_FREE_MODELS:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                ),
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = e
            continue
    raise last_error

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "مرحباً بك في **مساعد تقنيات التخدير والعناية المركزة** 🩺💉\n\n"
        "1️⃣ ارفع أي ملزمة بصيغة PDF.\n"
        "2️⃣ اضغط على أي خيار بالأسفل (MCQ، تلخيص، Short Answer).\n"
        "3️⃣ حدد لغة الجواب وسأجيبك فوراً وبشكل مباشر.\n\n"
        "ــــــــــــــــــــــــــــــــــــــــ\n"
        "✨ **تمت البرمجة والتطوير من قبل السيد**"
    )
    await update.message.reply_text(
        welcome_text, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text(
            "⚠️ يرجى رفع ملفات بصيغة PDF فقط للملازم الطبية.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    msg = await update.message.reply_text("⏳ جاري قراءة الملزمة وتحليلها...")
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

        chat_id = update.effective_chat.id
        uploaded_docs[chat_id] = extracted_text[:45000]

        await msg.edit_text(
            f"✅ تم تحميل الملزمة بنجاح ({len(reader.pages)} صفحة)!\n\n"
            "اضغط الآن على المربع الذي تريده لاختيار لغة الجواب.",
        )
    except Exception as e:
        await msg.edit_text(f"❌ تعذر قراءة الملف: {e}")

def get_language_inline_keyboard(task_type: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🇬🇧 إنجليزي فقط (English)",
                    callback_data=f"{task_type}:en",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🌐 إنجليزي + عربي (Bilingual)",
                    callback_data=f"{task_type}:ar_en",
                ),
            ],
        ]
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    chat_id = update.effective_chat.id
    has_pdf = chat_id in uploaded_docs

    if user_query == "🗑 مسح الملزمة الحالية":
        if has_pdf:
            del uploaded_docs[chat_id]
            await update.message.reply_text(
                "🧹 تم مسح الملزمة من الذاكرة بنجاح.",
                reply_markup=MAIN_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                "لا توجد ملزمة مخزنة حالياً لمسحها.", reply_markup=MAIN_KEYBOARD
            )
        return

    if user_query == "ℹ️ مساعدة":
        help_msg = (
            "📌 **دليل الاستخدام:**\n\n"
            "1. ارفع ملف المحاضرة بصيغة PDF.\n"
            "2. اضغط على خيار (تلخيص / MCQ / Short Answer / أسئلة شاملة).\n"
            "3. اختر لغة الجواب المطلوبة لتظهر لك النتيجة فوراً.\n\n"
            "ــــــــــــــــــــــــــــــــــــــــ\n"
            "👨‍💻 **تمت البرمجة والتطوير من قبل السيد**"
        )
        await update.message.reply_text(
            help_msg, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown"
        )
        return

    if user_query in [
        "📑 تلخيص الملزمة",
        "📝 أسئلة MCQ (اختيارات)",
        "✍️ أسئلة Short Answer",
        "❓ أسئلة شاملة للمحاضرة",
    ]:
        if not has_pdf:
            await update.message.reply_text(
                "⚠️ يرجى رفع ملزمة PDF أولاً!", reply_markup=MAIN_KEYBOARD
            )
            return

        task_map = {
            "📑 تلخيص الملزمة": "summary",
            "📝 أسئلة MCQ (اختيارات)": "mcq",
            "✍️ أسئلة Short Answer": "short",
            "❓ أسئلة شاملة للمحاضرة": "comprehensive",
        }
        task_code = task_map[user_query]
        await update.message.reply_text(
            f"🎯 اختر لغة الجواب لـ ({user_query}):",
            reply_markup=get_language_inline_keyboard(task_code),
        )
        return

    context_text = uploaded_docs.get(chat_id, "")
    if context_text:
        prompt = f"الملزمة المرفوعة:\n{context_text}\n\nالسؤال: {user_query}\n(ادخل في الإجابة مباشرة دون أي مقدمات ترحيبية)"
    else:
        prompt = f"السؤال: {user_query}\n(ادخل في الإجابة مباشرة دون أي مقدمات ترحيبية)"

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        reply_text = generate_fast_ai_response(prompt)
        await update.message.reply_text(reply_text, reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        await update.message.reply_text(
            f"❌ حدث خطأ، يرجى المحاولة ثانية: {e}", reply_markup=MAIN_KEYBOARD
        )

async def handle_language_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    task_code, lang_choice = query.data.split(":")
    chat_id = update.effective_chat.id
    context_text = uploaded_docs.get(chat_id, "")

    if not context_text:
        await query.edit_message_text(
            "⚠️ تم مسح الملزمة أو انتهت الجلسة، يرجى رفع الملف مجدداً."
        )
        return

    if lang_choice == "en":
        lang_instruction = "المطلوب: كامل الإخراج باللغة الإنجليزية الطبية فقط (English Only) بدون مقدمات أو ترحيب."
        chosen_label = "🇬🇧 إنجليزي فقط"
    else:
        lang_instruction = "المطلوب: اكتب كل سؤال وفقرة بالإنجليزية الطبية ومباشرة تحتها الترجمة والشرح العربي، بدون أي مقدمات أو ترحيب."
        chosen_label = "🌐 إنجليزي + عربي"

    await query.edit_message_text(f"⏳ جاري التوليد بـ ({chosen_label})...")

    if task_code == "summary":
        task_prompt = "قم بتلخيص هذه المحاضرة بنقاط مباشرة ومركزة على الأدوية والجرعات والإجراءات المهمة."
    elif task_code == "mcq":
        task_prompt = "اكتب 5 أسئلة MCQ متعددة الخيارات (A, B, C, D) حول محتوى هذه الملزمة، وفي النهاية اذكر مفتاح الحل والتفسير الطبي مباشرة."
    elif task_code == "short":
        task_prompt = "اكتب 5 أسئلة Short Answer مقالية قصيرة ومباشرة مع إجاباتها النموذجية المختصرة."
    else:
        task_prompt = "قم بإنشاء بنك أسئلة شامل يغطي كل تفاصيل وفقرات الملزمة مع الحلول مباشرة."

    full_prompt = f"الملزمة:\n{context_text}\n\n{task_prompt}\n\n{lang_instruction}\n(تذكير: ابدأ بالمحتوى فوراً دون أي تحية أو مقدمة)."

    try:
        reply_text = generate_fast_ai_response(full_prompt)
        await context.bot.send_message(
            chat_id=chat_id, text=reply_text, reply_markup=MAIN_KEYBOARD
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ حدث خطأ أثناء المعالجة: {e}",
            reply_markup=MAIN_KEYBOARD,
        )

def main():
    # تشغيل خادم الويب في مسار مستقل ليتعرف Render على الخدمة المجانية
    threading.Thread(target=run_web, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_language_choice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )

    print("🚀 البوت شغال ومجهز للسيرفر السحابي المجاني...")
    app.run_polling()

if __name__ == "__main__":
    main()