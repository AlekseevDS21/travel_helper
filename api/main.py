from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from enum import Enum
import httpx
import os
import random
import asyncio
from datetime import datetime, timedelta
from fastapi.responses import PlainTextResponse
from avia_parser import search_flights
from hotels_request import find_hotels

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
    price: float  # в рублях

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
    # Конвертация цен отелей обратно в рубли
    if hotel_list:
        # Преобразуем и отфильтровываем отели с нулевой ценой
        hotels: List[ParsedItem] = [
            ParsedItem(
                markdown=f"**{h['name']}** — {h['total_price']} руб.",
                url=h['url'],
                price=h['total_price']
            )
            for h in hotel_list if h.get("total_price", 0) > 0
        ]


        hotels = hotels[:3]


    else:
        hotels = []

    flights_md = "\n\n".join([
        f"Перелёт {i+1}: {f['airline']} — {f['price']} руб., пересадки: {f['transfers']}, {f['link']}"
        for i, f in enumerate(selected_flights)
    ])
    if hotels:
        hotels_md = "\n".join([item.markdown for item in hotels])
    else:
        hotels_md = "*Бюджета не хватает на отели.*"


    rec_prompt = f"""
Ты — туристический помощник. Перед тобой 3 варианта перелётов и  3 варианта отелей.
Объясни преимущества и недостатки каждого. Учитывай цену, количество пересадок, длительность перелёта и репутацию авиакомпании.
Учитывай цену и количество звёзд у отелей. Отвечай на русском языке

Перелёты:
{flights_md}

Отели:
{hotels_md}

Верни ответ в формате Markdown со списком:
1. [Вариант] (без цены)
   • Преимущества:
   • Недостатки: (если недостатков нет, не выводи поле)
   • Кому подойдёт:
"""

    checklist_prompt = f"""
Используй русский язык. Создай чеклист по дням для поездки в {request.destination_city} с учётом:
- Предпочтений: {', '.join(request.preferences)}
- Длительности: с {request.departure_date} по {request.return_date or request.departure_date}
- Состава группы: {request.adults} взрослых, {request.children} детей

Опиши, чем хорош город, и что посетить по дням. Формат: Markdown с заголовками дней.
"""

    recommendation, checklist = await asyncio.gather(
        ask_llm(rec_prompt),
        ask_llm(checklist_prompt)
    )


    result = f"""
## 🛫 Авиабилеты
{flights_md}

## 🏨 Отели
{hotels_md}

---
## 🤖 Рекомендации по перелетам\отелям
{recommendation}

---
## 📋 Чеклист путешественника!
{checklist}
"""

    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
