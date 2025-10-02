# bot.py
import logging
from telebot import TeleBot, types

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Инициализация бота
TOKEN = '123456789*****'
bot = TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, f'Привет, {message.chat.first_name}!')

    try:
        with open('./static/1.PNG', 'rb') as sticker:
            bot.send_sticker(message.chat.id, sticker)
    except FileNotFoundError:
        logging.error("Стикер не найден")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Кнопка")
    markup.add(item1)
    bot.send_message(message.chat.id, 'Для регистрации на сайте нажмите на Кнопку, далее на ссылку', reply_markup=markup)

@bot.message_handler(content_types=['text'])
def message_reply(message):
    if message.text == "Кнопка":
        bot.send_message(message.chat.id, "https://flask.cubinez.ru")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item2 = types.KeyboardButton("Кнопка 2")
        markup.add(item2)
        bot.send_message(message.chat.id, 'Нажмите на Кнопку 2', reply_markup=markup)
    elif message.text == "Кнопка 2":
        bot.send_message(message.chat.id, 'Спасибо за регистрацию!')

def main():
    bot.infinity_polling()

if __name__ == '__main__':
    main()