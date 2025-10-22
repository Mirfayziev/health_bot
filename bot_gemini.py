# -*- coding: utf-8 -*-

import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import openai
from deep_translator import GoogleTranslator
import requests
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API Keys
TELEGRAM_TOKEN = os.getenv('8040309330:AAHvjWpg2dbhzrlbpzoQJc2i33O26Ey97pw')
OPENAI_API_KEY = os.getenv('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')

openai.api_key = OPENAI_API_KEY

# User data storage
user_data = {}

# Supported languages
LANGUAGES = {
    'uz': '🇺🇿 O\'zbekcha',
    'en': '🇬🇧 English',
    'ru': '🇷🇺 Русский',
    'tr': '🇹🇷 Türkçe',
    'ar': '🇸🇦 العربية',
    'zh': '🇨🇳 中文',
    'es': '🇪🇸 Español',
    'fr': '🇫🇷 Français',
    'de': '🇩🇪 Deutsch',
    'ja': '🇯🇵 日本語',
    'ko': '🇰🇷 한국어',
    'hi': '🇮🇳 हिन्दी'
}

# Language codes for deep-translator
LANG_CODES = {
    'uz': 'uz', 'en': 'en', 'ru': 'ru', 'tr': 'tr',
    'ar': 'ar', 'zh': 'zh-CN', 'es': 'es', 'fr': 'fr',
    'de': 'de', 'ja': 'ja', 'ko': 'ko', 'hi': 'hi'
}

