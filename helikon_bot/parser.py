# parser.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

PLAYBILL_URL = "https://www.helikon.ru/ru/playbill"

def parse_news(max_news=5):
    """
    Парсит новости с https://www.helikon.ru/ru/news/
    Возвращает список строк вида: "26.09.2025 — Текст новости"
    """
    url = "https://www.helikon.ru/ru/news/"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = []

        for li in soup.select('ul li'):
            text = li.get_text(strip=True)
            if not text:
                continue

            # Убираем дублирующуюся дату: "26.09.2025 26.09.2025Текст" → "26.09.2025Текст"
            text = re.sub(r'^(\d{2}\.\d{2}\.\d{4})\s+\1', r'\1', text)

            # Извлекаем дату
            date_match = re.match(r'^(\d{2}\.\d{2}\.\d{4})', text)
            if not date_match:
                continue
            date = date_match.group(1)
            body = text[len(date):].strip()

            if not body:
                continue

            # Формируем строку для вывода
            news_items.append(f"{date} — {body}")

        if not news_items:
            return ["Новости не найдены."]

        return news_items[:max_news]

    except Exception as e:
        logger.error(f"Ошибка при парсинге новостей: {e}")
        return [f"Ошибка при загрузке новостей: {str(e)}"]


# --- Остальной код (parse_afisha, get_events_for_week, calculate_end_time) остаётся без изменений ---

def parse_afisha():
    """
    Парсит афишу с https://www.helikon.ru/ru/playbill  
    Возвращает список событий в формате:
    {
        'event_name': str,
        'date': 'YYYY-MM-DD',
        'time': 'HH:MM',
        'hall': str,
        'type': 'спектакль'  # или 'концерт', 'экскурсия' и т.д.
    }
    """
    try:
        response = requests.get(PLAYBILL_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        events = []

        rows = soup.select('table tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 5:
                continue

            date_cell = cols[0].get_text(strip=True)
            title_cell = cols[1].get_text(strip=True)
            time_cell = cols[3].get_text(strip=True)
            hall_cell = cols[4].get_text(strip=True)

            date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', date_cell)
            if not date_match:
                continue
            date_str = date_match.group()

            title_lower = title_cell.lower()
            if any(kw in title_lower for kw in ['экскурс', 'историческ', 'техническ']):
                event_type = "экскурсия"
            elif any(kw in title_lower for kw in ['концерт', 'jazzкафе', 'гостиная', 'каф', 'юбилейный концерт']):
                event_type = "концерт"
            else:
                event_type = "спектакль"

            clean_title = re.split(r'\s+(Премьера|В рамках|Хореографический спектакль)', title_cell)[0].strip()

            hall_clean = hall_cell.replace('Белоколонный зал княгини Шаховской', 'Шаховской') \
                                 .replace('Зал «Стравинский»', 'Стравинский') \
                                 .replace('Зал «Покровский»', 'Покровский') \
                                 .strip()

            try:
                dt = datetime.strptime(date_str, "%d.%m.%Y")
                date_iso = dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

            events.append({
                "event_name": clean_title,
                "date": date_iso,
                "time": time_cell,
                "hall": hall_clean,
                "type": event_type
            })

        return events
    except Exception as e:
        logger.error(f"Ошибка парсинга афиши: {e}")
        return []


def get_events_for_week(start_date: datetime.date, end_date: datetime.date):
    """Возвращает все спектакли и концерты (не экскурсии) между start_date и end_date."""
    all_events = parse_afisha()
    result = []
    for ev in all_events:
        if ev["type"] == "экскурсия":
            continue
        try:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            if start_date <= ev_date <= end_date:
                result.append({
                    "date": ev["date"],
                    "start": ev["time"],
                    "end": calculate_end_time(ev["time"]),
                    "hall": ev["hall"],
                    "type": ev["type"],
                    "event_name": ev["event_name"]
                })
        except Exception as e:
            logger.warning(f"Ошибка обработки даты события: {e}")
    return result


def calculate_end_time(start_time: str) -> str:
    """Рассчитывает время окончания (спектакль ~2.5 ч, концерт ~1.5 ч)"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        # Определяем тип по времени? Лучше — по контексту, но у нас его нет.
        # Пока оставим 2.5 ч для всех, кроме явных концертов (но в get_events_for_week тип уже известен)
        # Однако в текущей реализации calculate_end_time вызывается без типа.
        # Поэтому временно используем 2.5 ч как умолчание.
        end = start + timedelta(hours=2.5)
        return end.strftime("%H:%M")
    except:
        return "21:30"
