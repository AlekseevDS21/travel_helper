from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from enum import Enum
import httpx
import os
from dotenv import load_dotenv
import random
import asyncio
from datetime import datetime, timedelta
from fastapi.responses import PlainTextResponse
from avia_parser import search_flights
from hotels_request import find_hotels

# Load environment variables
load_dotenv()

app = FastAPI(title="Travel Recommendation API")


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "deepseek/deepseek-prover-v2:free"

# Примерный курс доллара для конвертации цен отелей в рубли
USD_TO_RUB = 90.0


class TravelPreference(str, Enum):
    ACTIVE = "active"
    ART = "art"
    BEACH = "beach"

class FlightClass(str, Enum):
    ECONOMY = "economy"
    BUSINESS = "business"
    FIRST = "first"

class TravelRequest(BaseModel):
    departure_city: str
    destination_city: Optional[str] = None
    departure_date: str
    return_date: Optional[str] = None
    flight_class: FlightClass = FlightClass.ECONOMY
    budget: float  # в рублях
    adults: int = 1
    children: int = 0
    infants: int = 0
    is_one_way: bool = False
    direct_flights: bool = False
    preferences: List[TravelPreference]

class ParsedItem(BaseModel):
    markdown: str
    url: str
    price: float  # в USD

async def ask_llm(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://your-travel-app.com",
        "X-Title": "Travel AI"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OPENROUTER_API_URL,
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}]
            }, headers=headers, timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

@app.get("/", response_class=PlainTextResponse)
async def root():
    return "Travel Recommendation API up & running. POST to /recommend"

