#ПАРАМЕТРЫ ПУТЕШЕСТВИЯ 
origin_input = "Москва"         # Город вылета
destination_input = "Дубай"     # Город назначения или оставить пустым для популярных направлений
departure_date = "10-06-25"      # Дата вылета: DD-MM-YY или YYYY-MM-DD
return_date = "24-06-25"         # Дата возвращения: DD-MM-YY или YYYY-MM-DD
is_one_way = False               # Билет в одну сторону?
direct = False                   # Только прямые рейсы?
adult = 2                         # Взрослых
child = 1                         # Детей
infant = 0                        # Младенцев


import os
import json
import csv
import requests
from datetime import datetime
from dotenv import load_dotenv


# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("AVIASALES_TOKEN")
API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

# Загрузка справочника городов
def load_city_codes(file_path="city2code.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Файл city2code.json не найден.")
        return {}

# Поиск IATA-кода по названию города
def find_iata_code(city_name, city_codes):
    matches = []
    city_name = city_name.lower()

    for city, code in city_codes.items():
        if city_name in city.lower():
            matches.append((city, code))

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0][1]

    # Если несколько совпадений, выбираем первое
    return matches[0][1]

# Парсинг даты DD-MM-YY или YYYY-MM-DD
def parse_date(date_str):
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%y"):
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("Дата должна быть в формате DD-MM-YY или YYYY-MM-DD")

# Загрузка данных об авиакомпаниях из JSON
def load_airline_data(file_path="airlines.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return {item["code"]: item for item in json.load(f)}
    except FileNotFoundError:
        return {}

# Получение названия авиакомпании по IATA-коду из JSON
def get_airline_name(code, airline_data):
    item = airline_data.get(code)
    if item:
        if item["name"] and item["name"] != "null":
            return item["name"]
        en_name = item["name_translations"].get("en", "Неизвестная авиакомпания")
        return en_name
    return f"({code})"

# Получение полного названия города по коду
def get_city_name(code, city_data):
    for city, iata in city_data.items():
        if iata == code:
            return city
    return code  # если не нашли, оставляем IATA

# Получение данных от API
def fetch_flight_prices(
    origin,
    destination=None,
    departure_at=None,
    return_at=None,
    one_way=False,
    adult=1,
    child=0,
    infant=0,
    direct=None
):
    if not origin or len(origin) < 2 or len(origin) > 3:
        raise ValueError("Неверный IATA-код города вылета")

    params = {
        "origin": origin,
        "token": TOKEN,
        "currency": "RUB",
        "one_way": str(one_way).lower(),
        "sorting": "price",
        "limit": 10,
        "page": 1,
        "adults": adult,
        "children": child,
        "infants": infant
    }

    if direct is not None:
        params["direct"] = str(direct).lower()

    if destination:
        params["destination"] = destination

    if departure_at:
        params["departure_at"] = departure_at

    if return_at:
        params["return_at"] = return_at

    response = requests.get(API_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"Ошибка API: {response.status_code}, {response.text}")

    return response.json()

# Форматирование минут в ЧЧ:ММ
def minutes_to_hhmm(minutes):
    if not minutes or minutes <= 0:
        return "—"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}ч {mins}м"

# === ПАРАМЕТРЫ ===
BASE_LINK = "https://www.aviasales.ru"

