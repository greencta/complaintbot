import logging
import uuid
import os
import re
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
# Tahapan untuk pengguna yang melapor
CATEGORY, DESCRIPTION, PHOTO, DEPARTMENT = range(4)
# Tahapan BARU untuk tim divisi yang menyelesaikan laporan
GET_RESOLUTION_DESCRIPTION = range(4, 5)

# --- Fungsi Percakapan untuk Pelapor (Sama seperti sebelumnya) ---
async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    await update.message.reply_text(
        "Terima kasih, deskripsi Anda telah disimpan.\n\n"
        "Sekarang, silakan unggah satu (1) foto sebagai bukti."
    )
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo_file = update.message.photo[-1]
    context.user_data['photo_id'] = photo_file.file_id
    department_buttons = [DIVISIONS]
    reply_markup = ReplyKeyboardMarkup(department_buttons, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Foto bukti telah diterima. Terakhir, silakan pilih divisi yang dituju.",
        reply_markup=reply_markup
    )
    return DEPARTMENT

async def photo_invalid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Input tidak valid. Mohon unggah sebuah foto sebagai bukti.")
    return PHOTO

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    chosen_division = update.message.text
    if chosen_division not in DIVISIONS:
        await update.message.reply_text("Pilihan divisi tidak valid.")
        return DEPARTMENT
    complaint_id = str(uuid.uuid4()).split('-')[0].upper()
    category_text = context.user_data.get('category')
    description_text = context.user_data.get('description')
    report_text_for_parsing = (
        f"ID Keluhan: {complaint_id}\n"
        f"Divisi yang Dituju: {chosen_division}\n"
        f"Pelapor: @{user.username} (ID: {user.id})\n"
        f"Kategori: {category_text}\n\n"
        f"Deskripsi:\n{description_text}"
    )
    report_text_for_group = f"🚨 *Laporan Keluhan Baru* 🚨\n\n{report_text_for_parsing}"
    photo_id_to_send = context.user_data['photo_id']
    await context.bot.send_photo(
        chat_id=TARGET_GROUP_ID, photo=photo_id_to_send,
        caption=report_text_for_group, parse_mode='Markdown'
    )
    await update.message.reply_text(
        "Terima Kasih, komplain anda telah disubmit dan akan disampaikan ke divisi terkait",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Laporan dibatalkan.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# --- Fungsi Percakapan BARU untuk Tim Divisi ---
async def start_solved_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Memulai alur penyelesaian, meminta deskripsi."""
    if not update.message.reply_to_message or not update.message.reply_to_message.caption:
        return ConversationHandler.END

    caption_text = update.message.reply_to_message.caption
    complaint_id_match = re.search(r"ID Keluhan: (\w+)", caption_text)
    reporter_id_match = re.search(r"\(ID: (\d+)\)", caption_text)

    if not (complaint_id_match and reporter_id_match):
        return ConversationHandler.END

    # Simpan data yang dibutuhkan untuk langkah selanjutnya
    context.user_data['reporter_id'] = reporter_id_match.group(1)
    context.user_data['complaint_id'] = complaint_id_match.group(1)
    context.user_data['proof_photo_id'] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "Foto bukti penyelesaian diterima. Sekarang, silakan ketik keterangan/deskripsi penyelesaian."
    )
    return GET_RESOLUTION_DESCRIPTION

async def get_resolution_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mengambil deskripsi, mengirim notifikasi lengkap ke pelapor, dan mengakhiri."""
    resolution_description = update.message.text
    
    # Ambil kembali data yang disimpan
    reporter_id = context.user_data['reporter_id']
    complaint_id = context.user_data['complaint_id']
    proof_photo_id = context.user_data['proof_photo_id']

    logger.info(f"Mengirim bukti & deskripsi selesai untuk keluhan {complaint_id} ke pengguna {reporter_id}.")

    try:
        notification_caption = (
            f"Kabar baik! Laporan Anda dengan ID {complaint_id} telah diselesaikan.\n\n"
            f"Keterangan dari tim:\n{resolution_description}"
        )
        await context.bot.send_photo(
            chat_id=reporter_id,
            photo=proof_photo_id,
            caption=notification_caption
        )
        await update.message.reply_text(f"✅ Notifikasi lengkap untuk keluhan ID {complaint_id} telah dikirim ke pelapor.")
    except Exception as e:
        logger.error(f"Gagal mengirim notifikasi 'selesai' lengkap ke {reporter_id}: {e}")
        await update.message.reply_text(f"Gagal mengirim notifikasi ke pelapor. Error: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_solved_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Membatalkan alur penyelesaian."""
    await update.message.reply_text("Proses penyelesaian dibatalkan.")
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Menjalankan bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Handler Percakapan #1: Untuk pengguna yang membuat laporan
    report_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("report", start_report)],
        states={
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
            PHOTO: [MessageHandler(filters.PHOTO, photo), MessageHandler(~filters.PHOTO, photo_invalid)],
            DEPARTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_report)]
        },
        fallbacks=[CommandHandler("batal", cancel_report)],
    )

    # Handler Percakapan #2: Untuk tim divisi yang menyelesaikan laporan
    solved_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO & filters.REPLY & filters.Caption(['/selesai']), start_solved_flow)],
        states={
            GET_RESOLUTION_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_resolution_description)]
        },
        fallbacks=[CommandHandler("batal_selesai", cancel_solved_flow)],
    )

    application.add_handler(report_conv_handler)
    application.add_handler(solved_conv_handler)
    
    print("Bot sedang berjalan dengan alur penyelesaian multi-langkah...")
    application.run_polling()

if __name__ == "__main__":
    main()