import os
import librosa
import numpy as np
import subprocess

# ----------------------------------------------------
# 1. LIBROSA (АУДИО-АНАЛИЗ)
# ----------------------------------------------------

def analyze_audio_file(audio_path):
    """
    Анализирует MP3/WAV файл и возвращает характеристики Librosa:
    tempo, energy, danceability, valence.
    """
    try:
        y, sr = librosa.load(audio_path, duration=30)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]
        energy = min(float(np.mean(rms)) * 10, 1.0)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        danceability = max(0, min(1, float(np.std(onset_env)) / 10))

        # Расчет Valence (Позитивности) через хрома-фичи и энергию
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_sums = np.sum(chroma, axis=1)
        major_weight = (chroma_sums[0] + chroma_sums[4] + chroma_sums[7]) / np.sum(chroma_sums)
        valence = float(major_weight * 0.7 + energy * 0.3)

        return {
            'tempo': float(tempo),
            'energy': energy,
            'danceability': danceability,
            'valence': valence
        }
    except Exception:
        return None


# ----------------------------------------------------
# 2. YTDL + LIBROSA (АВТОМАТИЗАЦИЯ)
# ----------------------------------------------------

def get_audio_features_auto(artist, track):
    """
    Ищет трек на YouTube, скачивает его 30-секундный сэмпл (yt-dlp),
    анализирует (Librosa) и удаляет временный файл.
    Возвращает словарь фичей или None.
    """
    temp_file = "temp_audio_librosa.mp3"
    query = f"{artist} - {track} audio"

    try:
        command = [
            'yt-dlp', 'ytsearch1:' + query, '-x', '--audio-format', 'mp3',
            '--postprocessor-args', '-ss 00:00:00 -t 00:00:30', '-o', temp_file, '--quiet'
        ]
        # используем subprocess.run для выполнения команды yt-dlp
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            # eсли команда завершилась с ошибкой, выводим причину
            print(f"\n yt-dlp FAILED for query '{query}':")
            print("--- yt-dlp stderr (Top 5 lines) ---")
            print('\n'.join(result.stderr.split('\n')[:5]))
            print("-----------------------------------")
            return None

        if not os.path.exists(temp_file):
            return None

        audio_features = analyze_audio_file(temp_file)
        return audio_features
    except Exception as e:
        # общая ошибка (например, subprocess не найден)
        print(f"\n Общая ошибка запуска yt-dlp: {e}")
        return None
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


if __name__ == "__main__":
    TEST_ARTIST = "Boulevard Depo"
    TEST_TRACK = "БЕЛЫЙ ФЛАГ"

    print("=" * 60)
    print(f"ТЕСТОВЫЙ ЗАПУСК: {TEST_ARTIST} - {TEST_TRACK}")
    print("=" * 60)

    # 1. получение аудио-фичей
    print("\n1. Запуск аудио-анализа (yt-dlp + Librosa)...")
    audio_features = get_audio_features_auto(TEST_ARTIST, TEST_TRACK)

    if audio_features:
        print("Аудио-фичи успешно получены:")
        for key, value in audio_features.items():
            print(f"   • {key.capitalize()}: {value:.2f}")
    else:
        print(" Не удалось получить аудио-фичи. Проверьте yt-dlp, Librosa и доступ в интернет.")

    print("\n=" * 60)
    print(" Модуль готов к импорту и использованию в основном скрипте.")
    print("=" * 60)