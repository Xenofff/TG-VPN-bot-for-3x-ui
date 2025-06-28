# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import secrets 

def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔑 Получить ключ", callback_data="get_key_button")],
        [InlineKeyboardButton("📄 Мои ключи", callback_data="my_keys")],
        [InlineKeyboardButton("❓ Инструкция по подключению", callback_data="instructions")], # Новая кнопка
        [InlineKeyboardButton("👨‍💻 Связь с администратором", callback_data="contact_admin")], # Новая кнопка
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_menu_keyboard(include_instructions: bool = False) -> InlineKeyboardMarkup:

    keyboard = []
    if include_instructions:
        keyboard.append([InlineKeyboardButton("❓ Инструкция по подключению", callback_data="instructions")])
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def protocol_selection_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⚡ VLESS Reality", callback_data="get_key_vless")],
        [InlineKeyboardButton("👻 Shadowsocks", callback_data="get_key_shadowsocks")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)
