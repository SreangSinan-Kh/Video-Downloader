import os
import logging
import yt_dlp
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
from flask import Flask, request

# --- 1. ការកំណត់ Environment Variables និង Constants ---

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# អាន​ទិន្នន័យ​សម្ងាត់​ពី Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = f"https://YOUR_RENDER_SERVICE_NAME.onrender.com/{BOT_TOKEN}"
SECRET = os.environ.get("WEBHOOK_SECRET", "default_secret_key") # គួរ​ប្រើ​តម្លៃ​ពិត
PORT = int(os.environ.get("PORT", 10000))
DOWNLOAD_PATH = "/tmp/%(title)s.%(ext)s" # ផ្លាស់ប្តូរ​ទៅ​ជា​ឈ្មោះ​ឯកសារ​ឌីណាមិក

# --- 2. មុខងារ Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    await update.message.reply_text(
        "👋 សួស្តី! ខ្ញុំជា Bot ទាញយកវីដេអូទំនើប។\n\n"
        "សូមផ្ញើ **Link (URL)** វីដេអូណាមួយ (YouTube, Facebook, TikTok ។ល។) មកខ្ញុំ ដើម្បីចាប់ផ្តើម។\n\n"
        "ប្រើ /help ដើម្បីមើលព័ត៌មានបន្ថែម។"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    await update.message.reply_text(
        "ℹ️ **មុខងារ​របស់​ Bot**:\n"
        "1. ផ្ញើ URL វីដេអូ => Bot នឹង​សួរ​រក​គុណភាព។\n"
        "2. ជ្រើសរើស​គុណភាព (MP4 720p, MP4 1080p, ឬ MP3)។\n"
        "3. ទាញ​យក​និង​បង្ហោះ​ត្រឡប់​មកវិញ។\n\n"
        "🚨 **កំណត់​សម្គាល់**: វីដេអូ​ដែល​មាន​ទំហំ​ធំ​ពេក​អាច​នឹង​បរាជ័យ​ក្នុង​ការ​បង្ហោះ​ទៅ Telegram។"
    )

# --- 3. មុខងារ​ទាញយក​និង​ឆ្លើយតប ---

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the URL and asks the user to select quality."""
    url = update.message.text
    
    # រក្សាទុក URL ក្នុង user_data ដើម្បី​ប្រើ​ពេល Callback
    context.user_data['url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 វីដេអូ (720p)", callback_data='dl_720'),
            InlineKeyboardButton("🎞️ វីដេអូ (1080p)", callback_data='dl_1080')
        ],
        [
            InlineKeyboardButton("🎧 តែ​សំឡេង (MP3)", callback_data='dl_mp3'),
            InlineKeyboardButton("❌ បោះបង់", callback_data='dl_cancel')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ សូម​ជ្រើសរើស​គុណភាព​ទាញយក​សម្រាប់ Link នេះ៖", 
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user's quality selection from the inline keyboard."""
    query = update.callback_query
    await query.answer() # បិទ​ការ​រង់ចាំ
    
    choice = query.data
    chat_id = query.message.chat_id
    
    if choice == 'dl_cancel':
        await query.edit_message_text(text="🚫 ប្រតិបត្តិការ​ទាញយក​ត្រូវ​បាន​បោះបង់។")
        return
        
    # ពិនិត្យ​មើល URL ដែល​បាន​រក្សាទុក
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text(text="⚠️ កំហុស៖ មិន​មាន URL ក្នុង​ប្រព័ន្ធ។")
        return

    await query.edit_message_text(text="🚀 កំពុង​ដំណើរការ​ទាញយក... សូម​រង់ចាំ!")
    
    # កំណត់ Options សម្រាប់ yt-dlp តាម​ជម្រើស
    if choice == 'dl_mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': '/tmp/%(title)s.mp3',
            'verbose': True
        }
        output_path = '/tmp/' # ផ្លាស់ប្តូរ​ដោយ​ផ្អែកលើ info
        file_type = 'audio'
        caption = "✅ ទាញយក​តែ​សំឡេង (MP3) រួចរាល់!"
    elif choice == 'dl_1080':
        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', # ព្យាយាម 1080p
            'outtmpl': DOWNLOAD_PATH,
            'merge_output_format': 'mp4',
            'verbose': True
        }
        output_path = '/tmp/' # ផ្លាស់ប្តូរ​ដោយ​ផ្អែកលើ info
        file_type = 'video'
        caption = "✅ ទាញយក​វីដេអូ (1080p) រួចរាល់!"
    else: # dl_720
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]', # ព្យាយាម 720p
            'outtmpl': DOWNLOAD_PATH,
            'merge_output_format': 'mp4',
            'verbose': True
        }
        output_path = '/tmp/' # ផ្លាស់ប្តូរ​ដោយ​ផ្អែកលើ info
        file_type = 'video'
        caption = "✅ ទាញយក​វីដេអូ (720p) រួចរាល់!"


    try:
        # ជំហាន​ទាញយក
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # កំណត់​ផ្លូវ​ឯកសារ​ចុងក្រោយ
            final_path = ydl.prepare_filename(info)
            # បើ​ជា MP3
            if choice == 'dl_mp3':
                final_path = final_path.rsplit('.', 1)[0] + '.mp3'


        # ជំហាន​ផ្ញើ​ឯកសារ
        if os.path.exists(final_path):
            await query.message.reply_chat_action(action=file_type.upper()) # បង្ហាញ​ថា​ Bot កំពុង​បង្ហោះ

            if file_type == 'video':
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=open(final_path, 'rb'),
                    supports_streaming=True,
                    caption=caption
                )
            else:
                await context.bot.send_audio(
                    chat_id=chat_id, 
                    audio=open(final_path, 'rb'),
                    caption=caption
                )
            
            await query.edit_message_text(text="🎉 ប្រតិបត្តិការ​ចប់​សព្វគ្រប់!")
        else:
            await query.edit_message_text(text="❌ ទាញយក​មិន​បាន​ជោគជ័យ។ (ឯកសារ​មិន​មាន)")
            
    except Exception as e:
        logger.error(f"Download or Upload Error: {e}")
        await query.edit_message_text(text=f"❌ មាន​កំហុស​ទូទៅ​ក្នុង​ការ​ទាញយក៖ {e}")
        
    finally:
        # ជំហាន​សម្អាត​ឯកសារ (សំខាន់​បំផុត!)
        if os.path.exists(final_path):
            os.remove(final_path)
            logger.info(f"Cleaned up file: {final_path}")

# --- 4. ការកំណត់រចនាសម្ព័ន្ធ Flask និង Webhook ---

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# បន្ថែម Handlers
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_message))
application.add_handler(CallbackQueryHandler(button_callback))


# កំណត់ Webhook Endpoint សម្រាប់​ទទួល​សារ​ពី Telegram
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_handler():
    # ពិនិត្យ Secret Token
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        return "Invalid Secret Token", 403
    
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return "ok"

# Route សាមញ្ញ​សម្រាប់​ត្រួតពិនិត្យ Health Check
@app.route("/")
def index():
    return "Bot is running!"

# ចាប់ផ្តើម​កំណត់ Webhook ពេល Server ចាប់ផ្តើម​ដំបូង
if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set.")
    else:
        try:
            # កំណត់ Webhook ទៅ​កាន់ Telegram
            application.bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=SECRET
            )
            logger.info(f"Webhook set to: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")

    # ដំណើរការ Flask App ដោយ​ប្រើ Gunicorn នៅ​ពេល​ដាក់​ពង្រាយ
    app.run(host="0.0.0.0", port=PORT)
