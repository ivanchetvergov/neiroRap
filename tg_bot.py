import os
import torch
import logging
from transformers import AutoTokenizer, AutoModelForCausalLM
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import re

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL_PATH = "./neiroRap_final_model"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# глобальные переменные для модели (для быстрой загрузки один раз)
tokenizer = None
model = None
device = None


# --- 1. ФУНКЦИЯ ЗАГРУЗКИ МОДЕЛИ ---
def load_model_and_tokenizer():
    """Загружает модель и токенизатор, используя GPU, если доступен."""
    global tokenizer, model, device

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Используемое устройство: {device}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model = AutoModelForCausalLM.from_pretrained(MODEL_PATH).to(device)
        logger.info("Модель и токенизатор успешно загружены!")
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}. Проверьте путь {MODEL_PATH}")

# --- 2. ФУНКЦИЯ ГЕНЕРАЦИИ РЭПА (Core Logic) ---
def generate_rap_lyrics(prompt: str) -> str:
    """Генерирует рэп-лирику по заданному началу."""

    # начинаю генерацию с тега, чтобы модель знала формат
    input_text = f"[{prompt}] " if not prompt.startswith("[") else prompt

    input_ids = tokenizer.encode(input_text, return_tensors='pt').to(device)

    # параметры генерации
    output_ids = model.generate(
        input_ids,
        do_sample=True,
        max_length=len(input_ids[0]) + 150,  # генерируем 150 токенов поверх промпта\

        temperature=0.75,         # увеличиваем креативность
        repetition_penalty=1.5,   # штраф за повторение

        top_k=5,
        top_p=0.85,               # сужаем ядро
        num_return_sequences=1
    )

    # декодируем результат
    generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    # очистка: удаляем введенный промпт и лишние символы
    if generated_text.startswith(input_text):
        generated_text = generated_text[len(input_text):].strip()

    # форматирование для читаемости
    generated_text = generated_text.replace("\\n", "\n")

    # удаление шума
    noise = [" ы,", " ы", " А а", " У у", " Что?", " Ну да", " Бр р Р ра Да", " Что?Я"]
    for item in noise:
        generated_text = generated_text.replace(item, " ")

    # Нормализация пробелов после чистки
    generated_text = re.sub(r'\s+', ' ', generated_text).strip()

    return generated_text


# --- 3. ОБРАБОТЧИКИ TELEGRAM ---

# Обработка команды /start
async def start_command(update: Update, context) -> None:
    """Отправляет приветственное сообщение."""
    await update.message.reply_text(
        "Привет! Я НейроРэп-бот, дообученный на русскоязычных артистах (Бульвар Депо, Хаски и др.).\n"
        "Отправь мне начало фразы, и я сгенерирую продолжение.\n"
        "Например: 'Над городом ночь и...'"
    )


# обработка текстовых сообщений
async def generate_message(update: Update, context) -> None:
    """Генерирует текст по сообщению пользователя."""
    user_prompt = update.message.text

    await update.message.reply_text("🤔 Пишу текст... Дай мне секунду.")

    try:
        # запускаем логику генерации
        lyrics = generate_rap_lyrics(user_prompt)

        # объединяем промпт и результат для красивого вывода
        full_rap = f" **{user_prompt}** {lyrics}"

        await update.message.reply_text(full_rap, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await update.message.reply_text("Произошла ошибка при генерации. Попробуй еще раз.")


# Обработка неизвестных команд
async def unknown_command(update: Update, context) -> None:
    """Отвечает на неизвестные команды."""
    await update.message.reply_text(f"Команда '{update.message.text}' не распознана.")


# --- 4. ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---
def main() -> None:
    """Запускает бота."""

    # 1. загрузка модели перед запуском бота
    load_model_and_tokenizer()

    if model is None or tokenizer is None:
        logger.error("Запуск бота невозможен: модель не загружена.")
        return

    # 2. создание приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 3. регистрация обработчиков
    application.add_handler(CommandHandler("start", start_command))

    # обработка всех текстовых сообщений, которые не являются командами
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_message))

    # обработка неизвестных команд (должна быть последней)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # 4. запуск бота (Polling)
    logger.info("Бот запущен! Ожидание сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()