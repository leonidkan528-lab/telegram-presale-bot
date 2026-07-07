import asyncio
import logging
import os
import json
import re
import html
from collections import deque
from datetime import datetime
from html import escape as h

import gspread
from gspread.exceptions import WorksheetNotFound

from aiohttp import web

from stack_ai_client import ask_stack_ai

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# =========================================================
# ЛОГИРОВАНИЕ
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("mts_ads_adviser")


# =========================================================
# КОНФИГ
# =========================================================

# ВНИМАНИЕ: по просьбе пользователя секреты здесь оставлены как есть —
# это единственное место в файле, которое сознательно не меняется сейчас.
TOKEN = "7975259132:AAGz94yL-7K-UDOReGNL0yjAzSd8P3L5seE"
ADMIN_ID = 237014151
MTS_LINK_URL = "https://mts.mts-link.ru/j/164981661/18742977822/stream-new/17925578984"

GOOGLE_SHEET_NAME = "Telegram Leads"
ACCESS_WORKSHEET_NAME = "Access"
QUESTIONS_WORKSHEET_NAME = "Questions"
FEEDBACK_WORKSHEET_NAME = "Feedback"
INTERNAL_REQUESTS_WORKSHEET_NAME = "Internal Requests"

BOT_VERSION = "MTS Ads Adviser v0.8 clean Stack AI answers / 2026-07"
START_TIME = datetime.now()

STACK_AI_TIMEOUT_SECONDS = 30

# Сколько последних пар «вопрос-ответ» бот помнит в рамках AI-диалога.
# Контекст сбрасывается по /start или «⬅️ В главное меню».
DIALOG_HISTORY_DEPTH = 3

# Порт для health-check веб-сервера.
# Render передает PORT автоматически; локально будет 8080.
HEALTH_PORT = int(os.getenv("PORT", "8080"))

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден. Добавьте BOT_TOKEN в Render Environment Variables.")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# =========================================================
# ПАМЯТЬ БОТА
# =========================================================

user_states = {}
user_requests = {}
last_ai_answers = {}

# История AI-диалога: user_id -> deque[{"q": вопрос, "a": ответ}]
# Позволяет боту понимать уточнения вида «а сколько это стоит?»
dialog_history = {}

ALLOWED_USERS = {ADMIN_ID}
pending_access_notifications = set()


# =========================================================
# МАТЕРИАЛЫ
# =========================================================

MATERIALS = [
    {
        "title": "Sales Kit Research",
        "path": "materials/sales_kit_research.pdf",
        "caption": "📎 Sales Kit Research — материалы по исследовательским продуктам МТС Ads",
    }
]


# =========================================================
# ПРОДУКТЫ / УСЛУГИ
# =========================================================

services = [
    {
        "name": "Brand Lift",
        "aliases": [
            "brand lift",
            "узнаваемость",
            "запоминаемость",
            "бренд",
            "отношение к бренду",
            "brand",
        ],
        "price": "от 100 000 ₽",
        "time": "до 7 рабочих дней",
        "desc": "исследование, которое показывает, как рекламная кампания повлияла на бренд-метрики: знание, запоминаемость, отношение к бренду, намерение купить.",
        "best_for": "если клиент хочет понять, не только увидели ли рекламу, но и изменилось ли восприятие бренда.",
        "inputs": [
            "период рекламной кампании",
            "целевая аудитория",
            "география",
            "каналы размещения",
            "креативы / форматы",
            "ключевые бренд-метрики для оценки",
        ],
        "client_pitch": "Мы можем оценить, как рекламная кампания повлияла на восприятие бренда: запомнили ли рекламу, выросло ли знание бренда, изменилось ли отношение или намерение купить.",
        "limits": [
            "Brand Lift не измеряет прямые продажи",
            "результат зависит от достаточного объема контактов и корректности вводных",
            "метрики нужно согласовать до старта исследования",
        ],
    },
    {
        "name": "Конверсионный анализ",
        "aliases": [
            "конверсионный анализ",
            "sales lift",
            "конверсии",
            "продажи",
            "заявки",
            "звонки",
            "лиды",
            "cpa",
        ],
        "price": "от 100 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "показывает, привела ли реклама к целевым действиям: продажам, заявкам, звонкам, визитам на сайт или другим событиям.",
        "best_for": "если клиент хочет доказать бизнес-эффект рекламы и связать кампанию с конкретными действиями.",
        "inputs": [
            "период кампании",
            "список каналов размещения",
            "описание целевых действий",
            "CRM / лиды / продажи / события, если применимо",
            "атрибуционное окно",
            "география и аудитория",
        ],
        "client_pitch": "Мы можем оценить, как рекламный контакт связан с целевыми действиями: заявками, продажами, звонками или визитами на сайт. Это помогает понять вклад кампании в бизнес-результат.",
        "limits": [
            "нельзя обещать 100% атрибуцию всех продаж",
            "для части задач нужны клиентские события или CRM-данные",
            "результат зависит от объема данных и корректности матчинга",
        ],
    },
    {
        "name": "Профилирование",
        "aliases": [
            "профилирование",
            "аудитория",
            "соцдем",
            "интересы",
            "портрет аудитории",
            "кто аудитория",
        ],
        "price": "от 185 000 ₽",
        "time": "до 7 рабочих дней",
        "desc": "показывает портрет аудитории: географию, интересы, социально-демографические признаки и поведенческие характеристики.",
        "best_for": "если клиент хочет лучше понять свою аудиторию или проверить гипотезы о целевых сегментах.",
        "inputs": [
            "описание аудитории или источник аудитории",
            "период анализа",
            "география",
            "интересующие признаки",
            "цель анализа",
        ],
        "client_pitch": "Мы можем описать аудиторию клиента: кто эти люди, где они находятся, какие у них интересы и поведенческие особенности. Это помогает точнее планировать коммуникацию и медиаразмещение.",
        "limits": [
            "не раскрываем персональные данные конкретных людей",
            "результаты используются в агрегированном виде",
            "глубина анализа зависит от доступных данных и сегмента",
        ],
    },
    {
        "name": "Анализ конкурентов",
        "aliases": [
            "конкуренты",
            "анализ конкурентов",
            "сравнение",
            "бренды конкурентов",
            "конкурентный анализ",
        ],
        "price": "от 185 000 ₽",
        "time": "до 10 рабочих дней",
        "desc": "помогает сравнить аудиторию клиента с аудиторией конкурентов: пересечения, различия, потенциал роста и особенности сегментов.",
        "best_for": "если клиент хочет понять, чем его аудитория отличается от аудитории конкурентов и где есть потенциал роста.",
        "inputs": [
            "список брендов / конкурентов",
            "география",
            "период анализа",
            "интересующие сегменты",
            "задача сравнения",
        ],
        "client_pitch": "Мы можем сравнить аудиторию бренда с конкурентами: где аудитории пересекаются, чем отличаются и какие сегменты могут быть перспективны для коммуникации.",
        "limits": [
            "результаты зависят от корректного определения конкурентного набора",
            "анализ проводится на агрегированных данных",
            "не подменяет полноценное стратегическое исследование рынка",
        ],
    },
    {
        "name": "Тепловая карта",
        "aliases": [
            "тепловая карта",
            "heatmap",
            "где живет",
            "где работает",
            "места посещения",
            "локации",
            "гео",
        ],
        "price": "от 290 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "показывает, где живет, работает и бывает целевая аудитория. Помогает понять географию спроса и выбрать локации.",
        "best_for": "если нужно выбрать точки, оценить географию аудитории или спланировать наружную рекламу / офлайн-размещение.",
        "inputs": [
            "описание аудитории",
            "география анализа",
            "период",
            "тип локаций",
            "бизнес-задача",
        ],
        "client_pitch": "Мы можем показать, где концентрируется нужная аудитория: где она живет, работает и бывает. Это помогает выбирать локации, планировать офлайн-точки и наружную рекламу.",
        "limits": [
            "данные предоставляются в агрегированном виде",
            "точность зависит от масштаба географии и размера аудитории",
            "нельзя использовать для идентификации конкретных людей",
        ],
    },
    {
        "name": "Аналитика наружной рекламы",
        "aliases": [
            "наружная реклама",
            "наружка",
            "ooh",
            "dooh",
            "билборд",
            "щит",
            "щиты",
            "наружной",
        ],
        "price": "от 175 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "оценивает контакт аудитории с OOH/DOOH-размещением и помогает понять, как наружная реклама сработала после контакта.",
        "best_for": "если клиент размещает наружную рекламу и хочет оценить охват, контакт, доходимость или последующие действия.",
        "inputs": [
            "список поверхностей / адресная программа",
            "период кампании",
            "география",
            "формат размещения",
            "целевая аудитория",
            "целевое действие, если нужно оценивать post-contact эффект",
        ],
        "client_pitch": "Мы можем оценить, какая аудитория контактировала с наружной рекламой и что происходило после контакта: например, были ли визиты в точки или другие целевые действия.",
        "limits": [
            "для оценки нужны корректные данные по поверхностям и периоду",
            "не стоит обещать абсолютную точность контакта каждого пользователя",
            "для оценки бизнес-эффекта могут потребоваться дополнительные события или точки",
        ],
    },
    {
        "name": "ТВ-аналитика",
        "aliases": [
            "тв-аналитика",
            "телевидение",
            "тв аналитика",
            "tv analytics",
            "реклама на тв",
            "телек",
        ],
        "price": "от 290 000 ₽",
        "time": "до 45 рабочих дней",
        "desc": "оценивает охват и эффект после контакта с ТВ-рекламой.",
        "best_for": "если клиент хочет связать ТВ-размещение с аудиторией, охватом или последующими действиями.",
        "inputs": [
            "период ТВ-кампании",
            "медиаплан / размещение",
            "география",
            "целевая аудитория",
            "метрики, которые нужно оценить",
        ],
        "client_pitch": "Мы можем дополнить ТВ-размещение аналитикой: оценить контакт аудитории с кампанией и посмотреть дальнейшие эффекты в зависимости от задачи.",
        "limits": [
            "сроки обычно длиннее, чем у digital-задач",
            "нужны корректные вводные по ТВ-размещению",
            "методологию лучше согласовывать заранее",
        ],
    },
    {
        "name": "Доходимость",
        "aliases": [
            "доходимость",
            "footfall",
            "визиты",
            "посещаемость",
            "дошли до точки",
            "магазины",
            "рестораны",
            "офлайн",
        ],
        "price": "от 250 000 ₽",
        "time": "до 10 рабочих дней",
        "desc": "измеряет, сколько пользователей дошло до офлайн-точки после контакта с рекламой.",
        "best_for": "если у клиента есть магазины, рестораны, офисы продаж, дилерские центры или другие физические точки.",
        "inputs": [
            "адреса офлайн-точек",
            "период кампании",
            "период пост-анализа",
            "каналы размещения",
            "география",
            "логика целевого визита",
        ],
        "client_pitch": "Мы можем оценить, были ли визиты в офлайн-точки после рекламного контакта. Это особенно полезно для ресторанов, ритейла, дилеров, офисов продаж и других точек.",
        "limits": [
            "нужны корректные адреса точек",
            "нужно согласовать окно визита после контакта",
            "не стоит обещать, что каждый визит на 100% вызван рекламой",
        ],
    },
]


