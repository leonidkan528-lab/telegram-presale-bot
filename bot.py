import asyncio
import os
import json
from datetime import datetime
from stack_ai_client import ask_stack_ai
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command


TOKEN = "7975259132:AAHa5mxmASaF1-qfKjiOJvwfubCmbQ-2BKU"
ADMIN_ID = 237014151

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден. Добавьте BOT_TOKEN в Render Environment Variables.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_states = {}
user_leads = {}

MTS_LINK_URL = "https://mts.mts-link.ru/j/164981661/18742977822/stream-new/17925578984"
GOOGLE_SHEET_NAME = "Telegram Leads"

MATERIALS = [
    {
        "title": "Sales Kit Research",
        "path": "materials/sales_kit_research.pdf",
        "caption": "📎 Sales Kit Research — материалы по исследовательским продуктам МТС Ads"
    }
]


services = [
    {
        "name": "Brand Lift",
        "aliases": ["brand lift", "узнаваемость", "запоминаемость", "бренд", "отношение к бренду"],
        "price": "от 100 000 ₽",
        "time": "до 7 рабочих дней",
        "desc": "помогает понять, запомнили ли рекламу и изменилось ли отношение к бренду.",
        "best_for": "если нужно оценить эффект рекламы на знание бренда, запоминаемость и намерение купить."
    },
    {
        "name": "Конверсионный анализ",
        "aliases": ["конверсионный анализ", "sales lift", "конверсии", "продажи", "заявки", "звонки"],
        "price": "от 100 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "показывает, привела ли реклама к целевым действиям: продажам, звонкам, заявкам или визитам на сайт.",
        "best_for": "если нужно доказать бизнес-эффект рекламы."
    },
    {
        "name": "Профилирование",
        "aliases": ["профилирование", "аудитория", "соцдем", "интересы", "портрет аудитории"],
        "price": "от 185 000 ₽",
        "time": "до 7 рабочих дней",
        "desc": "показывает портрет аудитории: географию, интересы, социально-демографические признаки.",
        "best_for": "если нужно лучше понять, кто ваша аудитория."
    },
    {
        "name": "Анализ конкурентов",
        "aliases": ["конкуренты", "анализ конкурентов", "сравнение", "бренды конкурентов"],
        "price": "от 185 000 ₽",
        "time": "до 10 рабочих дней",
        "desc": "помогает сравнить вашу аудиторию с аудиторией конкурентов.",
        "best_for": "если нужно понять пересечения, различия и потенциал роста относительно конкурентов."
    },
    {
        "name": "Тепловая карта",
        "aliases": ["тепловая карта", "heatmap", "где живет", "где работает", "места посещения"],
        "price": "от 290 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "показывает, где живёт, работает и бывает целевая аудитория.",
        "best_for": "если нужно выбрать локации, оценить географию спроса или спланировать размещение."
    },
    {
        "name": "Аналитика наружной рекламы",
        "aliases": ["наружная реклама", "наружка", "ooh", "dooh", "билборд", "щит"],
        "price": "от 175 000 ₽",
        "time": "до 14 рабочих дней",
        "desc": "оценивает контакт аудитории с наружной рекламой и дальнейшие целевые действия.",
        "best_for": "если нужно понять эффективность OOH/DOOH-размещений."
    },
    {
        "name": "ТВ-аналитика",
        "aliases": ["тв", "телевидение", "тв аналитика", "tv analytics", "реклама на тв"],
        "price": "от 290 000 ₽",
        "time": "до 45 рабочих дней",
        "desc": "оценивает охват и эффект после контакта с ТВ-рекламой.",
        "best_for": "если нужно связать ТВ-размещение с аудиторией или бизнес-результатом."
    },
    {
        "name": "Доходимость",
        "aliases": ["доходимость", "footfall", "визиты", "посещаемость", "дошли до точки"],
        "price": "от 250 000 ₽",
        "time": "до 10 рабочих дней",
        "desc": "измеряет, сколько пользователей дошло до офлайн-точки после контакта с рекламой.",
        "best_for": "если есть магазины, офисы, дилерские центры, рестораны или другие физические точки."
    }
]


