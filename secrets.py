# -*- coding: utf-8 -*-
# ==============================================================================
# !!! ВАЖНО: КОНФИГУРАЦИОННЫЙ ФАЙЛ С СЕКРЕТНЫМИ ДАННЫМИ !!!
# Заполните все необходимые поля ниже вашими реальными данными.
# ==============================================================================

# --- Telegram Bot ---
BOT_TOKEN = "7852232714:AAHv10klHOS9IsJ1pT3kA9ZPosuOJeNB1-M"  # <-- ЗАПОЛНИТЕ: Получите у @BotFather
ADMIN_USER_ID = 362529336                      # <-- ЗАПОЛНИТЕ: Ваш Telegram User ID для уведомлений об ошибках (0 для отключения)
ADMIN_TELEGRAM_USERNAME = "Rias_Gremori" # Например, "xenoff" (без @)
INSTRUCTION_LINK = "https://docs.google.com/document/d/1Cyzob_TdaVcXX0mxyvyhVFY_Dhk5-9I8b4DHnAvjwjg/edit?usp=sharing"

# --- База данных ---
DATABASE_URL = "sqlite:///vpn_bot.db"

# --- Настройки 3x-ui API (для управления VLESS через API) ---
# Панель находится на том же сервере, поэтому используем localhost
# ВАЖНО: Укажите ваш порт и уникальный путь к панели, если они отличаются
XUI_API_URL = "http://ip:port/path" # <-- УКАЖИТЕ ПРАВИЛЬНЫЙ URL ВАШЕЙ ПАНЕЛИ
XUI_USERNAME = "username" # <-- ЗАПОЛНИТЕ: ВАШ ЛОГИН ОТ ПАНЕЛИ 3x-ui
XUI_PASSWORD = "password" # <-- ЗАПОЛНИТЕ: ВАШ ПАРОЛЬ ОТ ПАНЕЛИ 3x-ui

# --- Лимит ключей ---
MAX_KEYS_PER_USER = 4 # Максимальное количество ключей на одного пользователя

# --- Серверы VPN ---
SERVERS = [
    {
        "id": 1,                          # Уникальный ID сервера
        "name": "VLESS Reality Server",
        "region": "Германия 🚀",     # Название для пользователя
        "ip": "255.255.255.255",      # <-- ВАЖНО: ВАШ ПУБЛИЧНЫЙ IP-адрес сервера! Не 127.0.0.1!
        "protocols_available": ["vless"], # Оставляем только VLESS

        # --- Настройки VLESS через 3x-ui API (Для Reality) ---
        "xui_vless_inbound_id": 1, # ID ВАШЕГО VLESS INBOUND В ПАНЕЛИ 3x-ui
        "xui_vless_public_key": "S0zzIyqEjjI7c_Uqt8jWB5I2NF-7728TUp_4e9G4iXY", # ВАШ ПУБЛИЧНЫЙ КЛЮЧ REALITY
        "xui_vless_sni": "wikiportal.su", # SNI ИЗ НАСТРОЕК REALITY
        "xui_vless_short_id": "c17ec0dffa", # SHORT ID ИЗ НАСТРОЕК REALITY
        "xui_vless_flow": "xtls-rprx-vision", # Опционально, если flow нужен в ссылке
    },

	# --- Настройки shadowsocks ---
	{
        "id": 2,
        "name": "Shadowsocks Server",
        "region": "Германия 🚀",
        "ip": "255.255.255.255", # Публичный IP вашего сервера Shadowsocks (может быть тем же)
        "xui_shadowsocks_inbound_id": 2, # ID Shadowsocks инбаунда в панели 3x-ui (индекс 2 в вашем config.json)
        "xui_shadowsocks_method": "2022-blake3-aes-256-gcm", # Метод шифрования Shadowsocks из config.json
    }
]

# --- Тексты сообщений ---
WELCOME_MESSAGE = "👋 Добро пожаловать!\n\nНажмите кнопку, чтобы получить ключ доступа."
MY_KEYS_MESSAGE_HEADER = "📄 **Ваши активные ключи:**\n\n"
NO_KEYS_MESSAGE = "У вас пока нет ключей. Нажмите 'Получить ключ', чтобы создать первый."
KEY_SUCCESS_MESSAGE = (
    "✅ Ваш новый ключ готов!\n\n"
    "Скопируйте ключ и добавьте его в ваше приложение:\n\n"
    "`{key}`\n\n"
    "Вы можете получить еще {keys_left} ключ(а/ей)."
)
KEY_LIMIT_REACHED_MESSAGE = "Превышен лимит ключей на одного пользователя. Для получения дополнительных ключей свяжитесь с администратором."
GENERIC_ERROR = "Произошла ошибка. Попробуйте позже или свяжитесь с администратором."
KEY_GENERATION_ERROR = "Произошла ошибка при автоматической генерации ключа. Мы уже уведомили администратора. Пожалуйста, попробуйте еще раз через некоторое время или свяжитесь с ним напрямую."

# --- Проверки конфигурации ---
if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN": print("!!! WARNING: BOT_TOKEN is not set in secrets.py !!!")
if not SERVERS or SERVERS[0].get("ip") == "YOUR_SERVER_PUBLIC_IP": print("!!! WARNING: Public IP for the server is not configured in secrets.py !!!")
if not XUI_USERNAME or XUI_USERNAME == "your_3xui_username": print("!!! WARNING: XUI_USERNAME is not configured in secrets.py !!!")