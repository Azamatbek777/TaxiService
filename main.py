import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from geopy.distance import geodesic
import nest_asyncio

nest_asyncio.apply()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

# Foydalanuvchilar ma'lumotlari
users = {"clients": {}, "drivers": {}}

# Asosiy menyu
def generate_main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📍 Lokatsiya yuborish", request_location=True)],
        [KeyboardButton("🔄 Yangilash"), KeyboardButton("🚪 Finish")],
        [KeyboardButton("/start"), KeyboardButton("/reklama")]
    ], resize_keyboard=True, one_time_keyboard=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[KeyboardButton("Mijoz"), KeyboardButton("Haydovchi")]]
    await update.message.reply_text(
        "👋 Xush kelibsiz! Kim siz?\nRolni tanlang:", 
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    )
    context.user_data.clear()

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = 'clients' if update.message.text == "Mijoz" else 'drivers'
    context.user_data["role"] = role
    await update.message.reply_text(
        "📞 Telefon raqamingizni yuboring:", 
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📞 Raqam yuborish", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True
        )
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = context.user_data.get("role")
    if not role:
        await update.message.reply_text("Iltimos, avval rolni tanlang. /start komandasini bering.")
        return
    
    contact = update.message.contact
    users[role][update.message.chat_id] = {
        "phone": contact.phone_number,
        "location": None,
        "active": True
    }
    await update.message.reply_text(
        "✅ Raqam qabul qilindi.\n📍 Endi lokatsiyangizni yuboring.", 
        reply_markup=generate_main_menu()
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = context.user_data.get("role")
    if not role:
        await update.message.reply_text("Iltimos, avval rolni tanlang. /start komandasini bering.")
        return

    location = update.message.location
    user = users[role].get(update.message.chat_id)
    if user:
        user["location"] = (location.latitude, location.longitude)
        user["active"] = True
        await update.message.reply_text("📍 Lokatsiya qabul qilindi.", reply_markup=generate_main_menu())
        if role == "clients":
            await show_nearby_drivers(update)
        else:
            await show_nearby_clients(update)
    else:
        await update.message.reply_text("Iltimos, avval telefon raqamingizni yuboring.")

async def show_nearby_drivers(update: Update):
    client_loc = users["clients"][update.message.chat_id].get("location")
    if not client_loc:
        await update.message.reply_text("Sizning lokatsiyangiz mavjud emas.")
        return

    results = [
        f"🚗 {info['phone']} — [Ko'rish](https://www.google.com/maps/search/?api=1&query={info['location'][0]},{info['location'][1]})"
        for info in users["drivers"].values()
        if info.get("location") and info.get("active") and distance(client_loc, info["location"]) < 10
    ]
    if results:
        await update.message.reply_text(
            "🟢 Yaqin haydovchilar:\n" + "\n".join(results),
            parse_mode="Markdown",
            reply_markup=generate_main_menu()
        )
    else:
        await update.message.reply_text("❌ Yaqin haydovchilar topilmadi.", reply_markup=generate_main_menu())

async def show_nearby_clients(update: Update):
    driver_loc = users["drivers"][update.message.chat_id].get("location")
    if not driver_loc:
        await update.message.reply_text("Sizning lokatsiyangiz mavjud emas.")
        return

    results = [
        f"👤 {info['phone']} — [Ko'rish](https://www.google.com/maps/search/?api=1&query={info['location'][0]},{info['location'][1]})"
        for info in users["clients"].values()
        if info.get("location") and info.get("active") and distance(driver_loc, info["location"]) < 10
    ]
    if results:
        await update.message.reply_text(
            "🟢 Yaqin mijozlar:\n" + "\n".join(results),
            parse_mode="Markdown",
            reply_markup=generate_main_menu()
        )
    else:
        await update.message.reply_text("❌ Yaqin mijozlar topilmadi.", reply_markup=generate_main_menu())

def distance(loc1, loc2):
    return geodesic(loc1, loc2).km

async def send_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_CHAT_ID:
        return await update.message.reply_text("⛔ Sizda ruxsat yo'q.")

    msg = update.message.text[9:].strip()
    if not msg:
        return await update.message.reply_text("ℹ️ Iltimos, reklama matnini yozing.")

    count = 0
    for group in ["clients", "drivers"]:
        for uid in list(users[group].keys()):
            try:
                await context.bot.send_message(uid, f"📢 Reklama:\n{msg}")
                count += 1
            except Exception:
                pass

    await update.message.reply_text(f"✅ Reklama {count} foydalanuvchiga yuborildi.")

async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = context.user_data.get("role")
    if role == "clients":
        await show_nearby_drivers(update)
    elif role == "drivers":
        await show_nearby_clients(update)
    else:
        await update.message.reply_text("Iltimos, avval /start buyrug'ini bering.")

async def handle_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = context.user_data.get("role")
    chat_id = update.message.chat_id

    if role in ["clients", "drivers"]:
        if chat_id in users[role]:
            users[role][chat_id]["active"] = False
            users[role][chat_id]["location"] = None
        context.user_data.clear()
        await update.message.reply_text("🔚 Faoliyatingiz tugatildi. /start bilan qayta boshlashingiz mumkin.", reply_markup=generate_main_menu())
    else:
        await update.message.reply_text("Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.", reply_markup=generate_main_menu())

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reklama", send_advertisement))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(Mijoz|Haydovchi)$"), register_user))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🔄 Yangilash$"), handle_refresh))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^🚪 Finish$"), handle_finish))

    app.run_polling()

if __name__ == "__main__":
    main()
