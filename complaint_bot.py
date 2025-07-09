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

# MODIFIED: Menambahkan tahapan PHOTO
CATEGORY, DESCRIPTION, PHOTO, DEPARTMENT = range(4)

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
    await update.message.reply_text(
        f"Baik! Anda telah memilih '{update.message.text}'.\n\n"
        "Sekarang, mohon jelaskan keluhan Anda secara rinci.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return DESCRIPTION

async def description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan deskripsi dan meminta foto."""
    context.user_data['description'] = update.message.text
    logger.info("Deskripsi: %s", update.message.text)
    await update.message.reply_text(
        "Terima kasih, deskripsi Anda telah disimpan.\n\n"
        "Sekarang, silakan unggah satu (1) foto sebagai bukti."
    )
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Menyimpan foto bukti dan meminta pengguna memilih divisi."""
    # Ambil file_id dari foto yang diunggah
    photo_file = update.message.photo[-1] # -1 untuk mendapatkan resolusi tertinggi
    context.user_data['photo_id'] = photo_file.file_id
    logger.info("Foto diterima dengan ID: %s", photo_file.file_id)

    department_buttons = [DIVISIONS]
    reply_markup = ReplyKeyboardMarkup(department_buttons, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "Foto bukti telah diterima. Terakhir, silakan pilih divisi yang dituju.",
        reply_markup=reply_markup
    )
    return DEPARTMENT

async def photo_invalid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Memberi tahu pengguna jika input bukan foto."""
    await update.message.reply_text(
        "Input tidak valid. Mohon unggah sebuah foto sebagai bukti."
    )
    return PHOTO # Tetap di tahapan PHOTO

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mengirim laporan berupa FOTO DENGAN CAPTION dan mengakhiri percakapan."""
    user = update.message.from_user
    chosen_division = update.message.text
    
    if chosen_division not in DIVISIONS:
        await update.message.reply_text(
            "Pilihan divisi tidak valid. Silakan pilih salah satu dari tombol yang tersedia."
        )
        return DEPARTMENT

    complaint_id = str(uuid.uuid4()).split('-')[0].upper()
    category_text = context.user_data.get('category')
    description_text = context.user_data.get('description')
    
    report_text = (
        f"🚨 Laporan Keluhan Baru 🚨\n\n"
        f"ID Keluhan: {complaint_id}\n"
        f"Divisi yang Dituju: {chosen_division}\n"
        f"Pelapor: @{user.username} (ID: {user.id})\n"
        f"Kategori: {category_text}\n\n"
        f"Deskripsi:\n{description_text}"
    )
    
    # MODIFIED: Mengirim foto dengan caption, bukan hanya teks
    photo_id_to_send = context.user_data['photo_id']
    await context.bot.send_photo(
        chat_id=TARGET_GROUP_ID,
        photo=photo_id_to_send,
        caption=report_text,
    )
    
    await update.message.reply_text(
        "Terima Kasih, komplain anda telah disubmit dan akan disampaikan ke divisi terkait",
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan percakapan."""
    await update.message.reply_text("Laporan dibatalkan.", reply_markup=ReplyKeyboardRemove())
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
            # MODIFIED: Menambahkan state untuk menangani foto
            PHOTO: [
                MessageHandler(filters.PHOTO, photo),
                MessageHandler(~filters.PHOTO, photo_invalid) # Jika input bukan foto
            ],
            DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_report)]
        },
        fallbacks=[CommandHandler("batal", cancel)],
    )
    
    application.add_handler(conv_handler)
    print("Bot sedang berjalan dengan alur unggah foto...")
    application.run_polling()

if __name__ == "__main__":
    main()