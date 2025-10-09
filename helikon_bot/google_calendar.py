# google_calendar.py
import os
import pickle
import logging  # <-- добавлено
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']  # <-- пробелы убраны

def get_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(service, summary, start_time, end_time, location, description):
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'Europe/Moscow',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Europe/Moscow',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 180},  # за 3 часа
            ],
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event['id']

def delete_calendar_event(service, event_id: str):
    """Удаляет событие из Google Calendar по его ID."""
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
    except Exception as e:
        logging.error(f"Ошибка при удалении события из Google Calendar: {e}")
        raise
