import os
import re
import time
import pandas as pd
from dotenv import load_dotenv
import lyricsgenius as lg
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from config import ARTIST_LIST, ARTIST_DEFAULT_TAGS, ALBUM_TAGS
import requests
# ----------------------------------------------------
# 1. КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ----------------------------------------------------

load_dotenv()
GENIUS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")

if not GENIUS_TOKEN:
    raise ValueError("Токен GENIUS_ACCESS_TOKEN не найден.")

# Константы для путей
DATA_FOLDER = "data"
OUTPUT_CSV = f'{DATA_FOLDER}/genius_df.csv'
OUTPUT_TXT = f'{DATA_FOLDER}/structured_rap_lyrics.txt'

# ----------------------------------------------------
# 2. СХЕМА ДАННЫХ (Dataclass)
# ----------------------------------------------------

@dataclass
class SongData:
    """Структура для хранения данных о песне."""
    artist: str
    title: str
    lyrics: str
    structured_text: str
    tags: str
    primary_artist: str
    album: Optional[str]


# ----------------------------------------------------
# 3. ФУНКЦИИ-ПОМОЩНИКИ
# ----------------------------------------------------

def init_genius() -> lg.Genius:
    """Инициализация объекта Genius."""
    print("Инициализация API Genius...")
    return lg.Genius(
        GENIUS_TOKEN,
        verbose=False,
        remove_section_headers=False,
        skip_non_songs=False,
        excluded_terms=["(Live)", "(Remix)", "(Acoustic)"],
        timeout=60,
        retries=3
    )


def clean_lyrics(text: str) -> str:
    """Очистка текста от артефактов Genius."""
    if not isinstance(text, str):
        return ""

    # 1. Удаляем артефакты Genius (Embed, номера)
    cleaned_text = re.sub(r'Embed$', '', text, flags=re.MULTILINE).strip()
    cleaned_text = re.sub(r'^\d+Embed$', '', cleaned_text, flags=re.MULTILINE).strip()

    # 2. Нормализация переносов строк (не более двух подряд)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

    # 3. Нормализация заголовков секций: [  Verse 1 ] -> [Verse 1]
    cleaned_text = re.sub(r'\[\s*(.*?)\s*\]', r'[\g<1>]', cleaned_text)

    # 4. Удаление нестандартных символов (оставляем скобки для тегов)
    cleaned_text = re.sub(r'[^a-zA-Z0-9\s\.,:;?!а-яА-ЯёЁ\[\]]+', ' ', cleaned_text)

    # 5. Нормализация пробелов
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text


def process_song(song_light, artist_name: str, genius_api: lg.Genius) -> Optional[SongData]:
    """
    Получает полные данные по песне (включая теги) и форматирует их.
    Использует теги Genius как приоритет, с FALLBACK на хардкодные теги альбома/артиста.
    """
    try:
        # 1. Первая попытка: Получаем полный объект через поиск по названию (search_song)
        song_full = genius_api.search_song(song_light.title, artist=artist_name)

        if not song_full:
            print(f"  [!] Не удалось найти полные данные для '{song_light.title}'.")
            return None

        # 2. Очистка и проверка лирики
        lyrics_text = clean_lyrics(song_full.lyrics)
        if not lyrics_text or len(lyrics_text) < 10:
            print(f"  [.] Пропущена песня '{song_full.title}' (пустой текст).")
            return None

        # 3. ИЗВЛЕЧЕНИЕ ТЕГОВ: Genius -> Хардкод Альбома -> Хардкод Артиста

        # Получаем имя альбома и исполнителя
        album_name = None
        if hasattr(song_full, 'album') and isinstance(song_full.album, dict) and 'name' in song_full.album:
            album_name = song_full.album.get('name')

        primary_artist_name = artist_name
        if isinstance(song_full.primary_artist, dict):
            primary_artist_name = song_full.primary_artist.get('name', artist_name)


        final_tags = []

        # Попытка 2 (Fallback): Если Genius не дал тегов, используем хардкод
        if not final_tags:

            # 2.1 Проверяем хардкод по альбому
            album_tags_map = ALBUM_TAGS.get(artist_name, {})
            if album_name and album_name in album_tags_map:
                final_tags = album_tags_map[album_name]
                # print(f"  [>] Теги установлены по альбому '{album_name}' (Хардкод).")

            # 2.2 Если тегов альбома нет, используем общие теги артиста
            elif artist_name in ARTIST_DEFAULT_TAGS:
                final_tags = ARTIST_DEFAULT_TAGS[artist_name]
                # print(f"  [>] Теги установлены по умолчанию для артиста (Хардкод).")

        # Форматирование тегов
        tags_str = ','.join(final_tags)
        tags_context = f"[TAGS: {tags_str}]" if final_tags else ""

        # 4. Структурирование текста
        structured_text = (
            f"[ARTIST: {artist_name}] "
            f"[TITLE: {song_full.title}] "
            f"{tags_context} "
            f"{lyrics_text}"
        ).strip()

        # 5. Сборка объекта SongData
        return SongData(
            artist=artist_name,
            title=song_full.title,
            lyrics=lyrics_text,
            structured_text=structured_text,
            tags=tags_str,
            primary_artist=primary_artist_name,
            album=album_name
        )

    except Exception as e:
        print(f"  [!] Критическая ошибка при обработке песни '{song_light.title}': {e}")
        return None


