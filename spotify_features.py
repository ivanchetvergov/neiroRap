import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


def get_access_token():
    """Получает токен доступа через Client Credentials"""
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_str.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}

    print("🔑 Получение access token...")
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Token получен: {token[:20]}...\n")
        return token
    else:
        print(f"❌ Ошибка получения токена: {response.status_code}")
        print(response.text)
        return None


def search_track(token, artist, track):
    """Ищет трек напрямую через Spotify API"""
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": f"{artist} {track}",
        "type": "track",
        "limit": 5
    }

    print(f"🔍 Поиск: {artist} - {track}")
    print(f"📡 URL: {url}")
    print(f"📦 Params: {params}")

    response = requests.get(url, headers=headers, params=params)

    print(f"📊 Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        tracks = data['tracks']['items']

        if not tracks:
            print("⚠️  Треки не найдены\n")
            return None

        print(f"✅ Найдено треков: {len(tracks)}\n")

        for i, track_item in enumerate(tracks, 1):
            print(f"{i}. {track_item['artists'][0]['name']} - {track_item['name']}")

        return tracks[0]['id']
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(f"📄 Response: {response.text}\n")
        return None


def get_audio_features(token, track_id):
    """Получает аудио-фичи трека"""
    url = f"https://api.spotify.com/v1/audio-features/{track_id}"
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n📊 Получение аудио-фич для track_id: {track_id}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        features = response.json()
        print("✅ Аудио-фичи получены!\n")
        return features
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)
        return None


def print_features(features):
    """Выводит фичи"""
    if not features:
        return

    print("=" * 60)
    print("🎵 АУДИО-ХАРАКТЕРИСТИКИ:")
    print("=" * 60)
    print(f"Энергия: {features['energy']:.2%}")
    print(f"Танцевальность: {features['danceability']:.2%}")
    print(f"Позитивность: {features['valence']:.2%}")
    print(f"Темп: {features['tempo']:.0f} BPM")
    print(f"Громкость: {features['loudness']:.1f} dB")
    print(f"Акустичность: {features['acousticness']:.2%}")
    print(f"Инструментальность: {features['instrumentalness']:.2%}")
    print(f"Речь: {features['speechiness']:.2%}")
    print("=" * 60)


if __name__ == "__main__":
    # 1. Проверяем IP
    print("🌍 Проверка IP адреса...")
    try:
        ip_response = requests.get("https://api.ipify.org?format=json")
        ip_data = ip_response.json()
        print(f"✅ IP: {ip_data['ip']}")

        geo_response = requests.get(f"https://ipapi.co/{ip_data['ip']}/json/")
        geo_data = geo_response.json()
        print(f"✅ Страна: {geo_data.get('country_name')} ({geo_data.get('country_code')})\n")
    except:
        print("⚠️  Не удалось проверить IP\n")

    # 2. Получаем токен
    token = get_access_token()
    if not token:
        exit(1)

    # 3. Ищем трек
    track_id = search_track(token, "Хаски", "Панелька")

    if track_id:
        # 4. Получаем фичи
        features = get_audio_features(token, track_id)
        print_features(features)