# =========================================================
# КЛАВИАТУРЫ
# =========================================================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤖 Задать presale-вопрос")],
        [KeyboardButton(text="🧭 Подобрать решение под клиента")],
        [KeyboardButton(text="📊 Продукты и методологии")],
        [KeyboardButton(text="💬 Как объяснить клиенту"), KeyboardButton(text="❓ Возражения и FAQ")],
        [KeyboardButton(text="🚫 Что нельзя обещать"), KeyboardButton(text="📎 Материалы")],
        [KeyboardButton(text="💰 Цены и сроки"), KeyboardButton(text="🆚 Сравнить продукты")],
        [KeyboardButton(text="📅 Записаться в MTS Link")],
        [KeyboardButton(text="📌 Передать нестандартный запрос")],
    ],
    resize_keyboard=True,
)

materials_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📎 Получить Sales Kit")],
        [KeyboardButton(text="📚 Что внутри материалов")],
        [KeyboardButton(text="⬅️ В главное меню")],
    ],
    resize_keyboard=True,
)

services_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Brand Lift"), KeyboardButton(text="Конверсионный анализ")],
        [KeyboardButton(text="Профилирование"), KeyboardButton(text="Анализ конкурентов")],
        [KeyboardButton(text="Тепловая карта"), KeyboardButton(text="Доходимость")],
        [KeyboardButton(text="Аналитика наружной рекламы")],
        [KeyboardButton(text="ТВ-аналитика")],
        [KeyboardButton(text="⬅️ В главное меню")],
    ],
    resize_keyboard=True,
)

internal_role_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сейлз"), KeyboardButton(text="Аккаунт")],
        [KeyboardButton(text="CSM"), KeyboardButton(text="Аналитик")],
        [KeyboardButton(text="Руководитель"), KeyboardButton(text="Другое")],
        [KeyboardButton(text="❌ Отменить")],
    ],
    resize_keyboard=True,
)

feedback_reason_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Ответ слишком общий")],
        [KeyboardButton(text="Не хватает методологии")],
        [KeyboardButton(text="Не хватает формулировки для клиента")],
        [KeyboardButton(text="Не хватает ограничений")],
        [KeyboardButton(text="Фактологическая ошибка")],
        [KeyboardButton(text="Другое / напишу сам")],
        [KeyboardButton(text="❌ Отменить")],
    ],
    resize_keyboard=True,
)

feedback_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Полезно", callback_data="feedback_good"),
            InlineKeyboardButton(text="👎 Нужна доработка", callback_data="feedback_bad"),
        ],
        [
            InlineKeyboardButton(text="📥 Какие вводные нужны", callback_data="followup_inputs"),
            InlineKeyboardButton(text="💬 Формулировка клиенту", callback_data="followup_pitch"),
        ],
        [
            InlineKeyboardButton(text="🚫 Ограничения", callback_data="followup_limits"),
            InlineKeyboardButton(text="🔄 Переформулировать", callback_data="followup_retry"),
        ],
    ]
)


# =========================================================
# GOOGLE SHEETS (синхронные функции + кеш подключения)
# =========================================================

_gspread_client = None
_spreadsheet_cache = None


def get_google_client():
    google_creds_raw = os.getenv("GOOGLE_CREDENTIALS")

    if not google_creds_raw:
        raise ValueError("GOOGLE_CREDENTIALS не найден в Environment Variables.")

    google_creds = json.loads(google_creds_raw)
    return gspread.service_account_from_dict(google_creds)


def get_spreadsheet(force_reload: bool = False):
    """Кеширует подключение к таблице, чтобы не пересоздавать клиента на каждый запрос."""
    global _gspread_client, _spreadsheet_cache

    if force_reload or _spreadsheet_cache is None:
        _gspread_client = get_google_client()
        _spreadsheet_cache = _gspread_client.open(GOOGLE_SHEET_NAME)

    return _spreadsheet_cache


