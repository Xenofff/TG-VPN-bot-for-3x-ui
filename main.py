# -*- coding: utf-8 -*-
import logging
import sys
import secrets
from telegram.ext import ApplicationBuilder, Defaults
from telegram import LinkPreviewOptions
from telegram.constants import ParseMode

import db_manager
import bot_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO, 
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("vpn_bot.log", mode='a', encoding='utf-8')
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def main() -> None:
    logger.info("Checking essential configuration...")
    if not secrets.BOT_TOKEN or "YOUR" in secrets.BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set in secrets.py. Bot cannot start.")
        sys.exit(1)
    logger.info("Configuration seems OK.")

    logger.info("Initializing database...")
    try:
        db_manager.init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Setting up Telegram Bot Application...")
    defaults = Defaults(parse_mode=ParseMode.MARKDOWN, link_preview_options=LinkPreviewOptions(is_disabled=True))

    application = (
        ApplicationBuilder()
        .token(secrets.BOT_TOKEN)
        .defaults(defaults)
        .build()
    )

    logger.info("Registering handlers...")
    bot_handlers.register_handlers(application)
    
    logger.info("Starting bot polling...")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot polling stopped by user.")
    except Exception as e:
        logger.critical(f"Bot polling failed with error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete.")

if __name__ == '__main__':
    logger.info("=== VPN Telegram Bot Starting ===")
    main()
    logger.info("=== VPN Telegram Bot Stopped ===")