main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Подобрать решение")],
        [KeyboardButton(text="📎 Материалы"), KeyboardButton(text="📅 Консультация")],
        [KeyboardButton(text="📝 Оставить заявку")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

solution_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧭 Подбор по задаче")],
        [KeyboardButton(text="📊 Все услуги"), KeyboardButton(text="💰 Цены и сроки")],
        [KeyboardButton(text="🆚 Сравнить продукты"), KeyboardButton(text="❓ FAQ по продуктам")],
        [KeyboardButton(text="⬅️ В главное меню")]
    ],
    resize_keyboard=True
)

materials_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📎 Получить Sales Kit")],
        [KeyboardButton(text="📚 Что внутри материалов")],
        [KeyboardButton(text="⬅️ В главное меню")]
    ],
    resize_keyboard=True
)

consultation_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Записаться в MTS Link")],
        [KeyboardButton(text="📝 Передать задачу заранее")],
        [KeyboardButton(text="⬅️ В главное меню")]
    ],
    resize_keyboard=True
)

help_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚙️ Как проходит исследование")],
        [KeyboardButton(text="❓ Частые вопросы")],
        [KeyboardButton(text="👨‍💼 Связаться с менеджером")],
        [KeyboardButton(text="⬅️ В главное меню")]
    ],
    resize_keyboard=True
)

services_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Brand Lift"), KeyboardButton(text="Конверсионный анализ")],
        [KeyboardButton(text="Профилирование"), KeyboardButton(text="Анализ конкурентов")],
        [KeyboardButton(text="Тепловая карта"), KeyboardButton(text="Доходимость")],
        [KeyboardButton(text="Аналитика наружной рекламы")],
        [KeyboardButton(text="ТВ-аналитика")],
        [KeyboardButton(text="⬅️ В главное меню")]
    ],
    resize_keyboard=True
)

role_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏢 Рекламодатель")],
        [KeyboardButton(text="🤝 Агентство")],
        [KeyboardButton(text="📈 Маркетолог")],
        [KeyboardButton(text="📊 Аналитик")],
        [KeyboardButton(text="❓ Другое")],
        [KeyboardButton(text="❌ Отменить")]
    ],
    resize_keyboard=True
)

interest_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Доходимость")],
        [KeyboardButton(text="📊 Brand Lift")],
        [KeyboardButton(text="📈 Конверсионный анализ")],
        [KeyboardButton(text="🎯 Профилирование")],
        [KeyboardButton(text="🏙 Наружная реклама")],
        [KeyboardButton(text="📺 ТВ-аналитика")],
        [KeyboardButton(text="🤔 Пока не знаю")],
        [KeyboardButton(text="❌ Отменить")]
    ],
    resize_keyboard=True
)


def save_lead_to_google_sheets(lead, username, user_id):
    try:
        google_creds_raw = os.getenv("GOOGLE_CREDENTIALS")

        if not google_creds_raw:
            return "⚠️ GOOGLE_CREDENTIALS не найден в Render Environment"

        google_creds = json.loads(google_creds_raw)

        gc = gspread.service_account_from_dict(google_creds)
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lead.get("name", ""),
            lead.get("company", ""),
            lead.get("role", ""),
            lead.get("interest", ""),
            lead.get("task", ""),
            lead.get("contact", ""),
            username,
            str(user_id)
        ])

        return "✅ сохранена в Google Sheets"

    except Exception as e:
        print(f"Google Sheets error: {e}")
        return f"⚠️ ошибка Google Sheets: {e}"


def find_service(text: str):
    text = text.lower().strip()

    for service in services:
        if service["name"].lower() == text:
            return service

        for alias in service["aliases"]:
            if alias in text:
                return service

    return None


def service_card(service):
    return (
        f"📊 <b>{service['name']}</b>\n\n"
        f"{service['desc']}\n\n"
        f"✅ Подходит, {service['best_for']}\n\n"
        f"💰 <b>Стоимость:</b> {service['price']}\n"
        f"⏱ <b>Срок:</b> {service['time']}\n\n"
        f"Можете оставить заявку или записаться на консультацию."
    )


def start_lead_flow(user_id):
    user_states[user_id] = "lead_name"
    user_leads[user_id] = {}



