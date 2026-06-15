import logging
import os

import aiohttp


logger = logging.getLogger(__name__)

STACK_AI_API_URL = os.getenv("STACK_AI_API_URL")
STACK_AI_API_TOKEN = os.getenv("STACK_AI_API_TOKEN")

FALLBACK_MESSAGE = (
    "Сейчас AI-консультант временно недоступен. "
    "Оставьте вопрос и контакт — менеджер свяжется с вами."
)


async def ask_stack_ai(user_text: str, user_id: int | str) -> str:
    if not STACK_AI_API_URL or not STACK_AI_API_TOKEN:
        logger.error("Не найдены переменные Stack AI")
        return FALLBACK_MESSAGE

    headers = {
        "Authorization": f"Bearer {STACK_AI_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "in-0": user_text,
        "user_id": str(user_id),
    }

    timeout = aiohttp.ClientTimeout(total=90)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                STACK_AI_API_URL,
                headers=headers,
                json=payload,
            ) as response:

                data = await response.json()

                if response.status != 200:
                    logger.error("Ошибка Stack AI: %s", data)
                    return FALLBACK_MESSAGE

                outputs = data.get("outputs", {})
                answer = outputs.get("out-0")

                if isinstance(answer, str) and answer.strip():
                    return answer.strip()

                logger.error("Не найден ответ outputs -> out-0: %s", data)
                return FALLBACK_MESSAGE

    except Exception as error:
        logger.exception("Ошибка запроса к Stack AI: %s", error)
        return FALLBACK_MESSAGE