# Сохранение в CSV
def save_to_csv(data, city_data, airline_data, filename="aviasales_results.csv"):
    fieldnames = [
        "Город отправления",
        "Код отправления",
        "Город назначения",
        "Код назначения",
        "Цена за человека (₽)",
        "Общая цена (₽)",
        "Дата вылета",
        "Дата возвращения",
        "Пересадки",
        "Класс перелёта",
        "Длительность пути туда",
        "Длительность пути обратно",
        "Авиакомпания",
        "Ссылка"
    ]

    total_passengers = adult + child + infant
    class_map = {0: "Эконом", 1: "Бизнес", 2: "Первый"}

    with open(filename, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in data.get("data", []):
            price_per_person = item['price']
            total_price = price_per_person * total_passengers

            link = BASE_LINK + item.get("link", "")

            row = {
                "Город отправления": get_city_name(item['origin'], city_data),
                "Код отправления": item['origin'],
                "Город назначения": get_city_name(item['destination'], city_data),
                "Код назначения": item['destination'],
                "Цена за человека (₽)": price_per_person,
                "Общая цена (₽)": total_price,
                "Дата вылета": item['departure_at'].replace("T", " ").split("+")[0],
                "Дата возвращения": item.get('return_at', '—').replace("T", " ").split("+")[0] if item.get('return_at') else '—',
                "Пересадки": item.get('transfers', 0) + item.get('return_transfers', 0),
                "Класс перелёта": class_map.get(item.get("trip_class", 0), "Неизвестный"),
                "Длительность пути туда": minutes_to_hhmm(item.get('duration_to')),
                "Длительность пути обратно": minutes_to_hhmm(item.get('duration_back')),
                "Авиакомпания": get_airline_name(item.get('airline', 'N/A'), airline_data),
                "Ссылка": link
            }
            writer.writerow(row)
    print(f"\n✅ Результаты сохранены в файл {filename}")


# Сохранение в JSON
def save_to_json(data, city_data, airline_data, filename="aviasales_results.json"):
    enriched_data = []
    class_map = {0: "Эконом", 1: "Бизнес", 2: "Первый"}
    city_map = {code: city for city, code in city_data.items()}

    for item in data.get("data", []):
        origin = item['origin']
        destination = item['destination']
        transfers = item.get('transfers', 0) + item.get('return_transfers', 0)

        enriched_item = {
            "origin_city": get_city_name(origin, city_data),
            "origin_code": origin,
            "destination_city": get_city_name(destination, city_data),
            "destination_code": destination,
            "price_per_person": item['price'],
            "total_price": item['price'] * (adult + child + infant),
            "departure_at": item['departure_at'],
            "return_at": item.get('return_at'),
            "transfers": transfers,
            "trip_class": class_map.get(item.get("trip_class", 0), "Неизвестный"),
            "duration_to": minutes_to_hhmm(item.get('duration_to')),
            "duration_back": minutes_to_hhmm(item.get('duration_back')),
            "airline": get_airline_name(item.get('airline', 'N/A'), airline_data),
            "link": BASE_LINK + item.get("link", "")
        }
        enriched_data.append(enriched_item)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=4)
    print(f"\n✅ Результаты сохранены в файл {filename}")


def search_flights(
    origin_input,         # Город вылета
    destination_input,    # Город назначения или оставить пустым для популярных направлений
    departure_date,       # Дата вылета: DD-MM-YY или YYYY-MM-DD
    return_date,         # Дата возвращения: DD-MM-YY или YYYY-MM-DD
    is_one_way=False,    # Билет в одну сторону?
    direct=False,        # Только прямые рейсы?
    adult=1,            # Взрослых
    child=0,            # Детей
    infant=0,           # Младенцев
    save_results=True   # Сохранять результаты в файлы?
):
    """
    Основная функция поиска авиабилетов.
    
    Returns:
        dict: Результаты поиска в формате JSON
    """
    # Загрузка справочников
    city_data = load_city_codes()
    airline_data = load_airline_data()

    # Обработка дат
    try:
        dep_parsed = parse_date(departure_date)
        ret_parsed = parse_date(return_date) if not is_one_way and return_date else None
    except ValueError as ve:
        raise ValueError(f"Ошибка в формате даты: {ve}")

    # Город вылета
    if len(origin_input) != 3:
        origin = find_iata_code(origin_input, city_data)
    else:
        origin = origin_input.upper()

    if not origin:
        raise ValueError(f"Не удалось найти код города для: {origin_input}")

    # Город назначения
    destination = None
    if destination_input:
        if len(destination_input) != 3:
            destination = find_iata_code(destination_input, city_data)
        else:
            destination = destination_input.upper()

        if not destination:
            raise ValueError(f"Не удалось найти код города для: {destination_input}")

    try:
        results = fetch_flight_prices(
            origin=origin,
            destination=destination,
            departure_at=dep_parsed,
            return_at=ret_parsed if not is_one_way else None,
            one_way=is_one_way,
            adult=adult,
            child=child,
            infant=infant,
            direct=direct
        )

        # if save_results:
        #     save_to_csv(results, city_data, airline_data)
        #     save_to_json(results, city_data, airline_data)
        print(results)
        return results

    except Exception as e:
        raise Exception(f"Ошибка при поиске билетов: {e}")

# === Запуск как скрипт ===
if __name__ == "__main__":
    # Параметры поиска
    params = {
        "origin_input": "Москва",
        "destination_input": "Дубай",
        "departure_date": "10-06-25",
        "return_date": "24-06-25",
        "is_one_way": False,
        "direct": False,
        "adult": 2,
        "child": 1,
        "infant": 0
    }
    
    try:
        results = search_flights(**params)
        print("Поиск выполнен успешно. Результаты сохранены в файлы.")
    except Exception as e:
        print(f"\nПроизошла ошибка: {e}")