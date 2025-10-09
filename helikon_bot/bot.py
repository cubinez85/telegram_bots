# bot.py
import logging
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from db import (
    init_db,
    create_or_update_user,
    add_event,
    get_events_for_next_week,
    get_events_for_current_week,
    delete_event  # <-- добавлено
)
from parser import parse_news, get_events_for_week
from google_calendar import get_calendar_service, create_calendar_event, delete_calendar_event  # <-- добавлено delete_calendar_event

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация БД при старте
init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_or_update_user(user_id)
    await update.message.reply_text(
        "Здравствуйте! Я ваш личный менеджер по расписанию. Чем могу помочь?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    text_lower = text.lower()
    user_id = update.effective_user.id
    create_or_update_user(user_id)

    # === Удаление репетиции или спектакля ===
    if ("удалить" in text_lower) and ("репетиц" in text_lower or "спектакл" in text_lower):
        title_match = re.search(r'[«"‘](.+?)[»"’]', text)
        if not title_match:
            await update.message.reply_text(
                "Укажите название спектакля/репетиции в кавычках, например: удалить спектакль «Кармен» 15.10"
            )
            return

        title = title_match.group(1).strip()

        date_match = re.search(r"(\d{1,2})[ .\-](\d{1,2})(?:[ .\-](\d{4}))?", text)
        if not date_match:
            await update.message.reply_text("Укажите дату (например: 15.10)")
            return

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else datetime.now().year

        try:
            event_date = datetime(year, month, day).date()
            date_iso = event_date.strftime("%Y-%m-%d")
        except ValueError:
            await update.message.reply_text("Некорректная дата.")
            return

        # Удаляем из БД и получаем ID события в Google Calendar
        cal_event_id = delete_event(user_id, title, date_iso)

        if not cal_event_id:
            await update.message.reply_text(
                f"Событие «{title}» на {date_iso} не найдено в вашем расписании."
            )
            return

        # Удаляем из Google Calendar
        try:
            service = get_calendar_service()
            delete_calendar_event(service, cal_event_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении из Google Calendar: {e}")
            await update.message.reply_text(
                f"✅ Событие удалено из локального расписания, но не удалось удалить из Google Calendar: {e}"
            )
            return

        await update.message.reply_text(
            f"🗑️ Событие «{title}» на {date_iso} успешно удалено из расписания и Google Calendar."
        )
        return

    # === Ручное добавление репетиции или спектакля по шаблону ===
    if "добавь" in text_lower and ("репетиц" in text_lower or "спектакл" in text_lower):
        title_match = re.search(r'[«"‘](.+?)[»"’]', text)
        if not title_match:
            await update.message.reply_text(
                "Укажите название спектакля в кавычках, например: «В гостях у оперной сказки»"
            )
            return

        title = title_match.group(1).strip()

        date_match = re.search(r"(\d{1,2})[ .\-](\d{1,2})(?:[ .\-](\d{4}))?", text)
        if not date_match:
            await update.message.reply_text("Укажите дату (например: 11 октября или 11.10)")
            return

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else datetime.now().year

        try:
            event_date = datetime(year, month, day).date()
            date_iso = event_date.strftime("%Y-%m-%d")
        except ValueError:
            await update.message.reply_text("Некорректная дата.")
            return

        time_match = re.search(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", text)
        if time_match:
            start_time = time_match.group(1)
            end_time = time_match.group(2)
        else:
            time_match = re.search(r"(\d{1,2}:\d{2})", text)
            if not time_match:
                await update.message.reply_text("Укажите время (например: 12:00–13:00)")
                return
            start_time = time_match.group(1)
            duration = 1.5 if "репетиц" in text_lower else 2.5
            try:
                start_obj = datetime.strptime(start_time, "%H:%M")
                end_obj = start_obj + timedelta(hours=duration)
                end_time = end_obj.strftime("%H:%M")
            except:
                end_time = "13:30" if "репетиц" in text_lower else "21:30"

        hall = "Стравинский"
        if "шаховск" in text_lower:
            hall = "Шаховской"
        elif "покровск" in text_lower:
            hall = "Покровский"

        event_type = "репетиция" if "репетиц" in text_lower else "спектакль"

        try:
            service = get_calendar_service()
        except Exception as e:
            await update.message.reply_text(f"Ошибка подключения к календарю: {e}")
            return

        start_dt_iso = f"{date_iso}T{start_time}:00"
        end_dt_iso = f"{date_iso}T{end_time}:00"
        summary = f"{event_type.capitalize()} «{title}»"
        location = f"Зал {hall}"
        description = "участие в оркестре — фагот"

        try:
            cal_id = create_calendar_event(service, summary, start_dt_iso, end_dt_iso, location, description)
        except Exception as e:
            logger.error(f"Ошибка Google Calendar: {e}")
            cal_id = ""

        add_event(user_id, {
            "event_name": title,
            "date": date_iso,
            "start_time": start_time,
            "end_time": end_time,
            "hall": hall,
            "event_type": event_type,
            "role": "участие в оркестре — фагот",
            "calendar_event_id": cal_id
        })

        await update.message.reply_text(
            f"✅ Записано: {date_iso}, {start_time}–{end_time} — {event_type} «{title}» в зале {hall}.\n"
            "Добавлено в Google Календарь с напоминанием за 3 часа."
        )
        return

    # === Запрос: "Когда я работаю на этой неделе?" (личное расписание) ===
    if "этой неделе" in text_lower and ("работаю" in text_lower or "расписан" in text_lower or "запланировано" in text_lower or "что у меня" in text_lower):
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        local_events = get_events_for_current_week(user_id)
        if local_events:
            reply = "Ваше расписание на этой неделе:\n"
            for ev in local_events:
                reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event']}» в зале {ev['hall']}.\n"
            await update.message.reply_text(reply)
        else:
            site_events = get_events_for_week(start_of_week, end_of_week)
            if site_events:
                context.user_data["pending_events"] = site_events
                reply = "На этой неделе у вас пока нет записей.\n"
                reply += "Но на сайте «Геликон-опера» найдены следующие мероприятия:\n"
                for ev in site_events:
                    reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event_name']}» в зале {ev['hall']}.\n"
                reply += "\nХотите добавить их все в расписание? Напишите «да»."
                await update.message.reply_text(reply)
            else:
                await update.message.reply_text("На этой неделе мероприятий не найдено.")
        return

    # === Запрос: "Какие спектакли в театре на этой неделе?" (общая афиша) ===
    if ("спектакл" in text_lower or "мероприят" in text_lower or "афиш" in text_lower) and "этой неделе" in text_lower:
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        site_events = get_events_for_week(start_of_week, end_of_week)
        if site_events:
            reply = "На этой неделе в театре «Геликон-опера» пройдут следующие мероприятия:\n"
            for ev in site_events:
                reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event_name']}» в зале {ev['hall']}.\n"
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("На этой неделе мероприятий в театре не запланировано.")
        return

    # === Запрос: "Какие спектакли в театре на следующей неделе?" (общая афиша) ===
    if ("спектакл" in text_lower or "мероприят" in text_lower or "афиш" in text_lower) and "следующей неделе" in text_lower:
        today = datetime.now().date()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        end_of_next_week = start_of_next_week + timedelta(days=6)

        site_events = get_events_for_week(start_of_next_week, end_of_next_week)
        if site_events:
            reply = "На следующей неделе в театре «Геликон-опера» пройдут следующие мероприятия:\n"
            for ev in site_events:
                reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event_name']}» в зале {ev['hall']}.\n"
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("На следующей неделе мероприятий в театре не запланировано.")
        return

    # === Запрос: "Что у меня на следующей неделе?" (личное расписание) ===
    if "следующей неделе" in text_lower or ("расписание" in text_lower and "недел" in text_lower):
        today = datetime.now().date()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        end_of_next_week = start_of_next_week + timedelta(days=6)

        local_events = get_events_for_next_week(user_id)
        if local_events:
            reply = "Ваше расписание на следующей неделе:\n"
            for ev in local_events:
                reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event']}» в зале {ev['hall']}.\n"
            await update.message.reply_text(reply)
        else:
            site_events = get_events_for_week(start_of_next_week, end_of_next_week)
            if site_events:
                context.user_data["pending_events"] = site_events
                reply = "На сайте «Геликон-опера» найдены следующие мероприятия:\n"
                for ev in site_events:
                    reply += f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event_name']}» в зале {ev['hall']}.\n"
                reply += "\nХотите добавить их все в расписание? Напишите «да»."
                await update.message.reply_text(reply)
            else:
                await update.message.reply_text("На следующей неделе мероприятий не найдено.")
        return

    # === Подтверждение добавления всего списка ===
    if text_lower in ["да", "добавь"]:
        pending = context.user_data.get("pending_events")
        if not pending:
            await update.message.reply_text("Нет мероприятий для добавления.")
            return

        try:
            service = get_calendar_service()
        except Exception as e:
            await update.message.reply_text(f"Ошибка подключения к календарю: {e}")
            return

        for ev in pending:
            start_dt = f"{ev['date']}T{ev['start']}:00"
            end_dt = f"{ev['date']}T{ev['end']}:00"
            summary = f"{ev['type'].capitalize()} «{ev['event_name']}»"
            location = f"Зал {ev['hall']}"
            description = "участие в оркестре — фагот"

            try:
                cal_id = create_calendar_event(service, summary, start_dt, end_dt, location, description)
            except Exception as e:
                logger.error(f"Ошибка Google Calendar: {e}")
                cal_id = ""

            add_event(user_id, {
                "event_name": ev["event_name"],
                "date": ev["date"],
                "start_time": ev["start"],
                "end_time": ev["end"],
                "hall": ev["hall"],
                "event_type": ev["type"],
                "role": "участие в оркестре — фагот",
                "calendar_event_id": cal_id
            })

        await update.message.reply_text(
            "✅ Записано:\n" +
            "\n".join(
                f"- {ev['date']}, {ev['start']}–{ev['end']} — {ev['type']} «{ev['event_name']}» в зале {ev['hall']}."
                for ev in pending
            ) +
            "\nДобавлено в Google Календарь с напоминанием за 3 часа."
        )
        context.user_data.pop("pending_events", None)
        return

    # === Новости театра ===
    if "новост" in text_lower or "театр" in text_lower:
        news = parse_news()
        if news and "Ошибка" not in news[0]:
            news_text = "\n".join(f"{i+1}. {n}" for i, n in enumerate(news[:5]))
            await update.message.reply_text(f"Новости «Геликон-оперы»:\n{news_text}")
        else:
            await update.message.reply_text("Не удалось загрузить новости. Попробуйте позже.")
        return

    # === Дирижёр ===
    if "дириж" in text_lower:
        conductors = {
            "в гостях у оперной сказки": "Михаил Егиазарьян",
            "маддалена": "Валерий Кирьянов",
            "кармен щедрин": "Феликс Коробов",
            "кармен": "Феликс Коробов",  # версия Бизе — тоже Коробов (по данным театра)
            "алеко": "Феликс Коробов",
            "паяцы": "Тимур Зангиев",
            "борис годунов": "Александр Ведерников",
            "сказки гофмана": "Феликс Коробов",
            "травиата": "Феликс Коробов",
            "тоска": "Феликс Коробов",
            "аида": "Феликс Коробов",
            "ключ на мостовой": "Дмитрий Бертман",
            "золушка": "Феликс Коробов",
            "диалоги кармелиток": "Феликс Коробов",
            "медиум": "Дмитрий Бертман",
            "кофейная кантата": "Дмитрий Бертман",
            "летучая мышь": "Феликс Коробов",
            "свет вифлеемской звезды": "Дмитрий Бертман",
            "новый год в сказочном городе": "Дмитрий Бертман"
        }

        query = text_lower
        for word in ["спектакль", "репетиц", "дириж", "кто", "«", "»", '"', "‘", "’"]:
            query = query.replace(word, "")
        query = query.strip()

        found = None
        for title, conductor in conductors.items():
            if title in query:
                found = (title, conductor)
                break

        if found:
            title, conductor = found
            await update.message.reply_text(f"Дирижёром спектакля «{title.title()}» является {conductor}.")
        else:
            await update.message.reply_text(
                "Уточните, пожалуйста, название спектакля. Например:\n"
                "— Кто дирижёр «В гостях у оперной сказки»?\n"
                "— Кто дирижёр «Маддалены»?"
            )
        return

    # === Уточняющий вопрос ===
    if any(kw in text_lower for kw in ["когда", "во сколько", "какой зал", "что сегодня", "репетиц", "спектакл"]):
        await update.message.reply_text(
            "Уточните, пожалуйста: во сколько начинается мероприятие? Какой спектакль/репетиция? В каком зале проходит: Стравинский или Шаховской?"
        )
        return

    # === По умолчанию ===
    await update.message.reply_text(
        "Я помогаю с расписанием, новостями и информацией о дирижёрах. Например:\n"
        "— Когда я работаю на этой неделе?\n"
        "— Какие спектакли в театре на следующей неделе?\n"
        "— Добавь репетицию «В гостях у оперной сказки» 11.10 с 12:00 до 13:00 в Стравинском\n"
        "— Есть ли новости?\n"
        "— Кто дирижёр «Кармен»?\n"
        "— Удалить спектакль «Кармен» 15.10"
    )

def main():
    TOKEN = "12345****"  # ⚠️ Замените на ваш токен от @BotFather

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
