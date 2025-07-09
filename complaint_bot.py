import logging
import uuid
import os
# MODIFIED: Import the escape_markdown function
from telegram.helpers import escape_markdown
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- Konfigurasi ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TARGET_GROUP_ID = os.environ.get('TARGET_GROUP_ID')
DIVISIONS = ["ME", "HOUSE KEEPING", "SAS"]

# --- Validasi ---
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable not set.")
if not TARGET_GROUP_ID:
    raise ValueError("Error: TARGET_GROUP_ID environment variable not set.")

# --- Pengaturan Log ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Tahapan Percakapan ---
CATEGORY, DESCRIPTION, DEPARTMENT = range(3)

# --- Fungsi Percakapan (Bahasa Indonesia) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categories = [['Infrastruktur', 'Kebersihan'], ['Keamanan', 'Lainnya']]
    reply_markup = ReplyKeyboardMarkup(categories, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Halo! Saya siap membantu Anda mengajukan laporan keluhan.\n\n"
        "Silakan pilih kategori keluhan Anda. Kirim /batal untuk berhenti.",
        reply_markup=reply_markup,
    )
    return CATEGORY

async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['category'] = update.message.text
    await update.message.reply_text(
        f"Baik! Anda telah memilih '{update.message.text}'.\n\n"
        "Sekarang, mohon jelaskan keluhan Anda secara rinci.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text
    department_buttons = [DIVISIONS]
    reply_markup = ReplyKeyboardMarkup(department_buttons, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Terima kasih. Sekarang, silakan pilih divisi yang dituju.",
        reply_markup=reply_markup
    )
    return DEPARTMENT

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    chosen_division_raw = update.message.text
    
    if chosen_division_raw not in DIVISIONS:
        await update.message.reply_text(
            "Pilihan divisi tidak valid. Silakan pilih salah satu dari tombol yang tersedia.",
            reply_markup=update.message.reply_markup
        )
        return DEPARTMENT

    complaint_id = str(uuid.uuid4()).split('-')[0].upper()

    # --- MODIFIED: Safely escape all user-provided text ---
    chosen_division = escape_markdown(chosen_division_raw, version=2)
    category_text = escape_markdown(context.user_data.get('category', ''), version=2)
    description_text = escape_markdown(context.user_data.get('description', ''), version=2)
    reporter_username = escape_markdown(f"@{user.username}", version=2) if user.username else "N/A"
    
    report_text = (
        f"🚨 *Laporan Keluhan Baru* 🚨\n\n"
        f"*ID Keluhan:* `{complaint_id}`\n"
        f"*Divisi yang Dituju:* {chosen_division}\n"
        f"*Pelapor:* {reporter_username} \(ID: {user.id}\)\n"
        f"*Kategori:* {category_text}\n"
        f"*Deskripsi:* {description_text}"
    )
    
    await context.bot.send_message(
        chat_id=TARGET_GROUP_ID,
        text=report_text,
        parse_mode='MarkdownV2'
    )
    
    await update.message.reply_text(
        "Terima Kasih, komplain anda telah disubmit dan akan disampaikan ke divisi terkait",
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Laporan dibatalkan.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("report", start)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
            DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_report)]
        },
        fallbacks=[CommandHandler("batal", cancel)],
    )
    application.add_handler(conv_handler)
    print("Bot is running with single group logic...")
    application.run_polling()

if __name__ == "__main__":
    main()