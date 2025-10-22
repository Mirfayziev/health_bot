import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# .env faylni yuklash
load_dotenv()

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API kalitlari
TELEGRAM_TOKEN = os.getenv("8321755260:AAHzrU2HhnWEARnxvn8dykq3ixw5r2PX2nM")
GEMINI_API_KEY = os.getenv("AIzaSyAeDbNZVcpZ7wemRVCc9dvkoaMFkJZZ16A")

# Google Gemini AI sozlash
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-pro')

# Conversation states
(MAIN_MENU, PROFILE_SETUP, WEIGHT_INPUT, HEIGHT_INPUT, AGE_INPUT, 
 ACTIVITY_LEVEL, GOAL_INPUT, TASK_INPUT, MEAL_PLAN, 
 STRESS_CHECK, WEEKLY_REVIEW) = range(11)

# Foydalanuvchi ma'lumotlarini saqlash
user_data_storage = {}


class UserProfile:
    """Foydalanuvchi profili"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.weight = None
        self.height = None
        self.age = None
        self.gender = None
        self.activity_level = None
        self.goal = None
        self.daily_tasks = []
        self.completed_tasks = []
        self.meal_history = []
        self.stress_levels = []
        self.weekly_stats = []
        
    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'weight': self.weight,
            'height': self.height,
            'age': self.age,
            'gender': self.gender,
            'activity_level': self.activity_level,
            'goal': self.goal,
            'daily_tasks': self.daily_tasks,
            'completed_tasks': self.completed_tasks,
            'meal_history': self.meal_history,
            'stress_levels': self.stress_levels,
            'weekly_stats': self.weekly_stats
        }
    
    def calculate_bmi(self) -> float:
        """BMI hisoblab berish"""
        if self.weight and self.height:
            height_m = self.height / 100
            return round(self.weight / (height_m ** 2), 2)
        return 0
    
    def calculate_daily_calories(self) -> int:
        """Kunlik kerakli kaloriyani hisoblash"""
        if not all([self.weight, self.height, self.age, self.gender]):
            return 2000
        
        if self.gender == "male":
            bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age + 5
        else:
            bmr = 10 * self.weight + 6.25 * self.height - 5 * self.age - 161
        
        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        
        multiplier = activity_multipliers.get(self.activity_level, 1.55)
        daily_calories = bmr * multiplier
        
        if self.goal == "lose_weight":
            daily_calories -= 500
        elif self.goal == "gain_muscle":
            daily_calories += 300
        
        return int(daily_calories)


async def ask_gemini(prompt: str, context: str = "") -> str:
    """Google Gemini AI dan javob olish (100% BEPUL!)"""
    try:
        system_prompt = """Siz professional nutritsionist, fitnes treneri va psixolog 
        rolida javob berasiz. Har doim o'zbek tilida, oddiy va tushunarli javob bering. 
        Sog'liq, ovqatlanish, stress va produktivlik bo'yicha maslahat bering.
        Javoblaringiz qisqa va amaliy bo'lsin."""
        
        if context:
            full_prompt = f"{system_prompt}\n\nKontekst: {context}\n\nSavol: {prompt}"
        else:
            full_prompt = f"{system_prompt}\n\nSavol: {prompt}"
        
        response = gemini_model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "Kechirasiz, hozir javob bera olmayman. Iltimos, qaytadan urinib ko'ring."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start komandasi - asosiy menyu"""
    user = update.effective_user
    user_id = user.id
    
    if user_id not in user_data_storage:
        user_data_storage[user_id] = UserProfile(user_id)
    
    keyboard = [
        [KeyboardButton("📋 Kunlik rejalashtirish")],
        [KeyboardButton("🍎 Ovqatlanish rejasi"), KeyboardButton("📊 Haftalik natijalar")],
        [KeyboardButton("😌 Stress va dam olish"), KeyboardButton("👤 Profil sozlash")],
        [KeyboardButton("💬 AI bilan suhbat")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = f"""
🤖 Assalomu alaykum, {user.first_name}!

Men sizning shaxsiy AI yordamchingizman (Google Gemini 🆓)

✅ Kunlik vazifalarni rejalashtirish
✅ Vazndan kelib chiqib ovqatlanish rejasi
✅ Stress va dam olishni boshqarish
✅ Haftalik natijalarni monitoring
✅ AI bilan 24/7 maslahat (BEPUL!)