@dp.message(Command("ai"))
async def ai_consultant(message: types.Message):
    question = (message.text or "").replace("/ai", "", 1).strip()

    if not question:
        await message.answer(
            "Напишите вопрос после команды.\n\n"
            "Например:\n"
            "/ai Что такое мультиканальная атрибуция?"
        )
        return

    await message.answer("⏳ Готовлю ответ...")

    answer = await ask_stack_ai(
        user_text=question,
        user_id=message.from_user.id,
    )

    await message.answer(answer)


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()
    text_lower = text.lower()

    if text == "❌ Отменить":
        user_states[user_id] = None
        user_leads[user_id] = {}

        await message.answer(
            "Ок, отменил текущий сценарий. Возвращаю в главное меню.",
            reply_markup=main_kb
        )
        return

    if text == "/start" or text == "⬅️ В главное меню":
        user_states[user_id] = None

        await message.answer(
            "👋 Привет! Я помогу подобрать исследовательское решение МТС Ads под вашу задачу.\n\n"
            "Выберите, что вам нужно:\n\n"
            "🔍 подобрать решение\n"
            "📎 получить материалы\n"
            "📅 записаться на консультацию\n"
            "📝 оставить заявку\n"
            "ℹ️ узнать, как всё работает",
            reply_markup=main_kb
        )
        return

    if text == "🔍 Подобрать решение":
        await message.answer(
            "🔍 Раздел подбора решения.\n\n"
            "Можно посмотреть все продукты, сравнить их, узнать цены или описать задачу — я подскажу подходящий вариант.",
            reply_markup=solution_kb
        )
        return

    if text == "📎 Материалы":
        await message.answer(
            "📎 Раздел материалов.\n\n"
            "Здесь можно получить Sales Kit и кратко посмотреть, что внутри.",
            reply_markup=materials_kb
        )
        return

    if text == "📅 Консультация":
        await message.answer(
            "📅 Раздел консультации.\n\n"
            "Можно сразу записаться в MTS Link или передать задачу менеджеру заранее.",
            reply_markup=consultation_kb
        )
        return

    if text == "ℹ️ Помощь":
        await message.answer(
            "ℹ️ Раздел помощи.\n\n"
            "Здесь можно узнать, как проходит исследование, посмотреть частые вопросы или связаться с менеджером.",
            reply_markup=help_kb
        )
        return

    if text == "📝 Оставить заявку":
        start_lead_flow(user_id)

        await message.answer(
            "Давайте быстро соберём заявку, чтобы менеджер сразу понял контекст.\n\n"
            "Как вас зовут?"
        )
        return

    if text == "📝 Передать задачу заранее" or text == "👨‍💼 Связаться с менеджером":
        start_lead_flow(user_id)

        await message.answer(
            "Хорошо, передадим задачу менеджеру.\n\n"
            "Как вас зовут?"
        )
        return

    if text == "📊 Все услуги":
        await message.answer(
            "Выберите услугу из списка ниже:",
            reply_markup=services_kb
        )
        return

    if text == "💰 Цены и сроки":
        msg = "💰 <b>Цены и сроки по услугам:</b>\n\n"

        for s in services:
            msg += f"• <b>{s['name']}</b> — {s['price']}, {s['time']}\n"

        await message.answer(
            msg,
            parse_mode="HTML",
            reply_markup=solution_kb
        )
        return

    if text == "🆚 Сравнить продукты":
        await message.answer(
            "🆚 <b>Короткое сравнение продуктов</b>\n\n"
            "<b>Brand Lift</b> — если нужно понять узнаваемость, запоминаемость и отношение к бренду.\n\n"
            "<b>Конверсионный анализ</b> — если нужно оценить влияние рекламы на продажи, заявки, звонки или действия на сайте.\n\n"
            "<b>Доходимость</b> — если нужно понять, дошли ли пользователи до офлайн-точек после контакта с рекламой.\n\n"
            "<b>Профилирование</b> — если нужно узнать портрет аудитории: пол, возраст, интересы, гео и другие признаки.\n\n"
            "<b>Аналитика наружной рекламы</b> — если нужно оценить эффективность OOH/DOOH-размещений.\n\n"
            "<b>ТВ-аналитика</b> — если нужно оценить охват и эффект ТВ-размещений.",
            parse_mode="HTML",
            reply_markup=solution_kb
        )
        return

    if text == "❓ FAQ по продуктам" or text == "❓ Частые вопросы":
        await message.answer(
            "❓ <b>Частые вопросы</b>\n\n"
            "<b>1. Можно ли оценить эффективность рекламы?</b>\n"
            "Да. В зависимости от задачи подойдёт Brand Lift, конверсионный анализ, доходимость или OOH/TV-аналитика.\n\n"
            "<b>2. Что нужно для старта?</b>\n"
            "Обычно нужны период кампании, описание аудитории, каналы размещения и цель исследования.\n\n"
            "<b>3. Можно ли оценить офлайн-точки?</b>\n"
            "Да, для этого подходит доходимость или тепловая карта.\n\n"
            "<b>4. Можно ли сравнить себя с конкурентами?</b>\n"
            "Да, для этого есть анализ конкурентов.\n\n"
            "<b>5. Если я не знаю, какая услуга нужна?</b>\n"
            "Нажмите «🧭 Подбор по задаче» и опишите задачу своими словами.",
            parse_mode="HTML",
            reply_markup=help_kb
        )
        return

    if text == "⚙️ Как проходит исследование":
        await message.answer(
            "⚙️ <b>Как обычно проходит исследование</b>\n\n"
            "1. Уточняем бизнес-задачу клиента.\n"
            "2. Подбираем подходящую методологию.\n"
            "3. Согласуем вводные: период, каналы, аудиторию, гео, точки или события.\n"
            "4. Проводим расчёт или исследование.\n"
            "5. Передаём результаты, выводы и рекомендации.\n\n"
            "Если задача нестандартная, можно оставить заявку — менеджер подскажет, какой формат исследования подойдёт.",
            parse_mode="HTML",
            reply_markup=help_kb
        )
        return

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
            "Также внутри есть описание методологий, примеры задач и база кейсов.",
            parse_mode="HTML",
            reply_markup=materials_kb
        )
        return

    if text == "📎 Получить Sales Kit":
        await message.answer(
            "📎 Отправляю материалы по исследовательским продуктам МТС Ads.\n\n"
            "После просмотра можете оставить заявку или записаться на консультацию.",
            reply_markup=materials_kb
        )

        for material in MATERIALS:
            try:
                document = FSInputFile(material["path"])
                await message.answer_document(
                    document=document,
                    caption=material["caption"]
                )
            except Exception as e:
                await message.answer(
                    f"⚠️ Не удалось отправить файл: {material['title']}\n"
                    f"Ошибка: {e}"
                )

        username = message.from_user.username or "без username"

        await bot.send_message(
            ADMIN_ID,
            f"📎 <b>Пользователь запросил материалы</b>\n\n"
            f"От: @{username}\n"
            f"Telegram ID: {user_id}",
            parse_mode="HTML"
        )
        return

    if text == "📅 Записаться в MTS Link":
        await message.answer(
            "📅 <b>Запись на консультацию</b>\n\n"
            "Вы можете выбрать удобное время для встречи в MTS Link.\n\n"
            "На консультации менеджер поможет:\n"
            "— уточнить бизнес-задачу\n"
            "— подобрать подходящее аналитическое решение\n"
            "— сориентировать по срокам и стоимости\n"
            "— подсказать, какие данные нужны для старта\n\n"
            f"Ссылка на запись:\n{MTS_LINK_URL}\n\n"
            "После записи можете передать задачу заранее — менеджер подготовится к встрече.",
            parse_mode="HTML",
            reply_markup=consultation_kb
        )

        username = message.from_user.username or "без username"

        await bot.send_message(
            ADMIN_ID,
            f"📅 <b>Пользователь открыл запись на консультацию</b>\n\n"
            f"От: @{username}\n"
            f"Telegram ID: {user_id}",
            parse_mode="HTML"
        )
        return

    if text == "🧭 Подбор по задаче":
        user_states[user_id] = "selection"

        await message.answer(
            "Опишите задачу в одном сообщении.\n\n"
            "Например:\n"
            "— хотим понять, сработала ли наружная реклама\n"
            "— нужно оценить визиты в магазины\n"
            "— хотим узнать портрет аудитории\n"
            "— нужно доказать эффект рекламы на продажи",
            reply_markup=solution_kb
        )
        return

    if user_states.get(user_id) == "lead_name":
        user_leads[user_id]["name"] = text
        user_states[user_id] = "lead_company"

        await message.answer("Из какой вы компании?")
        return

    if user_states.get(user_id) == "lead_company":
        user_leads[user_id]["company"] = text
        user_states[user_id] = "lead_role"

        await message.answer(
            "Кто вы?",
            reply_markup=role_kb
        )
        return

    if user_states.get(user_id) == "lead_role":
        user_leads[user_id]["role"] = text
        user_states[user_id] = "lead_interest"

        await message.answer(
            "Какой продукт интересует больше всего?",
            reply_markup=interest_kb
        )
        return

    if user_states.get(user_id) == "lead_interest":
        user_leads[user_id]["interest"] = text
        user_states[user_id] = "lead_task"

        await message.answer(
            "Кратко опишите задачу: что хотите измерить или проанализировать?"
        )
        return

    if user_states.get(user_id) == "lead_task":
        user_leads[user_id]["task"] = text
        user_states[user_id] = "lead_contact"

        await message.answer(
            "Как с вами удобнее связаться? Можно оставить Telegram, телефон или email."
        )
        return

    if user_states.get(user_id) == "lead_contact":
        user_leads[user_id]["contact"] = text

        username = message.from_user.username or "без username"
        lead = user_leads[user_id]

        sheet_status = save_lead_to_google_sheets(lead, username, user_id)

        await message.answer(
            "Спасибо! Передал заявку менеджеру.\n\n"
            "Он сможет вернуться уже с пониманием вашей задачи.",
            reply_markup=main_kb
        )

        await bot.send_message(
            ADMIN_ID,
            f"🔥 <b>Новая заявка из Telegram-бота</b>\n\n"
            f"👤 Имя: {lead.get('name')}\n"
            f"🏢 Компания: {lead.get('company')}\n"
            f"👔 Роль: {lead.get('role')}\n"
            f"🎯 Интерес: {lead.get('interest')}\n"
            f"📌 Задача: {lead.get('task')}\n"
            f"☎️ Контакт: {lead.get('contact')}\n"
            f"🔗 Telegram: @{username}\n"
            f"🧾 Таблица: {sheet_status}",
            parse_mode="HTML"
        )

        user_states[user_id] = None
        user_leads[user_id] = {}
        return

    service = find_service(text)

    if service:
        await message.answer(
            service_card(service),
            parse_mode="HTML",
            reply_markup=solution_kb
        )
        return

    if user_states.get(user_id) == "selection":
        suggested = None

        if any(word in text_lower for word in ["наруж", "ooh", "dooh", "щит", "билборд"]):
            suggested = find_service("наружная реклама")
        elif any(word in text_lower for word in ["визит", "точк", "магазин", "офлайн", "дошли"]):
            suggested = find_service("доходимость")
        elif any(word in text_lower for word in ["аудитор", "портрет", "интерес", "соцдем"]):
            suggested = find_service("профилирование")
        elif any(word in text_lower for word in ["продаж", "конверс", "заявк", "звонк"]):
            suggested = find_service("конверсионный анализ")
        elif any(word in text_lower for word in ["бренд", "узнаваем", "запомн", "отношение"]):
            suggested = find_service("brand lift")
        elif any(word in text_lower for word in ["конкурент", "сравнить"]):
            suggested = find_service("анализ конкурентов")
        elif any(word in text_lower for word in ["тв", "телевид"]):
            suggested = find_service("тв-аналитика")
        elif any(word in text_lower for word in ["карта", "гео", "локац", "где живет", "где работает"]):
            suggested = find_service("тепловая карта")

        if suggested:
            await message.answer(
                "По описанию задачи больше всего подходит:\n\n" + service_card(suggested),
                parse_mode="HTML",
                reply_markup=solution_kb
            )
        else:
            await message.answer(
                "Пока не могу точно подобрать услугу по описанию.\n\n"
                "Лучше передать задачу менеджеру — он уточнит детали и предложит подходящий вариант.",
                reply_markup=main_kb
            )

            username = message.from_user.username or "без username"

            await bot.send_message(
                ADMIN_ID,
                f"❗ <b>Нераспознанный запрос на подбор услуги</b>\n\n"
                f"От: @{username}\n"
                f"Текст: {text}",
                parse_mode="HTML"
            )

        return

    await message.answer(
        "Я пока не понял, какую именно задачу нужно решить.\n\n"
        "Выберите один из разделов главного меню или нажмите «🔍 Подобрать решение».",
        reply_markup=main_kb
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