@app.post("/recommend", response_class=PlainTextResponse)
async def recommend(request: TravelRequest):
    flight_results = await asyncio.to_thread(
        search_flights,
        origin_input=request.departure_city,
        destination_input=request.destination_city,
        departure_date=request.departure_date,
        return_date=request.return_date,
        is_one_way=request.is_one_way,
        direct=request.direct_flights,
        adult=request.adults,
        child=request.children,
        infant=request.infants,
        save_results=False
    )
    if not flight_results.get('data'):
        raise HTTPException(status_code=404, detail="No flights found")


    flights = []
    for f in flight_results['data']:
        flights.append({
            "airline": f.get("airline", "N/A"),
            "price": f.get("price", 0),
            "departure_time": f.get("departure_at", ""),
            "arrival_time": f.get("return_at", ""),
            "transfers": f.get("transfers", "?"),
            "link": f"https://aviasales.ru{f.get('link')}"
        })


    affordable = [f for f in flights if f["price"] <= request.budget]
    if not affordable:
        raise HTTPException(status_code=400, detail="Бюджета недостаточно для билетов")


    selected_flights = random.sample(affordable, min(3, len(affordable)))
    cheapest_price = min(f["price"] for f in affordable)
    remaining_budget = request.budget - cheapest_price


    # Convert budget to USD for hotel search
    budget_hotels_usd = remaining_budget / USD_TO_RUB if remaining_budget > 0 else 0


    check_out = request.return_date or (
        (datetime.strptime(request.departure_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    )

    hotel_list = []
    if budget_hotels_usd > 0:
        hotel_list = await asyncio.to_thread(
            find_hotels,
            request.destination_city,
            budget_hotels_usd,
            request.departure_date,
            check_out,
            request.adults + request.children + request.infants
        )
    
    # Keep hotel prices in USD without converting to rubles
    if hotel_list:
        hotels = hotel_list[:3]  # Get top 3 hotels with most detailed info
    else:
        hotels = []

    # Восстанавливаем полную информацию о билетах, включая ссылки
    flights_md = "\n\n".join([
        f"### Перелёт {i+1}: {f['airline']}\n" +
        f"* **Цена:** ${f['price']/USD_TO_RUB:.2f}\n" +
        f"* **Вылет:** {f['departure_time']}\n" +
        f"* **Возвращение:** {f['arrival_time']}\n" +
        f"* **Пересадки:** {f['transfers']}\n" +
        f"* **Ссылка:** {f['link']}"
        for i, f in enumerate(selected_flights)
    ])
    
    # Enhance hotel output with more details
    if hotels:
        hotels_md = ""
        for i, h in enumerate(hotels):
            nights = calculate_nights(request.departure_date, check_out) if not request.is_one_way else 1
            hotels_md += f"### Отель {i+1}: {h['name']}\n"
            hotels_md += f"* **Рейтинг:** {h['rating']}/10\n"
            hotels_md += f"* **Звезд:** {'⭐' * int(h['stars'])}\n"
            hotels_md += f"* **Цена за ночь:** ${h['per_night']:.2f}\n"
            hotels_md += f"* **Общая стоимость ({nights} ночей):** ${h['total_price']/100:.2f}\n"
            hotels_md += f"* **Адрес:** {h['address']}\n"
            if h['url']:
                hotels_md += f"* **Ссылка:** {h['url']}\n"
            if h['main_photo']:
                hotels_md += f"* **Фото:** ![{h['name']}]({h['main_photo']})\n"
            hotels_md += "\n"
    else:
        hotels_md = "*Бюджета не хватает на отели.*"


    rec_prompt = f"""
Ты — туристический помощник. Перед тобой варианты перелётов и отелей.
Объясни преимущества и недостатки каждого. Учитывай цену, количество пересадок, длительность перелёта и репутацию авиакомпании.
Учитывай цену, рейтинг и количество звёзд у отелей. Отвечай на русском языке.

Важно: твой ответ должен быть строго в Markdown формате, ничего лишнего.

Перелёты:
{flights_md}

Отели:
{hotels_md}

Верни ответ в формате Markdown со списком:

#### Выбор перелёта и отеля

##### Перелёт 1: [Название авиакомпании]
- **Преимущества:**
  - [преимущество 1]
  - [преимущество 2]
- **Недостатки:** (если недостатков нет, не выводи поле)
  - [недостаток 1]
  - [недостаток 2]
- **Кому подойдёт:** [описание целевой аудитории]

##### [И так далее для каждого варианта]
"""

    checklist_prompt = f"""
Создай чеклист путешественника для поездки в {request.destination_city} в формате Markdown.

Важная информация:
- Предпочтения туриста: {', '.join(request.preferences)}
- Длительность поездки: с {request.departure_date} по {request.return_date or request.departure_date}
- Состав группы: {request.adults} взрослых, {request.children} детей

Твой ответ должен быть строго в формате Markdown:
1. Начни с краткого описания города и его особенностей (2-3 предложения)
2. Раздели чеклист по дням, где каждый день - это заголовок второго уровня (##)
3. Для каждого дня создай список активностей с маркерами (-)
4. Используй **жирный текст** для важных моментов и *курсив* для дополнительной информации
5. Обязательно учти предпочтения туриста
6. Если есть места которые стоит посетить, оформи их как подзаголовки третьего уровня (###)

Очень важно, чтобы это был качественный markdown для отображения в приложении.
"""

    recommendation, checklist = await asyncio.gather(
        ask_llm(rec_prompt),
        ask_llm(checklist_prompt)
    )

    # Форматируем результат с правильными отступами и структурой для Markdown
    result = f"""
## 🛫 Авиабилеты
{flights_md}

## 🏨 Отели
{hotels_md}

---

## 🤖 Рекомендации по перелетам и отелям

{recommendation}

---

## 📋 Чеклист путешественника

{checklist}
"""

    return result

def calculate_nights(check_in: str, check_out: str) -> int:
    """Количество ночей между датами."""
    date_in = datetime.strptime(check_in, '%Y-%m-%d')
    date_out = datetime.strptime(check_out, '%Y-%m-%d')
    nights = (date_out - date_in).days
    return max(1, nights)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