def _with_spreadsheet_retry(func, *args, **kwargs):
    """Пытается выполнить func(spreadsheet, *args, **kwargs); при ошибке один раз
    переподключается к Google Sheets и повторяет попытку."""
    try:
        spreadsheet = get_spreadsheet()
        return func(spreadsheet, *args, **kwargs)
    except Exception as e:
        logger.warning("Google Sheets call failed, retrying with fresh connection: %s", e)
        spreadsheet = get_spreadsheet(force_reload=True)
        return func(spreadsheet, *args, **kwargs)


def get_or_create_worksheet(spreadsheet, title, headers, rows=1000, cols=20):
    try:
        sheet = spreadsheet.worksheet(title)

        try:
            current_headers = sheet.row_values(1)

            if not current_headers:
                sheet.append_row(headers)
            else:
                updated_headers = current_headers[:]
                changed = False

                for header in headers:
                    if header not in updated_headers:
                        updated_headers.append(header)
                        changed = True

                if changed:
                    sheet.update("A1", [updated_headers])

        except Exception as e:
            logger.warning("Header check error for %s: %s", title, e)

    except WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
        sheet.append_row(headers)

    return sheet


def _get_access_sheet(spreadsheet):
    return get_or_create_worksheet(
        spreadsheet=spreadsheet,
        title=ACCESS_WORKSHEET_NAME,
        headers=[
            "created_at",
            "telegram_id",
            "username",
            "full_name",
            "status",
            "approved_at",
            "approved_by",
            "comment",
        ],
    )


def _get_questions_sheet(spreadsheet):
    return get_or_create_worksheet(
        spreadsheet=spreadsheet,
        title=QUESTIONS_WORKSHEET_NAME,
        headers=[
            "created_at",
            "telegram_id",
            "username",
            "full_name",
            "question",
            "mode",
        ],
    )


def _get_feedback_sheet(spreadsheet):
    return get_or_create_worksheet(
        spreadsheet=spreadsheet,
        title=FEEDBACK_WORKSHEET_NAME,
        headers=[
            "created_at",
            "telegram_id",
            "username",
            "full_name",
            "question",
            "answer_preview",
            "rating",
            "mode",
            "comment",
        ],
    )


def _get_internal_requests_sheet(spreadsheet):
    return get_or_create_worksheet(
        spreadsheet=spreadsheet,
        title=INTERNAL_REQUESTS_WORKSHEET_NAME,
        headers=[
            "created_at",
            "telegram_id",
            "username",
            "name",
            "role",
            "client",
            "task",
            "contact",
        ],
    )


def get_access_sheet():
    return _with_spreadsheet_retry(_get_access_sheet)


def get_questions_sheet():
    return _with_spreadsheet_retry(_get_questions_sheet)


def get_feedback_sheet():
    return _with_spreadsheet_retry(_get_feedback_sheet)


def _log_question_sync(user_id: str, username: str, full_name: str, question: str, mode: str):
    try:
        sheet = get_questions_sheet()
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            username,
            full_name,
            question,
            mode,
        ])
    except Exception as e:
        logger.error("Question log error: %s", e)


def _log_feedback_sync(user_id: int, username: str, full_name: str, rating: str, comment: str = ""):
    try:
        last_answer_data = last_ai_answers.get(user_id, {})

        question = last_answer_data.get("question", "")
        answer = last_answer_data.get("answer", "")
        mode = last_answer_data.get("mode", "")

        answer_preview = answer[:500]

        sheet = get_feedback_sheet()

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(user_id),
            username,
            full_name,
            question,
            answer_preview,
            rating,
            mode,
            comment,
        ])

        return True

    except Exception as e:
        logger.error("Feedback log error: %s", e)
        return False


def _save_internal_request_sync(request_data, username, user_id):
    try:
        spreadsheet = get_spreadsheet()
        sheet = _get_internal_requests_sheet(spreadsheet)

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(user_id),
            username,
            request_data.get("name", ""),
            request_data.get("role", ""),
            request_data.get("client", ""),
            request_data.get("task", ""),
            request_data.get("contact", ""),
        ])

        return "✅ сохранено в Google Sheets"

    except Exception as e:
        logger.error("Internal request Google Sheets error: %s", e)
        return f"⚠️ ошибка Google Sheets: {e}"


def _load_allowed_users_sync():
    allowed = {ADMIN_ID}

    try:
        sheet = get_access_sheet()
        records = sheet.get_all_records()

        for row in records:
            status = str(row.get("status", "")).strip().lower()
            telegram_id = str(row.get("telegram_id", "")).strip()

            if status == "approved" and telegram_id.isdigit():
                allowed.add(int(telegram_id))

    except Exception as e:
        logger.error("Access load error: %s", e)

    return allowed


def _find_access_row_sync(user_id: int):
    sheet = get_access_sheet()
    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):
        telegram_id = str(row.get("telegram_id", "")).strip()

        if telegram_id == str(user_id):
            return sheet, index, row

    return sheet, None, None


def _create_or_update_access_request_sync(user_id: int, username: str, full_name: str):
    try:
        sheet, row_index, existing = _find_access_row_sync(user_id)

        if existing:
            status = str(existing.get("status", "")).strip().lower()

            if status == "approved":
                return "approved"

            if status == "pending":
                return "pending"

            sheet.update_cell(row_index, 5, "pending")
            sheet.update_cell(row_index, 8, "Повторный запрос доступа")
            return "new_pending"

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(user_id),
            username,
            full_name,
            "pending",
            "",
            "",
            "",
        ])

        return "new_pending"

    except Exception as e:
        logger.error("Access request error: %s", e)
        return "error"