# ----------------------------------------------------
# 4. ГЛАВНАЯ ФУНКЦИЯ СБОРА
# ----------------------------------------------------

def collect_lyrics(artist_list: List[str], max_songs: Optional[int] = None) -> pd.DataFrame:
    """Собирает тексты песен и теги Genius для списка артистов."""
    all_songs_data: List[SongData] = []
    genius_api = init_genius()
    for artist_name in artist_list:
        print(f"\n--- Начинаем сбор песен артиста: {artist_name} ---")

        try:
            artist_obj = genius_api.search_artist(artist_name, max_songs=max_songs, sort='popularity')

            if not artist_obj:
                print(f" [!] Артист '{artist_name}' не найден.")
                continue

            print(f" Найдено {len(artist_obj.songs)} песен. Начинаем обработку...")

            song_count = 0
            for song_light in artist_obj.songs:
                song_data = process_song(song_light, artist_name, genius_api)

                if song_data:
                    all_songs_data.append(song_data)
                    song_count += 1

                time.sleep(0.1)  # 100ms пауза

            print(f" Успешно обработано {song_count} из {len(artist_obj.songs)} песен.")

        except Exception as e_artist:
            print(f" [!] Критическая ошибка при поиске артиста {artist_name}: {e_artist}")
            # Пауза при ошибке API
            time.sleep(5)

    print(f"\nСбор завершен. Итого собрано {len(all_songs_data)} песен.")
    # Преобразуем список датаклассов в DataFrame
    return pd.DataFrame([asdict(song) for song in all_songs_data])


# ----------------------------------------------------
# 5. ТОЧКА ВХОДА (ЗАПУСК)
# ----------------------------------------------------

def main():
    """Главный скрипт для запуска сбора и сохранения данных."""

    genius_api = init_genius()

    # 1. Сбор данных
    df = collect_lyrics(["SALUKI"], genius_api, max_songs=1)  # max_songs=50 для теста

    if df.empty:
        print(" [!] Данные не были собраны. Выход.")
        return

    # 2. Фильтрация (уже сделана в process_song, но дублируем для надежности)
    df = df[df['lyrics'].str.len() > 10].copy()

    # 3. Сохранение CSV
    os.makedirs(DATA_FOLDER, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nЧистые и структурированные данные сохранены в {OUTPUT_CSV}. Итого: {len(df)} песен.")

    # 4. Сохранение единого TXT файла для обучения
    final_structured_text = "\n\n".join(df['structured_text'].tolist())

    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write(final_structured_text)
    print(f"Единый TXT файл для обучения сохранен: {OUTPUT_TXT}")


if __name__ == "__main__":
    main()