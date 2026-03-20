import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from app.core.config import settings

logger = logging.getLogger(__name__)
MINI_APP_URL = "https://your-frontend.up.railway.app"  # Replace with real URL

application = None

def build_application() -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    return app

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referral_code = args[0] if args else None
    ref_param = f"?ref={referral_code}" if referral_code else ""
    keyboard = [[InlineKeyboardButton("⚡ Open ShillForge", web_app=WebAppInfo(url=f"{MINI_APP_URL}{ref_param}"))],
                [InlineKeyboardButton("📣 Join Channel", url="https://t.me/ShillForge_Official"),
                 InlineKeyboardButton("𝕏 Follow Twitter", url="https://twitter.com/ShillForge")]]
    await update.message.reply_text(
        f"🚀 *Welcome to ShillForge, {user.first_name}!*\n\nTap. Earn. Dominate.\n\n"
        f"{'✅ Referral applied: ' + referral_code if referral_code else '👇 Tap to start!'}",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔧 *ShillForge Commands*\n\n/start — Launch the Mini App\n/help — Show this message",
        parse_mode="Markdown")

async def send_notification(telegram_id: int, message: str):
    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=telegram_id, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Failed to notify {telegram_id}: {e}")

async def start_bot():
    global application
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("No TELEGRAM_BOT_TOKEN set, bot disabled")
        return
    application = build_application()
    logger.info("🤖 ShillForge Bot starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

async def stop_bot():
    global application
    if application:
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("🤖 Bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    standalone = build_application()
    standalone.run_polling(allowed_updates=Update.ALL_TYPES)