def _approve_access_sync(user_id: int, approved_by: int):
    try:
        sheet, row_index, existing = _find_access_row_sync(user_id)

        if not existing:
            return False, "Заявка не найдена"

        sheet.update_cell(row_index, 5, "approved")
        sheet.update_cell(row_index, 6, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        sheet.update_cell(row_index, 7, str(approved_by))

        return True, "Доступ выдан"

    except Exception as e:
        logger.error("Approve access error: %s", e)
        return False, str(e)


def _reject_access_sync(user_id: int, rejected_by: int):
    try:
        sheet, row_index, existing = _find_access_row_sync(user_id)

        if not existing:
            return False, "Заявка не найдена"

        sheet.update_cell(row_index, 5, "rejected")
        sheet.update_cell(row_index, 6, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        sheet.update_cell(row_index, 7, str(rejected_by))

        return True, "Доступ отклонен"

    except Exception as e:
        logger.error("Reject access error: %s", e)
        return False, str(e)


# ---- Асинхронные обёртки поверх синхронных вызовов gspread ----
# Всё, что ходит в Google Sheets, выполняется в отдельном потоке через
# asyncio.to_thread, чтобы не блокировать event loop и остальных пользователей бота.

async def log_question_to_google_sheets(user: types.User, question: str, mode: str):
    username = user.username or "без username"
    full_name = user.full_name or "без имени"

    await asyncio.to_thread(
        _log_question_sync,
        str(user.id),
        username,
        full_name,
        question,
        mode,
    )


async def log_feedback_to_google_sheets(user, rating: str, comment: str = ""):
    username = user.username or "без username"
    full_name = user.full_name or "без имени"

    return await asyncio.to_thread(
        _log_feedback_sync, user.id, username, full_name, rating, comment
    )


async def save_internal_request_to_google_sheets(request_data, username, user_id):
    return await asyncio.to_thread(_save_internal_request_sync, request_data, username, user_id)


async def load_allowed_users_from_sheet():
    return await asyncio.to_thread(_load_allowed_users_sync)


async def create_or_update_access_request(user_id: int, username: str, full_name: str):
    return await asyncio.to_thread(_create_or_update_access_request_sync, user_id, username, full_name)


async def approve_access(user_id: int, approved_by: int):
    success, result_text = await asyncio.to_thread(_approve_access_sync, user_id, approved_by)

    if success:
        ALLOWED_USERS.add(user_id)
        pending_access_notifications.discard(user_id)

    return success, result_text


async def reject_access(user_id: int, rejected_by: int):
    success, result_text = await asyncio.to_thread(_reject_access_sync, user_id, rejected_by)

    if success:
        if user_id in ALLOWED_USERS and user_id != ADMIN_ID:
            ALLOWED_USERS.remove(user_id)
        pending_access_notifications.discard(user_id)

    return success, result_text


# =========================================================
# ДОСТУПЫ
# =========================================================

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS or user_id == ADMIN_ID


async def deny_access(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    full_name = message.from_user.full_name or "без имени"

    request_status = await create_or_update_access_request(
        user_id=user_id,
        username=username,
        full_name=full_name,
    )

    if request_status == "approved":
        ALLOWED_USERS.add(user_id)
        await message.answer(
            "✅ Доступ уже одобрен.\n\n"
            "Напишите /start, чтобы открыть меню."
        )
        return

    if request_status == "error":
        await message.answer(
            "⛔ Доступ к боту открыт только для внутренних сотрудников МТС РТ.\n\n"
            "Не удалось автоматически отправить заявку на доступ. "
            "Передайте администратору ваш Telegram ID:\n\n"
            f"<code>{user_id}</code>",
            parse_mode="HTML",
        )

        try:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ <b>Ошибка при создании заявки на доступ</b>\n\n"
                f"Имя: {h(full_name)}\n"
                f"Username: @{h(username)}\n"
                f"Telegram ID: <code>{user_id}</code>\n\n"
                f"Проверьте Google Sheets / GOOGLE_CREDENTIALS.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Admin notify error: %s", e)

        return

    await message.answer(
        "⛔ Доступ к боту открыт только для внутренних сотрудников МТС РТ.\n\n"
        "Заявка на доступ отправлена администратору. "
        "После одобрения бот автоматически сообщит вам об открытии доступа."
    )

    if request_status == "pending" and user_id in pending_access_notifications:
        return

    pending_access_notifications.add(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"access_approve:{user_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"access_reject:{user_id}",
                ),
            ]
        ]
    )

    try:
        await bot.send_message(
            ADMIN_ID,
            f"🔐 <b>Новая заявка на доступ к боту</b>\n\n"
            f"Имя: {h(full_name)}\n"
            f"Username: @{h(username)}\n"
            f"Telegram ID: <code>{user_id}</code>\n\n"
            f"Одобрить доступ?",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.error("Admin notify error: %s", e)


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def find_service(text: str):
    text_lower = text.lower().strip()

    for service in services:
        if service["name"].lower() == text_lower:
            return service

    # Ищем совпадение алиаса как отдельного слова/фразы, а не произвольной подстроки,
    # чтобы короткие алиасы (например "тв") не матчились внутри других слов.
    for service in services:
        for alias in service["aliases"]:
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text_lower):
                return service

    return None


def suggest_service_from_task(text: str):
    text_lower = text.lower()

    if any(word in text_lower for word in ["наруж", "ooh", "dooh", "щит", "билборд"]):
        return find_service("наружная реклама")

    if any(word in text_lower for word in ["визит", "точк", "магазин", "офлайн", "дошли", "ресторан", "дилер"]):
        return find_service("доходимость")

    if any(word in text_lower for word in ["аудитор", "портрет", "интерес", "соцдем", "кто покупает"]):
        return find_service("профилирование")

    if any(word in text_lower for word in ["продаж", "конверс", "заявк", "звонк", "лиды", "cpa"]):
        return find_service("конверсионный анализ")

    if any(word in text_lower for word in ["бренд", "узнаваем", "запомн", "отношение", "brand"]):
        return find_service("brand lift")

    if any(word in text_lower for word in ["конкурент", "сравнить", "сравнение"]):
        return find_service("анализ конкурентов")

    if any(word in text_lower for word in ["тв", "телевид", "телек"]):
        return find_service("тв-аналитика")

    if any(word in text_lower for word in ["карта", "гео", "локац", "где живет", "где работает"]):
        return find_service("тепловая карта")

    return None


def format_list(items):
    if not items:
        return "— не указано"
    return "\n".join([f"— {item}" for item in items])


def service_card(service):
    return (
        f"📊 <b>{service['name']}</b>\n\n"
        f"<b>Что это:</b>\n"
        f"{service['desc']}\n\n"
        f"<b>Когда предлагать:</b>\n"
        f"{service['best_for']}\n\n"
        f"<b>Что запросить у клиента:</b>\n"
        f"{format_list(service.get('inputs', []))}\n\n"
        f"<b>Как объяснить клиенту:</b>\n"
        f"{service.get('client_pitch', '')}\n\n"
        f"<b>Ограничения:</b>\n"
        f"{format_list(service.get('limits', []))}\n\n"
        f"<b>Ориентир по стоимости:</b> {service['price']}\n"
        f"<b>Ориентир по сроку:</b> {service['time']}\n\n"
        f"⚠️ Цены, сроки и нестандартную методологию лучше дополнительно сверить с ответственным экспертом."
    )


def start_internal_request_flow(user_id):
    user_states[user_id] = "request_name"
    user_requests[user_id] = {}


def build_dialog_context(user_id: int) -> str:
    """Собирает контекст последних вопросов-ответов, чтобы AI понимал уточнения
    вида «а сколько это стоит?» без повторения всей задачи."""
    history = dialog_history.get(user_id)

    if not history:
        return ""

    parts = []
    for item in history:
        q = item.get("q", "")[:400]
        a = item.get("a", "")[:800]
        parts.append(f"Предыдущий вопрос сотрудника: {q}\nТвой предыдущий ответ (сокращенно): {a}")

    return (
        "Контекст текущего диалога (используй его, если новый вопрос — уточнение к предыдущим; "
        "если новый вопрос на другую тему — контекст можно игнорировать):\n"
        + "\n---\n".join(parts)
        + "\n\n"
    )


def remember_dialog(user_id: int, question: str, answer: str):
    history = dialog_history.setdefault(user_id, deque(maxlen=DIALOG_HISTORY_DEPTH))
    history.append({"q": question, "a": answer})


def reset_dialog(user_id: int):
    dialog_history.pop(user_id, None)


def make_presale_prompt(question: str, user_id: int, focus: str = "") -> str:
    focus_instruction = f"{focus}\n" if focus else ""

    return (
        "Ты внутренний presale-ассистент МТС Ads Adviser для сотрудников МТС РТ: сейлзов, аккаунтов, CSM и аналитиков.\n"
        "Отвечай профессионально, структурно и аккуратно. Не выдумывай факты, цены, сроки и кейсы.\n"
        "Если данных недостаточно — честно напиши, какие вводные нужно уточнить.\n"
        "Не вставляй ссылки на источники, номера документов, ID чанков, служебные коды, цитаты в квадратных скобках.\n"
        "Не используй markdown-разметку со звездочками. Пиши обычным чистым текстом для Telegram.\n"
        + focus_instruction
        + (
            ""
            if focus
            else (
                "В ответе желательно использовать структуру:\n"
                "1. Короткий вывод\n"
                "2. Что предложить клиенту\n"
                "3. Какие вводные запросить\n"
                "4. Как объяснить клиенту простыми словами\n"
                "5. Ограничения / что не обещать\n\n"
            )
        )
        + build_dialog_context(user_id)
        + f"Вопрос сотрудника:\n{question}"
    )


