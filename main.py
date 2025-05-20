import logging
import telebot
import re
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import os
import json

# Включаем отладку
logging.basicConfig(level=logging.DEBUG)

# Токен Telegram-бота
API_TOKEN = '7793273417:AAEQDFj3MFUaIo9PMKP9jgJpqN4zWvFBvMY'
bot = telebot.TeleBot(API_TOKEN)

# Google Sheets
creds_dict = json.loads(os.environ['GOOGLE_CREDS'])

SPREADSHEET_ID = '18H408uOOG8fgDlUUhSGY1I4viy88x7CNWrbwRS6bp9k'

# Листы
SHEET_XISOB = 'Xisob'
SHEET_BALANCE = 'Balance'

# Подключение к Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet_xisob = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_XISOB)
sheet_balance = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_BALANCE)

# ID групп
GROUP2_CHAT_ID = -  1002181407245 # Balance
GROUP1_CHAT_ID = -1002269282621  # Xisob

# Функции для добавления данных

def find_first_empty_row_xisob(sheet):
    all_values = sheet.get_all_values()
    for i, row in enumerate(all_values, start=1):
        # Проверяем колонки A-D (индексы 0-3)
        # Если в них пусто, возвращаем номер строки (1-based)
        cols_to_check = row[:4] + [''] * (4 - len(row))
        if all(cell.strip() == '' for cell in cols_to_check):
            return i
    return len(all_values) + 1  # Если нет пустых строк, значит новая строка


def append_to_xisob(row_data):
    try:
        row_number = find_first_empty_row_xisob(sheet_xisob)
        # row_data — список из 4 элементов (A, B, C, D)
        # Обновляем диапазон от A до D в найденной строке
        cell_range = f"A{row_number}:D{row_number}"
        sheet_xisob.update(cell_range, [row_data])
    except Exception as e:
        logging.error(f"Ошибка записи в Xisob: {e}")



def append_to_balance(amount, name, card):
    all_data = sheet_balance.get_all_values()
    empty_row = len(all_data) + 1
    row = [''] * 7
    row[0] = datetime.now().strftime("%Y-%m-%d")
    row[2] = str(amount)
    row[5] = name
    row[6] = card
    sheet_balance.insert_row(row, empty_row)

# Обработка сообщений для второй группы (Balance)
@bot.message_handler(func=lambda m: m.chat.id == GROUP2_CHAT_ID)
def handle_group2(m):
    text = m.text.strip()
    if not text.lower().startswith('reg'):
        # Игнорируем сообщения, не начинающиеся с 'Reg'
        logging.debug("Сообщение во второй группе не начинается с 'Reg', игнорируем")
        return

    pattern = r"Reg\s+([\d/]+)\s+paid\s+(\d+)\s*(k)?\s+(Terminal|Naxt|USD|Bank)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        reg_number = match.group(1)
        amount = int(match.group(2))
        if match.group(3):
            amount *= 1000
        payment_type = match.group(4).capitalize()
        date = datetime.now().strftime("%Y-%m-%d")
        row = [date, reg_number, str(amount), payment_type]
        append_to_xisob(row)  # Предполагается, что вторая группа тоже идет в лист Xisob?
        bot.send_message(m.chat.id, "✅ Данные добавлены в лист Xisob.", reply_to_message_id=m.message_id)
    else:
        bot.send_message(m.chat.id, "❌ Неверный формат. Пример: Reg 123/4 paid 500k Terminal", reply_to_message_id=m.message_id)

# Обработка сообщений для первой группы (Xisob)
@bot.message_handler(func=lambda m: m.chat.id == GROUP1_CHAT_ID)
def handle_group1(m):
    logging.debug(f"Group 1 message: {m.text}")
    pattern = r"(\d+)(k)?\s+(\w+)\s+(\w+)"
    match = re.search(pattern, m.text.strip(), re.IGNORECASE)
    if match:
        amount = int(match.group(1))
        if match.group(2):
            amount *= 1000
        name = match.group(3)
        card = match.group(4)
        append_to_balance(amount, name, card)
        bot.send_message(m.chat.id, "✅ Данные добавлены в лист Balance.", reply_to_message_id=m.message_id)
    else:
        # Здесь можно не отправлять сообщение об ошибке, чтобы не спамить чат,
        # либо делать это только если сообщение явно выглядит как попытка ввода данных
        logging.debug("Сообщение не подходит под формат Balance, игнорируем")

print("🤖 Бот запущен и слушает две группы...")
bot.polling(none_stop=True)