Boshlash uchun pastdagi tugmalardan birini tanlang! 👇
"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return MAIN_MENU


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asosiy menyu tanlovlarini boshqarish"""
    text = update.message.text
    
    if text == "📋 Kunlik rejalashtirish":
        return await show_daily_tasks(update, context)
    elif text == "🍎 Ovqatlanish rejasi":
        return await show_meal_plan(update, context)
    elif text == "📊 Haftalik natijalar":
        return await show_weekly_stats(update, context)
    elif text == "😌 Stress va dam olish":
        return await stress_management(update, context)
    elif text == "👤 Profil sozlash":
        return await setup_profile(update, context)
    elif text == "💬 AI bilan suhbat":
        await update.message.reply_text(
            "💬 Menga istalgan savol bering! Men Google Gemini AI yordamida sizga "
            "sog'liq, ovqatlanish, produktivlik va stress boshqarish bo'yicha "
            "maslahat beraman.\n\n"
            "🆓 Bu xizmat 100% BEPUL!\n\n"
            "Asosiy menyuga qaytish: /start"
        )
        return MAIN_MENU
    
    return MAIN_MENU


async def show_daily_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kunlik vazifalarni ko'rsatish"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Yangi vazifa qo'shish", callback_data="add_task")],
        [InlineKeyboardButton("✅ Vazifalarni ko'rish", callback_data="view_tasks")],
        [InlineKeyboardButton("🤖 AI bilan rejalashtirish", callback_data="ai_plan_tasks")],
        [InlineKeyboardButton("« Orqaga", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    today = datetime.now().strftime("%d-%m-%Y")
    completed = len(profile.completed_tasks) if profile else 0
    total = len(profile.daily_tasks) if profile else 0
    
    text = f"""
📋 **Kunlik rejalashtirish**
📅 Sana: {today}

✅ Bajarilgan: {completed}/{total}
⏳ Qolgan: {total - completed}

Nima qilmoqchisiz?
"""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return MAIN_MENU


async def show_meal_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ovqatlanish rejasini ko'rsatish"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    if not profile or not profile.weight:
        await update.message.reply_text(
            "⚠️ Avval profilingizni to'ldiring!\n"
            "Profil sozlash tugmasini bosing."
        )
        return MAIN_MENU
    
    await update.message.reply_text("🤖 Google Gemini AI sizga maxsus ovqatlanish rejasi tayyorlamoqda...")
    
    daily_calories = profile.calculate_daily_calories()
    bmi = profile.calculate_bmi()
    
    prompt = f"""
    Foydalanuvchi ma'lumotlari:
    - Vazni: {profile.weight} kg
    - Bo'yi: {profile.height} cm
    - BMI: {bmi}
    - Kunlik kaloriya: {daily_calories} kcal
    - Maqsad: {profile.goal or 'maintain'}
    
    Iltimos, bir kunlik ovqatlanish rejasi tuzing:
    1. Nonushta (kaloriya va tarkib)
    2. Tushlik (kaloriya va tarkib)
    3. Kechki ovqat (kaloriya va tarkib)
    4. Snacklar (2 ta)
    
    O'zbek milliy taomlarini ham qo'shing. Qisqa va aniq javob bering.
    """
    
    meal_plan = await ask_gemini(prompt)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Yangi reja", callback_data="new_meal_plan")],
        [InlineKeyboardButton("💾 Saqlash", callback_data="save_meal_plan")],
        [InlineKeyboardButton("« Orqaga", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
🍎 **Sizning ovqatlanish rejangiz**
(Google Gemini AI tomonidan)

📊 Kunlik kaloriya: {daily_calories} kcal
📏 BMI: {bmi}

{meal_plan}
"""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return MAIN_MENU