def get_main_keyboard():
    """Main menu keyboard"""
    keyboard = [
        [KeyboardButton('🤖 AI Suhbat'), KeyboardButton('🌍 Tarjima')],
        [KeyboardButton('🎤 Ovozli Tarjima'), KeyboardButton('📍 Joylashuv')],
        [KeyboardButton('⚙️ Sozlamalar'), KeyboardButton('ℹ️ Yordam')]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_language_keyboard():
    """Language selection keyboard"""
    keyboard = []
    langs = list(LANGUAGES.items())
    for i in range(0, len(langs), 2):
        row = []
        row.append(InlineKeyboardButton(langs[i][1], callback_data=f'lang_{langs[i][0]}'))
        if i + 1 < len(langs):
            row.append(InlineKeyboardButton(langs[i+1][1], callback_data=f'lang_{langs[i+1][0]}'))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {
            'language': 'uz',
            'target_language': 'en',
            'mode': 'translate'
        }
    
    welcome_text = """
🤖 Assalomu aleykum! Men sizning AI yordamchi botingizman!

✨ Imkoniyatlarim:
• 🤖 AI bilan suhbatlashish
• 🌍 Matnlarni tarjima qilish
• 🎤 Ovozli xabarlarni tarjima qilish
• 📍 Joylashuvingiz bo'yicha avtomatik til
• ⚙️ 12 ta til qo'llab-quvvatlash

Boshlaymizmi? Menyudan tanlang! 🚀
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI chat with OpenAI GPT"""
    user_message = update.message.text
    
    try:
        # Send typing action
        await update.message.chat.send_action(action="typing")
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Siz foydali va do'stona yordamchi AI assistentsiz. Foydalanuvchiga har qanday savolda yordam bering."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        await update.message.reply_text(f"🤖 {ai_response}")
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        await update.message.reply_text(
            "❌ AI xatolik berdi. Iltimos:\n"
            "1. OPENAI_API_KEY to'g'riligini tekshiring\n"
            "2. Hisobingizda kredit borligini tekshiring\n"
            "3. Qaytadan urinib ko'ring"
        )

async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Translate text using deep-translator"""
    user_id = update.effective_user.id
    text = update.message.text
    target_lang = LANG_CODES.get(
        user_data.get(user_id, {}).get('target_language', 'en'),
        'en'
    )
    
    try:
        # Detect source language and translate
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(text)
        
        response = f"🌍 Tarjima ({target_lang}):\n\n{translated}"
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        await update.message.reply_text(
            "❌ Tarjima xatoligi.\n"
            "Internet aloqangizni tekshiring va qaytadan urinib ko'ring."
        )

async def translate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Translate voice message"""
    user_id = update.effective_user.id
    target_lang = LANG_CODES.get(
        user_data.get(user_id, {}).get('target_language', 'en'),
        'en'
    )
    
    try:
        await update.message.reply_text("🎤 Ovoz qayta ishlanmoqda...")
        
        # Download voice file
        voice = await update.message.voice.get_file()
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as ogg_file:
            ogg_path = ogg_file.name
            await voice.download_to_drive(ogg_path)
        
        # Convert OGG to WAV
        wav_path = ogg_path.replace('.ogg', '.wav')
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format='wav')
        
        # Speech recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
            # Try to recognize speech
            try:
                transcript = recognizer.recognize_google(audio_data)
            except sr.UnknownValueError:
                await update.message.reply_text("❌ Ovoz aniq eshitilmadi. Qaytadan yuboring.")
                return
            except sr.RequestError:
                await update.message.reply_text("❌ Tarjima servisi ishlamayapti. Keyinroq urinib ko'ring.")
                return
        
        # Translate the transcript
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(transcript)
        
        response = f"🎤 Eshitildi:\n{transcript}\n\n🌍 Tarjima:\n{translated}"
        await update.message.reply_text(response)
        
        # Cleanup
        os.remove(ogg_path)
        os.remove(wav_path)
        
    except Exception as e:
        logger.error(f"Voice translation error: {e}")
        await update.message.reply_text(
            "❌ Ovozli xabar tarjima qilinmadi.\n"
            "FFmpeg o'rnatilganligini tekshiring:\n"
            "pip install pydub\n"
            "va ffmpeg binary yuklab oling."
        )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle location and set language automatically"""
    user_id = update.effective_user.id
    location = update.message.location
    
    try:
        # Get country from coordinates
        lat, lon = location.latitude, location.longitude
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        
        response = requests.get(url, headers={'User-Agent': 'TelegramBot/1.0'}, timeout=10)
        data = response.json()
        
        country_code = data.get('address', {}).get('country_code', 'uz')
        
        # Map country to language
        country_to_lang = {
            'uz': 'uz', 'us': 'en', 'gb': 'en', 'ru': 'ru',
            'tr': 'tr', 'sa': 'ar', 'cn': 'zh', 'es': 'es',
            'fr': 'fr', 'de': 'de', 'jp': 'ja', 'kr': 'ko',
            'in': 'hi'
        }
        
        detected_lang = country_to_lang.get(country_code, 'en')
        user_data[user_id]['target_language'] = detected_lang
        
        country = data.get('address', {}).get('country', 'Unknown')
        lang_name = LANGUAGES.get(detected_lang, 'English')
        
        await update.message.reply_text(
            f"📍 Joylashuv: {country}\n"
            f"🌍 Tarjima tili avtomatik o'rnatildi: {lang_name}\n\n"
            f"Endi xabar yuboring, avtomatik tarjima qilaman!"
        )
        
    except Exception as e:
        logger.error(f"Location error: {e}")
        await update.message.reply_text("❌ Joylashuv aniqlanmadi. Qaytadan urinib ko'ring.")

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings menu"""
    await update.message.reply_text(
        "⚙️ Tarjima tilini tanlang:",
        reply_markup=get_language_keyboard()
    )

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang_code = query.data.split('_')[1]
    
    if user_id not in user_data:
        user_data[user_id] = {'language': 'uz', 'target_language': 'en', 'mode': 'translate'}
    
    user_data[user_id]['target_language'] = lang_code
    lang_name = LANGUAGES.get(lang_code, 'Unknown')
    
    await query.edit_message_text(
        f"✅ Tarjima tili o'rnatildi: {lang_name}\n\n"
        f"Endi matn yoki ovozli xabar yuboring!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """
📖 Qo'llanma:

1️⃣ 🤖 AI Suhbat
   - AI bilan erkin suhbatlashing
   - Har qanday savol bering

2️⃣ 🌍 Tarjima
   - Matn yuboring
   - Avtomatik tarjima bo'ladi

3️⃣ 🎤 Ovozli Tarjima
   - Ovozli xabar yuboring
   - Ovoz taniladi va tarjima qilinadi

4️⃣ 📍 Joylashuv
   - Geolokatsiya yuboring
   - Til avtomatik aniqlanadi

5️⃣ ⚙️ Sozlamalar
   - Tarjima tilini o'zgartiring
   - 12 ta til mavjud

💡 Maslahat: Oddiy xabar yuboring, men avtomatik ishlayman!

❓ Savol: /start
    """
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Initialize user data if needed
    if user_id not in user_data:
        user_data[user_id] = {
            'language': 'uz',
            'target_language': 'en',
            'mode': 'translate'
        }
    
    # Handle menu buttons
    if text == '🤖 AI Suhbat':
        user_data[user_id]['mode'] = 'ai'
        await update.message.reply_text(
            "🤖 AI rejimi yoqildi!\n"
            "Menga har qanday savol bering, men javob beraman. 😊"
        )
        return
    
    elif text == '🌍 Tarjima':
        user_data[user_id]['mode'] = 'translate'
        await update.message.reply_text(
            "🌍 Tarjima rejimi yoqildi!\n"
            "Matn yuboring, tarjima qilaman."
        )
        return
    
    elif text == '🎤 Ovozli Tarjima':
        await update.message.reply_text(
            "🎤 Ovozli xabar yuboring, tarjima qilaman.\n\n"
            "📝 Eslatma: Aniq gapiring!"
        )
        return
    
    elif text == '📍 Joylashuv':
        keyboard = [[KeyboardButton('📍 Joylashuvni yuborish', request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "📍 Tugmani bosing yoki geolokatsiyangizni yuboring:",
            reply_markup=reply_markup
        )
        return
    
    elif text == '⚙️ Sozlamalar':
        await settings(update, context)
        return
    
    elif text == 'ℹ️ Yordam':
        await help_command(update, context)
        return
    
    # Process based on mode
    mode = user_data[user_id].get('mode', 'translate')
    
    if mode == 'ai':
        await ai_chat(update, context)
    else:
        await translate_text(update, context)

def main():
    """Start the bot"""
    # Check if token exists
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN topilmadi!")
        print("📝 .env faylini yarating va tokenni qo'shing:")
        print("TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, translate_voice))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(CallbackQueryHandler(language_callback, pattern='^lang_'))
    
    # Start bot
    logger.info("🤖 Bot ishga tushdi! Ctrl+C bilan to'xtatish mumkin.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

