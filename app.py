import streamlit as st
import requests
import datetime
from datetime import timedelta
import json

# Set page configuration
st.set_page_config(
    page_title="Планировщик Путешествий",
    page_icon="✈️",
    layout="wide"
)

# App title
st.title("✈️ Планировщик Путешествий")
st.markdown("Введите детали вашего путешествия для получения рекомендаций")

# Create a form for user inputs
with st.form("travel_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        departure_city = st.text_input("Город отправления", "Москва")
        destination_city = st.text_input("Город назначения", "")
        
        # Get today's date for defaults and validation
        today = datetime.date.today()
        # Set default departure date to a week from now
        default_departure = today + timedelta(days=7)
        
        # Make sure dates are within reasonable ranges
        departure_date = st.date_input(
            "Дата отправления",
            default_departure,
            min_value=today,
            max_value=today + timedelta(days=365)
        )
        
        # Set return date to be a week after departure by default
        default_return = departure_date + timedelta(days=7)
        return_date = st.date_input(
            "Дата возвращения",
            default_return,
            min_value=departure_date,
            max_value=departure_date + timedelta(days=30)
        )
        
    with col2:
        is_one_way = st.checkbox("В одну сторону")
        direct_flights = st.checkbox("Только прямые рейсы")
        
        flight_class = st.selectbox(
            "Класс полета",
            ["economy", "business", "first"],
            format_func=lambda x: {"economy": "Эконом", "business": "Бизнес", "first": "Первый"}[x]
        )
        
        # Change label to show budget in USD
        budget = st.number_input("Бюджет ($)", min_value=50, value=500)
        # Convert budget to rubles for API (since API expects rubles)
        budget_rub = budget * 90.0  # Using same conversion rate as API
        
        col_adults, col_children, col_infants = st.columns(3)
        with col_adults:
            adults = st.number_input("Взрослые", min_value=1, max_value=9, value=1)
        with col_children:
            children = st.number_input("Дети", min_value=0, max_value=9, value=0)
        with col_infants:
            infants = st.number_input("Младенцы", min_value=0, max_value=9, value=0)
    
    preferences = st.multiselect(
        "Предпочтения",
        ["active", "art", "beach"],
        format_func=lambda x: {"active": "Активный отдых", "art": "Искусство и культура", "beach": "Пляжный отдых"}[x],
        default=["active"]  # Default to active tourism
    )
    
    # Make the submit button more visible
    submitted = st.form_submit_button("Найти рекомендации", use_container_width=True)

# Process form submission
if submitted:
    # Check if destination city is provided
    if not destination_city:
        st.error("Пожалуйста, укажите город назначения.")
    # Check if preferences are selected
    elif not preferences:
        st.error("Пожалуйста, выберите хотя бы одно предпочтение.")
    else:
        with st.spinner('Получение рекомендаций...'):
            try:
                # Prepare request payload
                payload = {
                    "departure_city": departure_city,
                    "destination_city": destination_city,
                    "departure_date": departure_date.strftime('%Y-%m-%d'),
                    "return_date": None if is_one_way else return_date.strftime('%Y-%m-%d'),
                    "flight_class": flight_class,
                    "budget": budget_rub,  # Send budget in rubles to API
                    "adults": adults,
                    "children": children,
                    "infants": infants,
                    "is_one_way": is_one_way,
                    "direct_flights": direct_flights,
                    "preferences": preferences
                }
                
                # Make API request
                response = requests.post(
                    "http://api:8000/recommend",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60  # Increase timeout to 60 seconds
                )
                
                if response.status_code == 200:
                    # Process the response sections separately for better rendering
                    response_text = response.text
                    
                    # Split the response into sections
                    sections = response_text.split('---')
                    
                    if len(sections) >= 3:
                        # Flights and hotels info
                        st.markdown(sections[0], unsafe_allow_html=True)
                        
                        # Recommendations
                        st.markdown("---")
                        st.markdown(sections[1], unsafe_allow_html=True)
                        
                        # Checklist section
                        st.markdown("---")
                        st.markdown(sections[2], unsafe_allow_html=True)
                    else:
                        # Fallback if the response format is unexpected
                        st.markdown(response_text, unsafe_allow_html=True)
                else:
                    st.error(f"Ошибка: {response.status_code} - {response.text}")
                    
            except Exception as e:
                st.error(f"Произошла ошибка: {str(e)}")

# Footer
st.markdown("---")
st.markdown("💼 Планировщик путешествий | Создайте идеальное путешествие")