async def show_weekly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Haftalik natijalarni ko'rsatish"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    if not profile:
        await update.message.reply_text("⚠️ Ma'lumot topilmadi.")
        return MAIN_MENU
    
    await update.message.reply_text("📊 Haftalik natijalaringiz tahlil qilinmoqda...")
    
    total_tasks = len(profile.daily_tasks) * 7
    completed_tasks = len(profile.completed_tasks)
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    prompt = f"""
    Haftalik statistika:
    - Jami vazifalar: {total_tasks}
    - Bajarilgan: {completed_tasks}
    - Bajarish: {completion_rate:.1f}%
    - Stress: {profile.stress_levels[-1] if profile.stress_levels else 'Ma\'lumot yo\'q'}
    
    Qisqa tahlil va keyingi haftaga 3 ta maslahat bering.
    """
    
    analysis = await ask_gemini(prompt)
    
    keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
📊 **Haftalik natijalar**

✅ Bajarilgan: {completed_tasks}/{total_tasks}
📈 Bajarish: {completion_rate:.1f}%

🤖 **AI tahlili (Gemini):**
{analysis}
"""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return MAIN_MENU


async def stress_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stress boshqarish"""
    keyboard = [
        [InlineKeyboardButton("😓 Stress tekshirish", callback_data="check_stress")],
        [InlineKeyboardButton("🧘 Meditatsiya", callback_data="meditation")],
        [InlineKeyboardButton("⏰ Dam olish rejasi", callback_data="plan_rest")],
        [InlineKeyboardButton("💤 Uyqu rejasi", callback_data="sleep_schedule")],
        [InlineKeyboardButton("« Orqaga", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
😌 **Stress va dam olish**

Sog'lom turmush tarzi uchun stress boshqarish muhim!

Quyidagilardan birini tanlang:
"""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return MAIN_MENU


async def setup_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Profil sozlash"""
    keyboard = [
        [InlineKeyboardButton("Erkak 👨", callback_data="gender_male")],
        [InlineKeyboardButton("Ayol 👩", callback_data="gender_female")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👤 **Profil sozlash**\n\nJinsingizni tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return PROFILE_SETUP


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inline button handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    if query.data == "back_main":
        keyboard = [
            [KeyboardButton("📋 Kunlik rejalashtirish")],
            [KeyboardButton("🍎 Ovqatlanish rejasi"), KeyboardButton("📊 Haftalik natijalar")],
            [KeyboardButton("😌 Stress va dam olish"), KeyboardButton("👤 Profil sozlash")],
            [KeyboardButton("💬 AI bilan suhbat")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.edit_message_text("Asosiy menyu:")
        await context.bot.send_message(chat_id=user_id, text="👇", reply_markup=reply_markup)
        return MAIN_MENU
    
    elif query.data == "add_task":
        await query.edit_message_text(
            "✍️ Yangi vazifangizni yozing:\n\n"
            "Masalan: 'Ertalab yugurish', 'Hisobot tayyorlash'"
        )
        return TASK_INPUT
    
    elif query.data == "view_tasks":
        if not profile or not profile.daily_tasks:
            await query.edit_message_text("📝 Hozircha vazifalar yo'q.")
            return MAIN_MENU
        
        tasks_text = "📋 **Bugungi vazifalar:**\n\n"
        for i, task in enumerate(profile.daily_tasks, 1):
            status = "✅" if task in profile.completed_tasks else "⏳"
            tasks_text += f"{i}. {status} {task}\n"
        
        keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(tasks_text, reply_markup=reply_markup, parse_mode='Markdown')
        return MAIN_MENU
    
    elif query.data == "ai_plan_tasks":
        await query.edit_message_text("🤖 Google Gemini AI sizga kunlik reja tuzmoqda...")
        
        prompt = """Produktiv bir kun uchun 6 ta vazifa rejasi tuzing.
        Ish, sog'liq, o'rganish va dam olishni muvozanatlashtiring.
        Har vazifa uchun tavsiya vaqt ko'rsating. Qisqa va aniq."""
        
        ai_tasks = await ask_gemini(prompt)
        
        keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🤖 **AI reja (Gemini):**\n\n{ai_tasks}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    elif query.data == "check_stress":
        await query.edit_message_text(
            "😌 **Stress tekshirish**\n\n"
            "Quyidagi savollarga 1-10 baho bering:\n"
            "1️⃣ Charchoq darajasi?\n"
            "2️⃣ Uyqu sifati?\n"
            "3️⃣ Ish yuki?\n\n"
            "Javob: 5,7,6 formatda yozing"
        )
        return STRESS_CHECK
    
    elif query.data == "meditation":
        prompt = "5 daqiqalik oddiy meditatsiya mashqi tavsiya eting. O'zbek tilida, qisqa va amaliy."
        meditation = await ask_gemini(prompt)
        
        keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🧘 **Meditatsiya (Gemini AI):**\n\n{meditation}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    elif query.data == "plan_rest":
        prompt = "Ish kunida dam olishni qanday rejalashtirish kerak? 3-4 ta amaliy maslahat bering."
        rest_plan = await ask_gemini(prompt)
        
        keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"⏰ **Dam olish rejasi:**\n\n{rest_plan}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    elif query.data == "sleep_schedule":
        prompt = "Sog'lom uyqu uchun 5 ta muhim qoida va optimal uyqu jadvalini tavsiya eting."
        sleep_guide = await ask_gemini(prompt)
        
        keyboard = [[InlineKeyboardButton("« Orqaga", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💤 **Uyqu rejasi:**\n\n{sleep_guide}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return MAIN_MENU
    
    elif query.data.startswith("gender_"):
        gender = "male" if query.data == "gender_male" else "female"
        if not profile:
            profile = UserProfile(user_id)
            user_data_storage[user_id] = profile
        profile.gender = gender
        
        await query.edit_message_text("✅ Yaxshi!\n\n📏 Vazningizni kiriting (kg):")
        return WEIGHT_INPUT
    
    return MAIN_MENU


async def handle_weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vazn input"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    try:
        weight = float(update.message.text)
        if 30 <= weight <= 300:
            profile.weight = weight
            await update.message.reply_text(f"✅ Vazn: {weight} kg\n\n📏 Bo'yingizni kiriting (cm):")
            return HEIGHT_INPUT
        else:
            await update.message.reply_text("❌ 30-300 kg orasida kiriting:")
            return WEIGHT_INPUT
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting:")
        return WEIGHT_INPUT


async def handle_height_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bo'y input"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    try:
        height = float(update.message.text)
        if 100 <= height <= 250:
            profile.height = height
            await update.message.reply_text(f"✅ Bo'y: {height} cm\n\n🎂 Yoshingizni kiriting:")
            return AGE_INPUT
        else:
            await update.message.reply_text("❌ 100-250 cm orasida kiriting:")
            return HEIGHT_INPUT
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting:")
        return HEIGHT_INPUT


async def handle_age_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Yosh input"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    try:
        age = int(update.message.text)
        if 10 <= age <= 100:
            profile.age = age
            
            keyboard = [
                [InlineKeyboardButton("🪑 Kam harakatli", callback_data="activity_sedentary")],
                [InlineKeyboardButton("🚶 Yengil faol", callback_data="activity_light")],
                [InlineKeyboardButton("🏃 O'rtacha faol", callback_data="activity_moderate")],
                [InlineKeyboardButton("💪 Juda faol", callback_data="activity_very_active")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Yosh: {age}\n\n🏃 Faollik darajangiz:",
                reply_markup=reply_markup
            )
            return ACTIVITY_LEVEL
        else:
            await update.message.reply_text("❌ 10-100 orasida kiriting:")
            return AGE_INPUT
    except ValueError:
        await update.message.reply_text("❌ Faqat raqam kiriting:")
        return AGE_INPUT


async def handle_activity_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Faollik darajasi"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    activity_map = {
        "activity_sedentary": "sedentary",
        "activity_light": "light",
        "activity_moderate": "moderate",
        "activity_very_active": "very_active"
    }
    
    profile.activity_level = activity_map.get(query.data, "moderate")
    
    keyboard = [
        [InlineKeyboardButton("📉 Vazn tushirish", callback_data="goal_lose_weight")],
        [InlineKeyboardButton("⚖️ Vazn saqlash", callback_data="goal_maintain")],
        [InlineKeyboardButton("💪 Mushak ortirish", callback_data="goal_gain_muscle")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "✅ Saqlandi!\n\n🎯 Maqsadingiz:",
        reply_markup=reply_markup
    )
    return GOAL_INPUT


async def handle_goal_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqsad input"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    goal_map = {
        "goal_lose_weight": "lose_weight",
        "goal_maintain": "maintain",
        "goal_gain_muscle": "gain_muscle"
    }
    
    profile.goal = goal_map.get(query.data, "maintain")
    
    bmi = profile.calculate_bmi()
    daily_calories = profile.calculate_daily_calories()
    
    keyboard = [
        [KeyboardButton("📋 Kunlik rejalashtirish")],
        [KeyboardButton("🍎 Ovqatlanish rejasi"), KeyboardButton("📊 Haftalik natijalar")],
        [KeyboardButton("😌 Stress va dam olish"), KeyboardButton("👤 Profil sozlash")],
        [KeyboardButton("💬 AI bilan suhbat")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    summary = f"""
✅ **Profil saqlandi!**

📊 **Ma'lumotlar:**
👤 Jins: {'Erkak' if profile.gender == 'male' else 'Ayol'}
📏 Vazn: {profile.weight} kg
📐 Bo'y: {profile.height} cm
🎂 Yosh: {profile.age}
🏃 Faollik: {profile.activity_level}
🎯 Maqsad: {profile.goal}

📈 BMI: {bmi}
🔥 Kunlik kaloriya: {daily_calories} kcal

Tayyor! Google Gemini AI yordamida barcha funksiyalardan foydalaning! 🎉
"""
    
    await query.edit_message_text(summary, parse_mode='Markdown')
    await context.bot.send_message(
        chat_id=user_id,
        text="Asosiy menyu 👇",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU


async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """AI bilan suhbat"""
    user_id = update.effective_user.id
    user_message = update.message.text
    profile = user_data_storage.get(user_id)
    
    context_info = ""
    if profile and profile.weight:
        context_info = f"""
        Foydalanuvchi: {profile.age} yosh, {profile.weight}kg, {profile.height}cm
        Maqsad: {profile.goal}
        """
    
    response = await ask_gemini(user_message, context_info)
    await update.message.reply_text(f"🤖 {response}")
    
    return MAIN_MENU


async def handle_task_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vazifa input"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    task = update.message.text
    
    if profile:
        profile.daily_tasks.append(task)
        await update.message.reply_text(
            f"✅ Vazifa qo'shildi: {task}\n\n/start - Asosiy menyu"
        )
    
    return MAIN_MENU


async def handle_stress_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stress check"""
    user_id = update.effective_user.id
    profile = user_data_storage.get(user_id)
    
    try:
        scores = [int(x.strip()) for x in update.message.text.split(',')]
        if len(scores) == 3 and all(1 <= s <= 10 for s in scores):
            avg_stress = sum(scores) / 3
            profile.stress_levels.append(avg_stress)
            
            prompt = f"""
            Stress baholari:
            - Charchoq: {scores[0]}/10
            - Uyqu: {scores[1]}/10
            - Ish yuki: {scores[2]}/10
            O'rtacha: {avg_stress:.1f}/10
            
            Qisqa tahlil va 3 ta maslahat bering.
            """
            
            advice = await ask_gemini(prompt)
            
            await update.message.reply_text(
                f"📊 **Stress tahlili**\n\n"
                f"O'rtacha: {avg_stress:.1f}/10\n\n"
                f"🤖 {advice}\n\n"
                f"/start - Asosiy menyu"
            )
        else:
            await update.message.reply_text("❌ 3 ta baho (1-10): 5,7,6")
    except:
        await update.message.reply_text("❌ Xato format. Misol: 5,7,6")
    
    return MAIN_MENU


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xatolarni handle qilish"""
    logger.error(f"Error: {context.error}")


#def main():
 #   """Botni ishga tushirish"""
  #  if not TELEGRAM_TOKEN:
   #     raise ValueError("❌ TELEGRAM_BOT_TOKEN topilmadi!")
   # if not GEMINI_API_KEY:
    #    raise ValueError("❌ GEMINI_API_KEY topilmadi!")
def main():
    """Botni ishga tushirish"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
                CallbackQueryHandler(button_callback)
            ],
            PROFILE_SETUP: [CallbackQueryHandler(button_callback)],
            WEIGHT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_weight_input)],
            HEIGHT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_height_input)],
            AGE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age_input)],
            ACTIVITY_LEVEL: [CallbackQueryHandler(handle_activity_level)],
            GOAL_INPUT: [CallbackQueryHandler(handle_goal_input)],
            TASK_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_input)],
            STRESS_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stress_check)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Bot ishga tushdi! (Google Gemini AI)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()



