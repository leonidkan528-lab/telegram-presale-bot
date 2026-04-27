import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

import os

TOKEN = "7975259132:AAHa5mxmASaF1-qfKjiOJvwfubCmbQ-2BKU"
ADMIN_ID = 237014151

bot = Bot(token=TOKEN)
dp = Dispatcher()

services = [
    {
        "name": "brand lift",
        "aliases": ["brand lift", "узнаваемость", "запоминаемость", "запомнили рекламу", "отношение к бренду"],
        "price": "от 100 000 ₽",
        "desc": "измеряет, запомнили ли рекламу и изменилось ли отношение к бренду",
        "time": "до 7 рабочих дней"
    },
    {
        "name": "конверсионный анализ",
        "aliases": ["конверсионный анализ", "sales lift", "конверсии", "продажи после рекламы", "конверсии в звонки", "заходы на сайт"],
        "price": "от 100 000 ₽",
        "desc": "показывает, увеличила ли реклама продажи и другие целевые действия",
        "time": "до 14 рабочих дней"
    },
    {
        "name": "профилирование",
        "aliases": ["профилирование", "профиль аудитории", "аудитория", "соцдем", "интересы аудитории"],
        "price": "от 185 000 ₽",
        "desc": "показывает характеристики аудитории: гео, интересы, соцдем и другие признаки",
        "time": "до 7 рабочих дней"
    },
    {
        "name": "анализ конкурентов",
        "aliases": ["анализ конкурентов", "конкуренты", "сравнение с конкурентами", "бренды конкурентов"],
        "price": "от 185 000 ₽",
        "desc": "помогает сравнить аудиторию клиента и конкурентов",
        "time": "до 10 рабочих дней"
    },
    {
        "name": "тепловая карта",
        "aliases": ["тепловая карта", "heatmap", "где живет аудитория", "где работает аудитория", "места посещения"],
        "price": "от 290 000 ₽",
        "desc": "показывает, где живёт, работает и бывает целевая аудитория",
        "time": "до 14 рабочих дней"
    },
    {
        "name": "аналитика наружной рекламы",
        "aliases": ["аналитика наружной рекламы", "наружная реклама", "ooh", "dooh", "наружка", "анализ dooh", "анализ ooh"],
        "price": "от 175 000 ₽",
        "desc": "оценивает охват и целевые действия после контакта с наружной рекламой",
        "time": "до 14 рабочих дней"
    },
    {
        "name": "тв-аналитика",
        "aliases": ["тв-аналитика", "тв аналитика", "tv analytics", "тв", "телевидение", "анализ тв рекламы"],
        "price": "от 290 000 ₽",
        "desc": "оценивает охват и целевые действия после контакта с ТВ-рекламой",
        "time": "до 45 рабочих дней"
    },
    {
        "name": "доходимость",
        "aliases": ["доходимость", "footfall", "визиты в точку", "посещаемость точки", "сколько дошло до точки"],
        "price": "от 250 000 ₽",
        "desc": "измеряет, сколько пользователей дошло до офлайн-точки после контакта с рекламой",
        "time": "до 10 рабочих дней"
    }
]

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Доходимость"), KeyboardButton(text="Brand Lift")],
        [KeyboardButton(text="Конверсионный анализ"), KeyboardButton(text="Профилирование")],
        [KeyboardButton(text="Анализ конкурентов"), KeyboardButton(text="Тепловая карта")],
        [KeyboardButton(text="Аналитика наружной рекламы")],
        [KeyboardButton(text="ТВ-аналитика")],
        [KeyboardButton(text="Связаться с менеджером")]
    ],
    resize_keyboard=True
)

def find_service(text: str):
    text = text.lower().strip()

    for service in services:
        if service["name"] == text:
            return service
        for alias in service["aliases"]:
            if alias in text:
                return service

    return None


@dp.message()
async def handle_message(message: types.Message):
    text = (message.text or "").strip()

    if text == "/start":
        await message.answer(
            "Привет! Выбери интересующую услугу кнопкой ниже или напиши её вручную.",
            reply_markup=main_kb
        )
        return

    if text.lower() == "связаться с менеджером":
        await message.answer(
            "Напиши свой вопрос одним сообщением, и я передам его менеджеру.",
            reply_markup=main_kb
        )
        username = message.from_user.username or "без username"
        await bot.send_message(
            ADMIN_ID,
            f"📩 Клиент хочет связаться с менеджером\nОт: @{username}"
        )
        return

    service = find_service(text)

    if service:
        await message.answer(
            f"📊 Услуга: {service['name'].title()}\n"
            f"💰 Стоимость: {service['price']}\n"
            f"⏱ Срок подготовки: {service['time']}\n"
            f"📌 Что показывает: {service['desc']}\n\n"
            f"Можешь выбрать другую услугу кнопками ниже.",
            reply_markup=main_kb
        )
    else:
        await message.answer(
            "Не нашёл точную услугу.\n"
            "Выбери вариант кнопкой ниже или опиши задачу подробнее.",
            reply_markup=main_kb
        )

        username = message.from_user.username or "без username"
        await bot.send_message(
            ADMIN_ID,
            f"❗ Новый нераспознанный запрос\n"
            f"От: @{username}\n"
            f"Текст: {text}"
        )


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
