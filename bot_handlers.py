# -*- coding: utf-8 -*-
import logging
import datetime
import traceback
import secrets
from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    Application
)
from sqlalchemy.orm import Session # pylint: disable=unused-import
import keyboards
import db_manager
import vpn_connector
import os 
import telegram.helpers

logger = logging.getLogger(__name__) 


async def notify_admin(message: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение администратору."""
    if secrets.ADMIN_USER_ID != 0:
        try:
            await context.bot.send_message(chat_id=secrets.ADMIN_USER_ID, text=f"⚠️ Бот-уведомление:\n{message}")
            logger.info("Admin notified.")
        except Exception as e:
            logger.error(f"Failed to notify admin ({secrets.ADMIN_USER_ID}): {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot.")
    
    with db_manager.get_db() as db:
        db_manager.add_user(db, user_id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    
    reply_markup = keyboards.main_menu_keyboard()
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(secrets.WELCOME_MESSAGE, reply_markup=reply_markup)
    else: 
        await update.message.reply_text(secrets.WELCOME_MESSAGE, reply_markup=reply_markup)

# Новая функция для выбора протокола
async def choose_protocol_for_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    keyboard = keyboards.protocol_selection_keyboard()
    await query.edit_message_text(
        "Выберите протокол для нового ключа:",
        reply_markup=keyboard
    )

async def handle_get_key_protocol_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_username = update.effective_user.username
    protocol = query.data.replace("get_key_", "") # Получаем протокол из callback_data

    logger.info(f"User {user_id} ({user_username}) requests a new {protocol} key.")
    
    with db_manager.get_db() as db:
        keys_count = db_manager.count_user_keys(db, user_id)
    
    if keys_count >= secrets.MAX_KEYS_PER_USER:
        logger.warning(f"User {user_id} has reached the key limit ({keys_count} keys).")
        await query.edit_message_text(
            secrets.KEY_LIMIT_REACHED_MESSAGE,
            reply_markup=keyboards.back_to_menu_keyboard()
        )
        return
        
    await query.edit_message_text(f"⏳ Генерирую ваш {protocol.upper()} ключ, пожалуйста, подождите...")
    
    server_config = None
    for s_conf in secrets.SERVERS:
        if protocol == "vless" and "xui_vless_inbound_id" in s_conf:
            server_config = s_conf
            break
        elif protocol == "shadowsocks" and "xui_shadowsocks_inbound_id" in s_conf:
            server_config = s_conf
            break
            
    if not server_config:
        logger.error(f"No suitable server found for protocol {protocol}.")
        await notify_admin(f"Не найден сервер для протокола {protocol} при генерации ключа для пользователя {user_id}.", context)
        await query.edit_message_text(
            secrets.KEY_GENERATION_ERROR,
            reply_markup=keyboards.back_to_menu_keyboard()
        )
        return

    try:
        server_id = server_config['id']
    
        key_data, key_identifier = await vpn_connector.create_key(
            server_id=server_id,
            protocol=protocol, 
            user_telegram_id=user_id,
            user_username=user_username 
        )
        
        if not key_data or not key_identifier:
            logger.error(f"Failed to create {protocol} key for user {user_id}. vpn_connector returned None.")
            await notify_admin(f"Ошибка генерации {protocol.upper()} ключа для пользователя {user_id}. Подробности:\n{secrets.KEY_GENERATION_ERROR}", context) 
            await query.edit_message_text(
                secrets.KEY_GENERATION_ERROR,
                reply_markup=keyboards.back_to_menu_keyboard()
            )
            return
            
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365 * 100) # Ключ действителен 100 лет
        
        with db_manager.get_db() as db:
            db_manager.add_subscription(
                db_session=db,
                user_id=user_id,
                server_id=server_id,
                protocol=protocol, 
                key_data=key_data,
                key_identifier=key_identifier,
                expires_at=expires_at
            )
            keys_count += 1
        
        keys_left = secrets.MAX_KEYS_PER_USER - keys_count
        success_message = secrets.KEY_SUCCESS_MESSAGE.format(key=key_data, keys_left=keys_left)
        
        await query.edit_message_text(
            success_message,
            reply_markup=keyboards.back_to_menu_keyboard(include_instructions=True), 
            parse_mode='Markdown' 
        )
        logger.info(f"Successfully issued {protocol} key to user {user_id}. Total keys: {keys_count}.")

    except Exception as e:
        error_message = f"Critical error in handle_get_key_protocol_selected for user {user_id} and protocol {protocol}: {e}"
        logger.error(error_message, exc_info=True)
        await notify_admin(f"{error_message}\n\nTraceback:\n{traceback.format_exc()}", context)
        await query.edit_message_text(
            secrets.GENERIC_ERROR,
            reply_markup=keyboards.back_to_menu_keyboard()
        )

async def handle_my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие на кнопку 'Мои ключи'."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"User {user_id} requests their key list.")
    
    with db_manager.get_db() as db:
        keys = db_manager.get_user_keys(db, user_id)
        
    if not keys:
        await query.edit_message_text(
            secrets.NO_KEYS_MESSAGE,
            reply_markup=keyboards.back_to_menu_keyboard()
        )
        return
        
    message_text = secrets.MY_KEYS_MESSAGE_HEADER
    for i, key in enumerate(keys, 1):
        created_date = key.created_at.strftime("%Y-%m-%d")
        
        server_info = next((s for s in secrets.SERVERS if s["id"] == key.server_id), None)
        server_name = server_info["name"] if server_info else "Неизвестный сервер"
        server_region = server_info["region"] if server_info and "region" in server_info else "Неизвестный регион"
        message_text += f"**{i}. Протокол: {key.protocol.upper()} ({server_name} - {server_region})**\n" 
        message_text += f"**ID в панели (Email):** `{key.key_identifier}`\n" 
        message_text += f"**Ключ от {created_date}**:\n`{key.key_data}`\n\n"
        
    await query.edit_message_text(
        message_text,
        reply_markup=keyboards.back_to_menu_keyboard(),
        parse_mode='Markdown' 
    )

async def handle_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    instructions_message = f"🔗 **Инструкция по подключению:**\n\nПожалуйста, ознакомьтесь с подробными шагами по настройке VPN на вашем устройстве, перейдя по ссылке:\n\n[Подробная инструкция]({secrets.INSTRUCTION_LINK})\n\n"
    
    await query.edit_message_text(
        instructions_message,
        reply_markup=keyboards.back_to_menu_keyboard(),
        parse_mode='Markdown'
    )
    logger.info(f"User {update.effective_user.id} requested connection instructions.")


async def handle_contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if secrets.ADMIN_TELEGRAM_USERNAME:
        escaped_username = telegram.helpers.escape_markdown(secrets.ADMIN_TELEGRAM_USERNAME, version=2)
        admin_link = f"@{escaped_username}"
        contact_message = (
            f"👨‍💻 **Связь с администратором:**\n\n"
            f"Если у вас возникли вопросы или проблемы, не стесняйтесь связаться с администратором:\n\n"
            f"{admin_link}\n\n"
        )
    else:
        contact_message = "👨‍💻 **Связь с администратором:**\n\nК сожалению, контакт администратора не указан. Пожалуйста, попробуйте позже."

    await query.edit_message_text(
        contact_message,
        reply_markup=keyboards.back_to_menu_keyboard(),
        parse_mode='MarkdownV2' 
    )
    logger.info(f"User {update.effective_user.id} requested to contact admin.")


def register_handlers(application: Application) -> None:
    logger.info("Registering bot handlers...")

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(choose_protocol_for_key, pattern='^get_key_button$')) # Новая кнопка
    application.add_handler(CallbackQueryHandler(handle_get_key_protocol_selected, pattern='^get_key_vless$'))
    application.add_handler(CallbackQueryHandler(handle_get_key_protocol_selected, pattern='^get_key_shadowsocks$')) 
    application.add_handler(CallbackQueryHandler(handle_my_keys, pattern='^my_keys$'))
    application.add_handler(CallbackQueryHandler(start_command, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(handle_instructions, pattern='^instructions$'))
    application.add_handler(CallbackQueryHandler(handle_contact_admin, pattern='^contact_admin$'))

    logger.info("Handlers registered.")
