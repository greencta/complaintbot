import logging
import uuid
import os
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

# Divisi yang akan digunakan
DEPARTMENT_CHAT_IDS = {
    "ME": os.environ.get("CHAT_ID_ME"),
    "HOUSE KEEPING": os.environ.get("CHAT_ID_HK"),
    "SAS": os.environ.get("CHAT_ID_SAS"),
}

# --- Validasi ---
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable not set.")
for department, chat_id in DEPARTMENT_CHAT_IDS.items():
    if not chat_id:
        # Pesan error ini akan terlihat di log Render jika ada variabel yang kurang
        raise ValueError(f"Error: Environment variable untuk {department} tidak di-set.")

# --- Pengaturan Log ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Tahapan Percakapan ---
CATEGORY, DESCRIPTION, DEPARTMENT = range(3)

# --- Fungsi Percakapan (Bahasa Indonesia) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Memulai percakapan."""
    categories = [['Infrastruktur', 'Kebersihan'], ['Keamanan', 'Lainnya']]
    reply_markup = ReplyKeyboardMarkup(categories, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "Halo! Saya siap membantu Anda mengajukan laporan keluhan.\n\n"
        "Silakan pilih kategori keluhan Anda. Kirim /batal untuk berhenti.",
        reply_markup=reply_markup,
    )
    return CATEGORY

async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan kategori dan meminta deskripsi."""
    context.user_data['category'] = update.message.text
    logger.info("Kategori: %s", update.message.text)
    
    await update.message.reply_text(
        f"Baik! Anda telah memilih '{update.message.text}'.\n\n"
        "Sekarang, mohon jelaskan keluhan Anda secara rinci.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan deskripsi dan meminta pengguna memilih divisi."""
    context.user_data['description'] = update.message.text
    logger.info("Deskripsi: %s", update.message.text)
    
    department_keys = list(DEPARTMENT_CHAT_IDS.keys())
    department_buttons = [department_keys]
    reply_markup = ReplyKeyboardMarkup(department_buttons, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "Terima kasih. Sekarang, silakan pilih divisi yang berwenang untuk menangani masalah ini.",
        reply_markup=reply_markup
    )
    return DEPARTMENT

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mendapatkan divisi pilihan, mengirim laporan, dan mengakhiri percakapan."""
    user = update.message.from_user
    chosen_department = update.message.text
    
    if chosen_department not in DEPARTMENT_CHAT_IDS:
        await update.message.reply_text(
            "Pilihan divisi tidak valid. Silakan pilih salah satu dari tombol yang tersedia.",
            reply_markup=update.message.reply_markup
        )
        return DEPARTMENT

    target_chat_id = DEPARTMENT_CHAT_IDS[chosen_department]
    complaint_id = str(uuid.uuid4()).split('-')[0].upper()
    category_text = context.user_data.get('category')
    description_text = context.user_data.get('description')
    
    report_text = (
        f"🚨 *Laporan Keluhan Baru* 🚨\n\n"
        f"*ID Keluhan:* `{complaint_id}`\n"
        f"*Diteruskan ke:* {chosen_department}\n"
        f"*Pelapor:* @{user.username} (ID: {user.id})\n"
        f"*Kategori:* {category_text}\n"
        f"*Deskripsi:* {description_text}"
    )
    
    await context.bot.send_message(
        chat_id=target_chat_id,
        text=report_text,
        parse_mode='MarkdownV2'
    )
    
    # --- PESAN KONFIRMASI YANG BARU ---
    await update.message.reply_text(
        "Terima Kasih, komplain anda telah disubmit dan akan disampaikan ke divisi terkait",
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan percakapan."""
    await update.message.reply_text(
        "Laporan dibatalkan.", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Menjalankan bot."""
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
    print("Bot sedang berjalan dengan divisi ME, HK, SAS...")
    application.run_polling()

if __name__ == "__main__":
    main()