def clean_ai_answer(raw_answer: str) -> str:
    """
    Убирает из ответа Stack AI служебные ссылки на источники,
    странные цифровые хвосты, markdown-звездочки и HTML-сущности.
    """
    if not raw_answer:
        return ""

    text = str(raw_answer)

    # Раскодировать HTML-сущности типа &quot;, &#x27; и т.п.
    text = html.unescape(text)

    # Убрать source/citation блоки вида 【...】
    text = re.sub(r"【[^】]*】", "", text)

    # Убрать цифровые ссылки вида 67283.1.0 / 67283:1:0 / ^67283.1.0
    text = re.sub(r"[\[\(\{]?\s*[\^*]?\d{4,}(?:[.:]\d+){1,5}\s*[\]\)\}]?", "", text)

    # Убрать ID вида #67283.1.0
    text = re.sub(r"#\s*\d{4,}(?:[.:]\d+){1,5}", "", text)

    # Убрать явные ссылки на источники вида [source ...], [cite ...], [источник ...]
    text = re.sub(
        r"\[\s*(source|cite|citation|источник|sources|citations)[^\]]*\]",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Убрать markdown-ссылки, оставив только текст
    # [текст](url) -> текст
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Убрать голые URL
    text = re.sub(r"https?://\S+", "", text)

    # Заменить markdown-жирный и курсив на обычный текст
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # Убрать markdown-заголовки
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)

    # Заменить markdown bullets на нормальные точки
    text = re.sub(r"(?m)^\s*[-*]\s+", "• ", text)

    # Убрать лишние служебные символы, которые часто остаются рядом с удаленными ссылками
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)

    # Почистить лишние пробелы и пустые строки
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def format_ai_answer_for_telegram(raw_answer: str) -> str:
    clean_text = clean_ai_answer(raw_answer)

    if not clean_text:
        return "Не удалось подготовить ответ. Попробуйте переформулировать вопрос."

    return clean_text


AI_ANSWER_FOOTER = (
    "\n\n———\n"
    "⚠️ Если вопрос связан с ценой, нестандартной методологией, юридическими ограничениями "
    "или клиентскими данными — лучше дополнительно сверить ответ с ответственным экспертом."
)


async def process_presale_question(
    message: types.Message,
    question: str,
    mode: str,
    focus: str = "",
    user: types.User = None,
):
    """Единая точка обработки presale-вопроса: команда /ai, кнопка меню и follow-up кнопки.

    user передается явно, потому что при вызове из callback-кнопки
    message.from_user — это бот, а не человек."""

    user = user or message.from_user

    await message.answer("⏳ Готовлю presale-ответ...")

    try:
        await log_question_to_google_sheets(user, question, mode)

        raw_answer = await asyncio.wait_for(
            ask_stack_ai(
                user_text=make_presale_prompt(question, user_id=user.id, focus=focus),
                user_id=user.id,
            ),
            timeout=STACK_AI_TIMEOUT_SECONDS,
        )

        answer = format_ai_answer_for_telegram(raw_answer)

        last_ai_answers[user.id] = {
            "question": question,
            "answer": answer,
            "mode": mode,
        }

        remember_dialog(user.id, question, answer)

        await message.answer(
            answer + AI_ANSWER_FOOTER,
            reply_markup=feedback_kb,
        )

    except asyncio.TimeoutError:
        logger.warning("Stack AI timeout for user_id=%s", user.id)
        await message.answer(
            "⚠️ AI-модуль отвечает дольше обычного и не успел ответить вовремя.\n\n"
            "Попробуйте ещё раз чуть позже или передайте вопрос эксперту.",
            reply_markup=main_kb,
        )

    except Exception as e:
        logger.exception("Stack AI error: %s", e)
        await message.answer(
            "⚠️ Не удалось получить ответ от AI-модуля.\n\n"
            "Попробуйте позже или передайте вопрос эксперту.",
            reply_markup=main_kb,
        )


# =========================================================
# CALLBACK: FOLLOW-UP КНОПКИ ПОСЛЕ AI-ОТВЕТА
# =========================================================

FOLLOWUP_FOCUS = {
    "followup_inputs": (
        "Сейчас сотрудник нажал кнопку «Какие вводные нужны». "
        "Дай ТОЛЬКО детальный список вводных, которые нужно запросить у клиента по этой задаче, "
        "с коротким пояснением, зачем нужна каждая вводная. Без остальных разделов."
    ),
    "followup_pitch": (
        "Сейчас сотрудник нажал кнопку «Формулировка клиенту». "
        "Дай ТОЛЬКО готовую формулировку для клиента: 2-4 варианта фраз, которые сейлз может "
        "произнести или написать клиенту дословно. Профессионально, без внутреннего жаргона. Без остальных разделов."
    ),
    "followup_limits": (
        "Сейчас сотрудник нажал кнопку «Ограничения». "
        "Дай ТОЛЬКО список ограничений и того, что нельзя обещать клиенту по этой задаче, "
        "с пояснением, как аккуратно проговорить каждое ограничение. Без остальных разделов."
    ),
    "followup_retry": (
        "Сейчас сотрудник нажал кнопку «Переформулировать»: предыдущий ответ его не устроил. "
        "Ответь на тот же вопрос заново — другими словами, с другой структурой подачи и, если возможно, глубже. "
        "Не повторяй формулировки из предыдущего ответа."
    ),
}


