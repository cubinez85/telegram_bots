# parser.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

PLAYBILL_URL = "https://www.helikon.ru/ru/playbill"
NEWS_URL = "https://www.helikon.ru"

def parse_news():
    """Парсит новости с главной страницы"""
    try:
        response = requests.get(NEWS_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        news_items = soup.select('.news-item')[:5]
        result = []
        for item in news_items:
            text = item.get_text(strip=True)
            if not text:
                continue
            # Убираем дубли даты: "13.08.2025 13.08.2025..." → "13.08.2025 ..."
            match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s+\1(.+)', text)
            if match:
                clean_text = match.group(1) + match.group(2)
            else:
                clean_text = text
            clean_text = clean_text[:120]
            if len(clean_text) > 40 and '.' in clean_text[40:]:
                clean_text = clean_text[:clean_text.find('.', 40) + 1]
            result.append(clean_text)
        return result or ["Новости не найдены."]
    except Exception as e:
        logger.error(f"Ошибка парсинга новостей: {e}")
        return ["Не удалось загрузить новости."]

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

def calculate_end_time(start_time: str, duration_hours=2.5) -> str:
    """Рассчитывает время окончания (спектакль ~2.5 ч, концерт ~1.5 ч)"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        if "концерт" in start_time.lower() or "jazz" in start_time.lower():
            end = start + timedelta(hours=1.5)
        else:
            end = start + timedelta(hours=2.5)
        return end.strftime("%H:%M")
    except:
        return "21:30"
