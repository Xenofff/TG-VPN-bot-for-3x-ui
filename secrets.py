# -*- coding: utf-8 -*-
# ==============================================================================
# !!! ВАЖНО: КОНФИГУРАЦИОННЫЙ ФАЙЛ С СЕКРЕТНЫМИ ДАННЫМИ !!!
# Заполните все необходимые поля ниже вашими реальными данными.
# ==============================================================================

# --- Telegram Bot ---
BOT_TOKEN = "your_bot_token"  # <-- ЗАПОЛНИТЕ: Получите у @BotFather
ADMIN_USER_ID = 000000000                      # <-- ЗАПОЛНИТЕ: Ваш Telegram User ID для уведомлений об ошибках (0 для отключения)
ADMIN_TELEGRAM_USERNAME = "your_tg_username" # Например, "xenoff" (без @)
INSTRUCTION_LINK = "https://your_link" #Ссылка на гайд по подключению, можно гуглдиск или телеграф

# --- База данных ---
DATABASE_URL = "sqlite:///vpn_bot.db"

# --- Настройки 3x-ui API (для управления VLESS через API) ---
XUI_API_URL = "http://127.0.0.1:port/path" # <-- УКАЖИТЕ ПРАВИЛЬНЫЙ URL ВАШЕЙ ПАНЕЛИ, ЕСЛИ БОТ НА ТОМ ЖЕ СЕРВЕРЕ, ЧТО И ПАНЕЛЬ, ТО ОСТАВЛЯЕМ LOCALHOST, ИНАЧЕ ПРАВИЛЬНЫЙ IP ПАНЕЛИ
XUI_USERNAME = "Login" #  ЛОГИН ОТ ПАНЕЛИ 3x-ui
XUI_PASSWORD = "Password" #  ПАРОЛЬ ОТ ПАНЕЛИ 3x-ui
XUI_SHADOWSOCKS_MASTER_KEY = "Your_secret_key" # МАСТЕР КЛЮЧ ДЛЯ SS
MAX_KEYS_PER_USER = 4 # Максимальное количество ключей на одного пользователя

SERVERS = [
    {
        "id": 1,                          # Уникальный ID сервера
	"name": "VLESS Reality Server",
        "region": "Германия 🚀",     # Название для пользователя
        "ip": "255.255.255.255",      # <-- ВАЖНО: ПУБЛИЧНЫЙ IP-адрес сервера! Не 127.0.0.1!
        "protocols_available": ["vless"], 

        # --- Настройки VLESS через 3x-ui API (Для Reality) ---
        "xui_vless_inbound_id": 1, # ID VLESS INBOUND В ПАНЕЛИ 3x-ui
        "xui_vless_public_key": "your_public_key", #ВАШ ПУБЛИЧНЫЙ КЛЮЧ REALITY
        "xui_vless_sni": "your_sni.com", # SNI ИЗ НАСТРОЕК REALITY
        "xui_vless_short_id": "your_short_id", # SHORT ID ИЗ НАСТРОЕК REALITY
        "xui_vless_flow": "xtls-rprx-vision", 
    },

	# --- Настройки shadowsocks ---
	{
        "id": 2, # ID этого сервера (должен быть уникальным)
        "name": "Shadowsocks Server",
	"region": "Германия 🚀",
        "ip": "255.255.255.255", # Публичный IP сервера Shadowsocks (может быть тем же)

        # Настройки Shadowsocks инбаунда
        "xui_shadowsocks_inbound_id": 2, 
        "xui_shadowsocks_method": "2022-blake3-aes-256-gcm", 
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