@dp.callback_query(lambda callback: callback.data and callback.data.startswith("followup_"))
async def handle_followup_callback(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    last = last_ai_answers.get(callback.from_user.id)

    if not last or not last.get("question"):
        await callback.answer(
            "Не нашел предыдущий вопрос (возможно, бот перезапускался). Задайте вопрос заново.",
            show_alert=True,
        )
        return

    focus = FOLLOWUP_FOCUS.get(callback.data)

    if not focus:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    await callback.answer("Готовлю уточнение...")

    await process_presale_question(
        callback.message,
        question=last["question"],
        mode=callback.data,
        focus=focus,
        user=callback.from_user,
    )


# =========================================================
# CALLBACK: FEEDBACK
# =========================================================

@dp.callback_query(lambda callback: callback.data and callback.data.startswith("feedback_"))
async def handle_feedback_callback(callback: CallbackQuery):
    if not is_allowed(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    if callback.data == "feedback_good":
        success = await log_feedback_to_google_sheets(
            user=callback.from_user,
            rating="good",
            comment="",
        )

        if success:
            await callback.answer("Спасибо, оценка сохранена")

            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception as e:
                logger.warning("Feedback keyboard remove error: %s", e)

            await callback.message.answer(
                "Спасибо за обратную связь: 👍 Полезно.\n\n"
                "Это поможет улучшать ответы бота для внутренних команд.",
                reply_markup=main_kb,
            )
        else:
            await callback.answer("Не удалось сохранить оценку", show_alert=True)

        return

    if callback.data == "feedback_bad":
        user_states[callback.from_user.id] = "feedback_comment"

        await callback.answer("Уточните, что нужно доработать")

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.warning("Feedback keyboard remove error: %s", e)

        await callback.message.answer(
            "Что именно нужно доработать в ответе?",
            reply_markup=feedback_reason_kb,
        )
        return

    await callback.answer("Некорректная оценка", show_alert=True)


# =========================================================
# CALLBACK: ОДОБРЕНИЕ / ОТКЛОНЕНИЕ ДОСТУПА
# =========================================================

@dp.callback_query(lambda callback: callback.data and callback.data.startswith("access_"))
async def handle_access_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет прав для этого действия", show_alert=True)
        return

    try:
        action, user_id_raw = callback.data.split(":", 1)
        target_user_id = int(user_id_raw)
    except Exception:
        await callback.answer("Некорректная заявка", show_alert=True)
        return

    if action == "access_approve":
        success, result_text = await approve_access(
            user_id=target_user_id,
            approved_by=callback.from_user.id,
        )

        if success:
            await callback.answer("Доступ одобрен")

            await callback.message.edit_text(
                f"✅ <b>Доступ одобрен</b>\n\n"
                f"Telegram ID: <code>{target_user_id}</code>",
                parse_mode="HTML",
            )

            try:
                await bot.send_message(
                    target_user_id,
                    "✅ Вам открыт доступ к внутреннему боту МТС РТ.\n\n"
                    "Напишите /start, чтобы открыть меню.",
                )
            except Exception as e:
                logger.warning("User notify error: %s", e)

        else:
            await callback.answer(f"Ошибка: {result_text}", show_alert=True)

    elif action == "access_reject":
        success, result_text = await reject_access(
            user_id=target_user_id,
            rejected_by=callback.from_user.id,
        )

        if success:
            await callback.answer("Доступ отклонен")

            await callback.message.edit_text(
                f"❌ <b>Доступ отклонен</b>\n\n"
                f"Telegram ID: <code>{target_user_id}</code>",
                parse_mode="HTML",
            )

            try:
                await bot.send_message(
                    target_user_id,
                    "❌ Заявка на доступ к боту отклонена.",
                )
            except Exception as e:
                logger.warning("User notify error: %s", e)

        else:
            await callback.answer(f"Ошибка: {result_text}", show_alert=True)


# =========================================================
# СЛУЖЕБНЫЕ КОМАНДЫ
# =========================================================

@dp.message(Command("myid"))
async def my_id(message: types.Message):
    username = message.from_user.username or "без username"
    full_name = message.from_user.full_name or "без имени"

    await message.answer(
        f"Ваш Telegram ID:\n"
        f"<code>{message.from_user.id}</code>\n\n"
        f"Имя: {h(full_name)}\n"
        f"Username: @{h(username)}",
        parse_mode="HTML",
    )


@dp.message(Command("version"))
async def version(message: types.Message):
    if not is_allowed(message.from_user.id):
        await deny_access(message)
        return

    await message.answer(BOT_VERSION)


@dp.message(Command("status"))
async def status(message: types.Message):
    if not is_allowed(message.from_user.id):
        await deny_access(message)
        return

    uptime = datetime.now() - START_TIME

    try:
        await asyncio.to_thread(get_access_sheet)
        google_status = "✅ Google Sheets подключен"
    except Exception as e:
        google_status = f"⚠️ Google Sheets ошибка: {e}"

    await message.answer(
        "✅ <b>Статус бота</b>\n\n"
        f"Версия: {BOT_VERSION}\n"
        f"Запущен: {START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Время работы: {str(uptime).split('.')[0]}\n"
        f"Пользователей с доступом: {len(ALLOWED_USERS)}\n"
        f"Перезапусков polling: {reliability_stats['polling_restarts']}"
        + (f" (последний: {reliability_stats['last_restart_at']})" if reliability_stats["last_restart_at"] else "")
        + f"\n{google_status}",
        parse_mode="HTML",
    )


@dp.message(Command("ai"))
async def ai_consultant(message: types.Message):
    if not is_allowed(message.from_user.id):
        await deny_access(message)
        return

    question = (message.text or "").replace("/ai", "", 1).strip()

    if not question:
        await message.answer(
            "Напишите вопрос после команды.\n\n"
            "Например:\n"
            "/ai Клиент хочет оценить эффективность наружки, что предложить?"
        )
        return

    await process_presale_question(message, question, mode="command_ai")


# =========================================================
# ОСНОВНОЙ ОБРАБОТЧИК
# =========================================================

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    if not is_allowed(user_id):
        await deny_access(message)
        return

    if text == "❌ Отменить":
        user_states[user_id] = None
        user_requests[user_id] = {}

        await message.answer(
            "Ок, отменил текущий сценарий. Возвращаю в главное меню.",
            reply_markup=main_kb,
        )
        return

    if text == "/start" or text == "⬅️ В главное меню":
        user_states[user_id] = None
        reset_dialog(user_id)

        await message.answer(
            "👋 Привет! Я внутренний presale-ассистент <b>MTS Ads Adviser</b>.\n\n"
            "Помогаю сейлзам, аккаунтам и смежным командам быстро разобраться в продуктах, "
            "подготовиться к клиентской встрече и сформулировать профессиональный ответ клиенту.\n\n"
            "Что можно сделать:\n"
            "🤖 задать presale-вопрос\n"
            "🧭 подобрать решение под задачу клиента\n"
            "📊 посмотреть продукты и методологии\n"
            "💬 получить формулировку для клиента\n"
            "❓ разобрать возражения\n"
            "🚫 проверить, что нельзя обещать\n"
            "📎 получить материалы\n"
            "📌 передать нестандартный запрос эксперту",
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    # =====================================================
    # КОММЕНТАРИЙ К ОТРИЦАТЕЛЬНОЙ ОЦЕНКЕ
    # =====================================================

    if user_states.get(user_id) == "feedback_comment":
        if text == "Другое / напишу сам":
            user_states[user_id] = "feedback_free_comment"

            await message.answer(
                "Напишите коротко, что именно нужно исправить в ответе.",
                reply_markup=main_kb,
            )
            return

        success = await log_feedback_to_google_sheets(
            user=message.from_user,
            rating="bad",
            comment=text,
        )

        if success:
            await message.answer(
                "Спасибо, комментарий сохранен.\n\n"
                "Это поможет улучшить качество ответов бота.",
                reply_markup=main_kb,
            )
        else:
            await message.answer(
                "Не удалось сохранить комментарий в Google Sheets.",
                reply_markup=main_kb,
            )

        user_states[user_id] = None
        return

    if user_states.get(user_id) == "feedback_free_comment":
        success = await log_feedback_to_google_sheets(
            user=message.from_user,
            rating="bad",
            comment=text,
        )

        if success:
            await message.answer(
                "Спасибо, комментарий сохранен.\n\n"
                "Это поможет улучшить качество ответов бота.",
                reply_markup=main_kb,
            )
        else:
            await message.answer(
                "Не удалось сохранить комментарий в Google Sheets.",
                reply_markup=main_kb,
            )

        user_states[user_id] = None
        return

    # =====================================================
    # РЕЖИМ AI-ВОПРОСА
    # =====================================================

    if user_states.get(user_id) == "ai_question":
        user_states[user_id] = None
        await process_presale_question(message, text, mode="button_ai")
        return

    # =====================================================
    # РЕЖИМ ОБЪЯСНЕНИЯ КЛИЕНТУ
    # =====================================================

    if user_states.get(user_id) == "client_explain":
        service = find_service(text) or suggest_service_from_task(text)

        if service:
            await message.answer(
                f"💬 <b>Как объяснить клиенту: {service['name']}</b>\n\n"
                f"{service.get('client_pitch', '')}\n\n"
                f"<b>Какие вводные запросить:</b>\n"
                f"{format_list(service.get('inputs', []))}\n\n"
                f"<b>Аккуратно проговорить ограничения:</b>\n"
                f"{format_list(service.get('limits', []))}",
                parse_mode="HTML",
                reply_markup=main_kb,
            )
        else:
            await message.answer(
                "Не смог точно определить продукт по описанию.\n\n"
                "Лучше нажмите «🤖 Задать presale-вопрос» и опишите клиентскую задачу подробнее.",
                reply_markup=main_kb,
            )

        user_states[user_id] = None
        return

    # =====================================================
    # РЕЖИМ ПОДБОРА ПО ЗАДАЧЕ
    # =====================================================

    if user_states.get(user_id) == "selection":
        suggested = suggest_service_from_task(text)

        if suggested:
            await message.answer(
                "По описанию клиентской задачи больше всего подходит:\n\n"
                + service_card(suggested),
                parse_mode="HTML",
                reply_markup=main_kb,
            )
        else:
            await message.answer(
                "Пока не могу точно подобрать услугу по описанию.\n\n"
                "Рекомендация: нажмите «🤖 Задать presale-вопрос» и опишите задачу подробнее "
                "или передайте нестандартный запрос эксперту.",
                reply_markup=main_kb,
            )

            username = message.from_user.username or "без username"

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"❗ <b>Нераспознанный запрос на подбор услуги</b>\n\n"
                    f"От: @{h(username)}\n"
                    f"Telegram ID: <code>{user_id}</code>\n"
                    f"Текст: {h(text)}",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("Admin notify error: %s", e)

        user_states[user_id] = None
        return

    # =====================================================
    # РЕЖИМ ПЕРЕДАЧИ НЕСТАНДАРТНОГО ЗАПРОСА
    # =====================================================

    if user_states.get(user_id) == "request_name":
        user_requests[user_id]["name"] = text
        user_states[user_id] = "request_role"

        await message.answer(
            "Ваша роль / команда?",
            reply_markup=internal_role_kb,
        )
        return

    if user_states.get(user_id) == "request_role":
        user_requests[user_id]["role"] = text
        user_states[user_id] = "request_client"

        await message.answer(
            "По какому клиенту или категории вопрос?\n\n"
            "Например: автобизнес, банки, ритейл, рестораны, недвижимость, конкретный клиент."
        )
        return

    if user_states.get(user_id) == "request_client":
        user_requests[user_id]["client"] = text
        user_states[user_id] = "request_task"

        await message.answer(
            "Опишите задачу или вопрос, который нужно передать эксперту.\n\n"
            "Чем подробнее вводные, тем быстрее можно будет ответить."
        )
        return

    if user_states.get(user_id) == "request_task":
        user_requests[user_id]["task"] = text
        user_states[user_id] = "request_contact"

        await message.answer(
            "Как с вами удобнее связаться?\n\n"
            "Можно указать Telegram, почту или просто написать «в Telegram»."
        )
        return

    if user_states.get(user_id) == "request_contact":
        user_requests[user_id]["contact"] = text

        username = message.from_user.username or "без username"
        request_data = user_requests[user_id]

        sheet_status = await save_internal_request_to_google_sheets(request_data, username, user_id)

        await message.answer(
            "✅ Запрос передан эксперту.\n\n"
            "Если задача срочная, дополнительно напишите ответственному напрямую.",
            reply_markup=main_kb,
        )

        try:
            await bot.send_message(
                ADMIN_ID,
                f"📌 <b>Нестандартный запрос из внутреннего бота</b>\n\n"
                f"👤 Имя: {h(str(request_data.get('name', '')))}\n"
                f"🧩 Роль: {h(str(request_data.get('role', '')))}\n"
                f"🏢 Клиент / категория: {h(str(request_data.get('client', '')))}\n"
                f"📌 Задача: {h(str(request_data.get('task', '')))}\n"
                f"☎️ Контакт: {h(str(request_data.get('contact', '')))}\n"
                f"🔗 Telegram: @{h(username)}\n"
                f"🧾 Таблица: {sheet_status}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Admin notify error: %s", e)

        user_states[user_id] = None
        user_requests[user_id] = {}
        return

    # =====================================================
    # ГЛАВНОЕ МЕНЮ
    # =====================================================

    if text == "🤖 Задать presale-вопрос":
        user_states[user_id] = "ai_question"

        await message.answer(
            "Напишите вопрос по presale, продуктам, методологии или клиентской задаче.\n\n"
            "Я помню контекст диалога: после ответа можно уточнять прямо текстом — "
            "«а сколько это стоит?», «а какие сроки?» — или нажимать кнопки под ответом.\n\n"
            "Например:\n"
            "— Клиент хочет оценить эффективность наружки, что предложить?\n"
            "— Чем Brand Lift отличается от конверсионного анализа?\n"
            "— Какие вводные нужны для доходимости?\n"
            "— Как объяснить клиенту мультиканальную атрибуцию?",
            reply_markup=main_kb,
        )
        return

    if text == "🧭 Подобрать решение под клиента":
        user_states[user_id] = "selection"

        await message.answer(
            "Опишите клиентскую задачу в одном сообщении.\n\n"
            "Например:\n"
            "— клиент хочет понять, сработала ли наружная реклама\n"
            "— нужно оценить визиты в рестораны после кампании\n"
            "— клиент хочет узнать портрет аудитории\n"
            "— нужно доказать эффект рекламы на продажи",
            reply_markup=main_kb,
        )
        return

    if text == "📊 Продукты и методологии":
        await message.answer(
            "📊 Выберите продукт или методологию:",
            reply_markup=services_kb,
        )
        return

    if text == "💬 Как объяснить клиенту":
        user_states[user_id] = "client_explain"

        await message.answer(
            "Напишите название продукта или коротко опишите задачу клиента.\n\n"
            "Например:\n"
            "— Brand Lift\n"
            "— Доходимость\n"
            "— клиент хочет понять, были ли визиты в магазины после рекламы",
            reply_markup=main_kb,
        )
        return

    if text == "❓ Возражения и FAQ":
        await message.answer(
            "❓ <b>Типовые возражения клиентов и ответы</b>\n\n"
            "<b>1. “Мы не верим, что можно точно оценить эффект рекламы”</b>\n"
            "Корректный ответ: мы не обещаем абсолютную 100% точность, но можем оценить вклад рекламы "
            "через понятную методологию, сравнение групп, анализ контакта с рекламой и последующих действий.\n\n"
            "<b>2. “У нас уже есть Яндекс Метрика / CRM / BI”</b>\n"
            "Это плюс. Клиентские данные могут усилить исследование. Мы можем дополнить их телеком-данными, "
            "геоаналитикой и независимым взглядом на аудиторию.\n\n"
            "<b>3. “Почему так дорого?”</b>\n"
            "Стоимость зависит от объема данных, периода, географии, методологии и сложности отчета. "
            "Важно продавать не таблицу, а управленческий ответ: сработала ли реклама, на кого, где и как.\n\n"
            "<b>4. “Можно ли гарантировать рост продаж?”</b>\n"
            "Нет, гарантировать рост продаж нельзя. Можно оценить влияние кампании на целевые действия "
            "и дать выводы для оптимизации следующих размещений.\n\n"
            "<b>5. “Что нужно для старта?”</b>\n"
            "Минимально: задача клиента, период кампании, каналы, география, аудитория и целевое действие. "
            "Для части задач нужны адреса точек, CRM, лиды или события.",
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    if text == "🚫 Что нельзя обещать":
        await message.answer(
            "🚫 <b>Что нельзя обещать клиенту</b>\n\n"
            "1. Нельзя обещать 100% точную атрибуцию всех продаж.\n\n"
            "2. Нельзя обещать результат без проверки вводных: периода, каналов, географии, объема данных, "
            "точек продаж или событий.\n\n"
            "3. Нельзя обещать персональные данные пользователей или раскрытие конкретных людей.\n\n"
            "4. Нельзя обещать сроки без проверки сложности задачи и доступности данных.\n\n"
            "5. Нельзя обещать нестандартную методологию без согласования с аналитиками.\n\n"
            "6. Нельзя говорить клиенту, что исследование гарантирует рост продаж. "
            "Мы оцениваем эффект и даем выводы, но не управляем всеми факторами бизнеса клиента.\n\n"
            "7. Нельзя подменять Brand Lift конверсионным анализом: это разные задачи. "
            "Brand Lift — про бренд-метрики, конверсионный анализ — про целевые действия.\n\n"
            "8. Нельзя обещать, что геоаналитика покажет конкретных людей. Работаем только с агрегированными данными.",
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    if text == "📎 Материалы":
        await message.answer(
            "📎 Раздел материалов.\n\n"
            "Здесь можно получить Sales Kit и кратко посмотреть, что внутри.",
            reply_markup=materials_kb,
        )
        return

    if text == "📌 Передать нестандартный запрос":
        start_internal_request_flow(user_id)

        await message.answer(
            "Передадим нестандартный запрос эксперту.\n\n"
            "Сначала напишите ваше имя."
        )
        return

    # =====================================================
    # МАТЕРИАЛЫ
    # =====================================================

    if text == "📚 Что внутри материалов":
        await message.answer(
            "📚 <b>Что внутри Sales Kit</b>\n\n"
            "В материалах собраны основные исследовательские продукты МТС Ads:\n\n"
            "• Brand Lift\n"
            "• Конверсионный анализ\n"
            "• Аудиторный анализ\n"
            "• OOH/DOOH-аналитика\n"
            "• ТВ-аналитика\n"
            "• Аналитика блогеров\n"
            "• Кросс-механики\n"
            "• AdHoc-исследования\n\n"
            "Также внутри могут быть описание методологий, примеры задач и база кейсов.",
            parse_mode="HTML",
            reply_markup=materials_kb,
        )
        return

    if text == "📎 Получить Sales Kit":
        await message.answer(
            "📎 Отправляю материалы по исследовательским продуктам МТС Ads.",
            reply_markup=materials_kb,
        )

        for material in MATERIALS:
            try:
                document = FSInputFile(material["path"])
                await message.answer_document(
                    document=document,
                    caption=material["caption"],
                )
            except Exception as e:
                logger.error("Send material error (%s): %s", material["title"], e)
                await message.answer(
                    f"⚠️ Не удалось отправить файл: {material['title']}\n"
                    f"Ошибка: {e}"
                )

        username = message.from_user.username or "без username"

        try:
            await bot.send_message(
                ADMIN_ID,
                f"📎 <b>Пользователь запросил материалы</b>\n\n"
                f"От: @{h(username)}\n"
                f"Telegram ID: <code>{user_id}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Admin notify error: %s", e)

        return

    # =====================================================
    # ДОПОЛНИТЕЛЬНЫЕ РАЗДЕЛЫ
    # =====================================================

    if text == "💰 Цены и сроки":
        msg = (
            "💰 <b>Ориентиры по ценам и срокам</b>\n\n"
            "Важно: это предварительные ориентиры. Перед обещанием клиенту лучше сверить финальные условия.\n\n"
        )

        for service in services:
            msg += f"• <b>{service['name']}</b> — {service['price']}, {service['time']}\n"

        await message.answer(
            msg,
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    if text == "🆚 Сравнить продукты":
        await message.answer(
            "🆚 <b>Короткое сравнение продуктов</b>\n\n"
            "<b>Brand Lift</b> — про бренд-метрики: знание, запоминаемость, отношение, намерение купить.\n\n"
            "<b>Конверсионный анализ</b> — про целевые действия: продажи, заявки, звонки, сайт, лиды.\n\n"
            "<b>Доходимость</b> — про визиты в офлайн-точки после контакта с рекламой.\n\n"
            "<b>Профилирование</b> — про портрет аудитории: соцдем, интересы, география, поведение.\n\n"
            "<b>OOH/DOOH-аналитика</b> — про контакт с наружной рекламой и post-contact эффекты.\n\n"
            "<b>ТВ-аналитика</b> — про контакт с ТВ-размещением и дальнейшую оценку эффекта.\n\n"
            "<b>Тепловая карта</b> — про географию аудитории: где живет, работает и бывает.",
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    if text == "📅 Записаться в MTS Link":
        if MTS_LINK_URL:
            link_text = f"Ссылка на MTS Link:\n{MTS_LINK_URL}"
        else:
            link_text = "Ссылка на MTS Link пока не настроена. Добавьте MTS_LINK_URL в Render Environment."

        await message.answer(
            "📅 <b>Консультация / обсуждение задачи</b>\n\n"
            "Можно использовать MTS Link для разбора нестандартной клиентской задачи.\n\n"
            f"{link_text}",
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    # =====================================================
    # КАРТОЧКИ ПРОДУКТОВ
    # =====================================================

    service = find_service(text)

    if service:
        await message.answer(
            service_card(service),
            parse_mode="HTML",
            reply_markup=main_kb,
        )
        return

    # =====================================================
    # FALLBACK
    # =====================================================

    # Если у пользователя есть активный AI-диалог — любой нераспознанный текст
    # считаем уточнением и продолжаем диалог (работает память контекста).
    # Если диалога нет, но текст похож на осмысленный вопрос — тоже отдаем в AI,
    # чтобы не отправлять человека в тупик.
    if dialog_history.get(user_id):
        await process_presale_question(message, text, mode="dialog_followup")
        return

    if len(text) >= 15:
        await process_presale_question(message, text, mode="fallback_ai")
        return

    await message.answer(
        "Я пока не понял запрос.\n\n"
        "Выберите раздел главного меню или нажмите «🤖 Задать presale-вопрос».",
        reply_markup=main_kb,
    )


# =========================================================
# ЗАПУСК
# =========================================================

# Счетчик перезапусков polling — виден в /status через ссылку на этот dict
reliability_stats = {"polling_restarts": 0, "last_restart_at": None}


async def health_handler(request):
    """Эндпоинт для Render и внешнего мониторинга (UptimeRobot и т.п.).
    Пока он отвечает 200 — бот жив, а бесплатный Render не усыпляет сервис."""
    uptime = datetime.now() - START_TIME
    return web.json_response({
        "status": "ok",
        "version": BOT_VERSION,
        "uptime_seconds": int(uptime.total_seconds()),
        "allowed_users": len(ALLOWED_USERS),
        "polling_restarts": reliability_stats["polling_restarts"],
    })


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=HEALTH_PORT)
    await site.start()

    logger.info("Health-check server started on port %s", HEALTH_PORT)


async def notify_admin_safe(text: str):
    """Отправка сообщения админу, которая никогда не роняет бот сама."""
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.warning("Admin notify error: %s", e)


async def run_polling_forever():
    """Обертка вокруг start_polling: при падении по сетевой или иной ошибке
    бот не умирает, а перезапускает polling с нарастающей паузой (5с → 300с)
    и уведомляет админа о каждом инциденте."""
    delay = 5

    while True:
        try:
            logger.info("Starting polling...")
            await dp.start_polling(bot)
            # start_polling завершился штатно (остановка) — выходим из цикла
            logger.info("Polling stopped normally.")
            break

        except Exception as e:
            reliability_stats["polling_restarts"] += 1
            reliability_stats["last_restart_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.exception("Polling crashed: %s", e)

            await notify_admin_safe(
                f"⚠️ <b>Polling упал и будет перезапущен</b>\n\n"
                f"Ошибка: {h(str(e))[:300]}\n"
                f"Перезапуск через {delay} сек.\n"
                f"Всего перезапусков: {reliability_stats['polling_restarts']}"
            )

            await asyncio.sleep(delay)
            delay = min(delay * 2, 300)


async def main():
    global ALLOWED_USERS

    # Health-check сервер поднимаем первым: Render должен сразу увидеть открытый порт
    await start_health_server()

    ALLOWED_USERS = await load_allowed_users_from_sheet()

    logger.info("Loaded allowed users: %s", ALLOWED_USERS)
    logger.info("Bot version: %s", BOT_VERSION)

    await notify_admin_safe(
        f"🚀 <b>Бот запущен</b>\n\n"
        f"Версия: {BOT_VERSION}\n"
        f"Пользователей с доступом: {len(ALLOWED_USERS)}\n"
        f"Health-check: порт {HEALTH_PORT}"
    )

    await run_polling_forever()


if __name__ == "__main__":
    asyncio.run(main())
