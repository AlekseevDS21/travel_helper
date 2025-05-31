# ✈️ Планировщик Путешествий

## 📌 О проекте

Интеллектуальная система для планирования путешествий, которая:
- Находит оптимальные авиабилеты по заданным параметрам
- Подбирает подходящие отели
- Дает персонализированные рекомендации
- Формирует чек-лист для поездки

## Особенности

- **Удобный интерфейс** на Streamlit
- **Интеграция с API** авиабилетов и отелей
- **AI-рекомендации** на основе бюджета и предпочтений

## Технологии

**Frontend:**

- `Streamlit` - веб-интерфейс
- `Requests` - работа с API

**Backend:**

- `FastAPI` - REST API
- `Uvicorn` - ASGI-сервер
- `Pydantic` - валидация данных

  
## Getting Started!

### Требования

- Установленные Docker и Docker Compose
- API-ключ от OpenRouter
- API-ключ от Авиасейлс

### Установка

1. Необходимо клонировать этот репозиторий
2. Создайте файл .env и добавьте ваш API-ключ:
   
   ```
   OPENROUTER_API_KEY=your_api_key_here
   HOTEL_TOKEN=your_token
   AVIA_TOKEN=your_token
   ```
4. Запустите контейнер
   
   ```
   docker-compose up -d
   ```
5. Откройте приложение на http://localhost:8501


## Пример запроса к API
```python
import requests

payload = {
    "departure_city": "Москва",
    "destination_city": "Санкт-Петербург",
    "departure_date": "2024-07-15",
    "return_date": "2024-07-20",
    "budget": 50000,
    "adults": 2,
    "preferences": ["art", "active"]
}

response = requests.post("http://localhost:8000/recommend", json=payload)
print(response.json())
```
