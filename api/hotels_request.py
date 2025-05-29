import os
import re
import requests
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from googletrans import Translator
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()
API_TOKEN = os.getenv('HOTEL_TOKEN')


def translate_to_en(text: str) -> str:
    """Переводим текст на английский (синхронно)."""
    translator = Translator()
    translated = translator.translate(text, src='auto', dest='en')
    return translated.text


def find_city_id(city_name: str) -> Optional[int]:
    """Ищем ID города по названию без сохранения на диск."""
    en_name = translate_to_en(city_name)
    url = (
        f"https://engine.hotellook.com/api/v2/lookup.json"
        f"?query={en_name}&lang=en&lookFor=city&limit=1&token={API_TOKEN}"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    locations = resp.json().get("results", {}).get("locations", [])
    return locations[0].get("id") if locations else None


def fetch_hotels_for_city(city_id: int) -> List[Dict[str, Any]]:
    """Загружает список всех отелей для данного city_id."""
    url = f"https://engine.hotellook.com/api/v2/static/hotels.json?locationId={city_id}&token={API_TOKEN}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("hotels", [])


def calculate_nights(check_in: str, check_out: str) -> int:
    """Количество ночей между датами."""
    date_in = datetime.strptime(check_in, '%Y-%m-%d')
    date_out = datetime.strptime(check_out, '%Y-%m-%d')
    nights = (date_out - date_in).days
    if nights <= 0:
        raise ValueError("Дата выезда должна быть позже даты заезда")
    return nights


def get_hotel_url(link: Optional[str]) -> Optional[str]:
    """Формируем полную URL-ссылку на отель."""
    if not link:
        return None
    match = re.search(r'(\d+)\.html$', link)
    return f"https://hotellook.com/hotels/hotel-{match.group(1)}" if match else None


def find_hotels(
    city: str,
    max_total_price: float,
    check_in: str,
    check_out: str,
    adults: int,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """Ищем и фильтруем отели по заданным критериям."""
    city_id = find_city_id(city)
    if city_id is None:
        raise RuntimeError(f"Город '{city}' не найден")

    all_hotels = fetch_hotels_for_city(city_id)
    nights = calculate_nights(check_in, check_out)

    filtered: List[Dict[str, Any]] = []
    for hotel in sorted(all_hotels, key=lambda x: x.get("rating", 0), reverse=True):
        if len(filtered) >= max_results:
            break

        price_per_night = hotel.get('pricefrom')
        if price_per_night is None:
            continue

        total_price = (price_per_night * nights * adults)*100
        if total_price <= max_total_price:
            photos = [p.get('url') for p in hotel.get('photos', []) if p.get('url')]
            filtered.append({
                "id":         hotel.get('id'),
                "name":       hotel.get('name', {}).get('en', 'Unknown'),
                "rating":     hotel.get('rating', 0),
                "stars":      hotel.get('stars', 0),
                "total_price":total_price,
                "per_night":  price_per_night,
                "address":    hotel.get('address', {}).get('en', ''),
                "url":        get_hotel_url(hotel.get('link')),
                "main_photo": photos[0] if photos else None,
                "photos":     photos
            })
    return filtered


if __name__ == "__main__":
    try:
        results = find_hotels(
            city="Париж",
            max_total_price=50000,
            check_in="2025-09-13",
            check_out="2025-09-23",
            adults=2
        )
        for hotel in results:
            print(json.dumps(hotel, ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"Ошибка: {error}")
