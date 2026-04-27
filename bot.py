import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

import os

TOKEN = "7975259132:AAHa5mxmASaF1-qfKjiOJvwfubCmbQ-2BKU"
ADMIN_ID = 237014151

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_states = {}
user_leads = {}

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
        [KeyboardButton(text="🔍 Подобрать услугу"), KeyboardButton(text="📊 Все услуги")],
        [KeyboardButton(text="💰 Цены и сроки"), KeyboardButton(text="❓ FAQ")],
        [KeyboardButton(text="📝 Оставить заявку"), KeyboardButton(text="👨‍💼 Связаться с менеджером")],
        [KeyboardButton(text="❌ Отменить")]
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
        f"Можете выбрать другую услугу или оставить заявку менеджеру."
    )


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()
    text_lower = text.lower()

    if text == "❌ Отменить":
        user_states[user_id] = None
        user_leads[user_id] = {}
        await message.answer(
            "Ок, отменил текущий сценарий. Можете выбрать действие в меню.",
            reply_markup=main_kb
        )
        return

    if text == "/start" or text == "⬅️ В главное меню":
        user_states[user_id] = None
        await message.answer(
            "Привет! Я помогу подобрать аналитический продукт под вашу задачу.\n\n"
            "Можно выбрать услугу из меню или описать задачу своими словами: "
            "например, «хочу оценить наружную рекламу» или «нужно понять аудиторию бренда».",
            reply_markup=main_kb
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
            reply_markup=main_kb
        )
        return

    if text == "❓ FAQ":
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
            "Нажмите «🔍 Подобрать услугу» и опишите задачу своими словами.",
            parse_mode="HTML",
            reply_markup=main_kb
        )
        return

    if text == "🔍 Подобрать услугу":
        user_states[user_id] = "selection"
        await message.answer(
            "Опишите задачу в одном сообщении.\n\n"
            "Например:\n"
            "— хотим понять, сработала ли наружная реклама\n"
            "— нужно оценить визиты в магазины\n"
            "— хотим узнать портрет аудитории\n"
            "— нужно доказать эффект рекламы на продажи",
            reply_markup=main_kb
        )
        return

    if text in ["👨‍💼 Связаться с менеджером", "📝 Оставить заявку"]:
        user_states[user_id] = "lead_name"
        user_leads[user_id] = {}
        await message.answer(
            "Давайте быстро соберём заявку, чтобы менеджер сразу понял контекст.\n\n"
            "Как вас зовут?"
        )
        return

    if user_states.get(user_id) == "lead_name":
        user_leads[user_id]["name"] = text
        user_states[user_id] = "lead_company"
        await message.answer("Из какой вы компании?")
        return

    if user_states.get(user_id) == "lead_company":
        user_leads[user_id]["company"] = text
        user_states[user_id] = "lead_task"
        await message.answer("Кратко опишите задачу: что хотите измерить или проанализировать?")
        return

    if user_states.get(user_id) == "lead_task":
        user_leads[user_id]["task"] = text
        user_states[user_id] = "lead_contact"
        await message.answer("Как с вами удобнее связаться? Можно оставить Telegram, телефон или email.")
        return

    if user_states.get(user_id) == "lead_contact":
        user_leads[user_id]["contact"] = text

        username = message.from_user.username or "без username"
        lead = user_leads[user_id]

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
            f"📌 Задача: {lead.get('task')}\n"
            f"☎️ Контакт: {lead.get('contact')}\n"
            f"🔗 Telegram: @{username}",
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
            reply_markup=services_kb
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
                reply_markup=services_kb
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
        "Можете написать проще, например:\n"
        "— хочу оценить наружную рекламу\n"
        "— нужно понять аудиторию бренда\n"
        "— хочу проверить, выросли ли продажи после рекламы\n"
        "— нужно понять, где живёт аудитория\n\n"
        "Или нажмите «🔍 Подобрать услугу».",
        reply_markup=main_kb
    )


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден. Добавьте его в Render Environment Variables.")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
