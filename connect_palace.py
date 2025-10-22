import requests
import json

# URL base del servidor
BASE_URL = "https://office-hours-buildathon.palaceresorts.com/api"

# --- 1. Verificar salud del servidor ---
health = requests.get(f"{BASE_URL.replace('/api','')}/health").json()
print("✅ Estado del servidor:")
print(json.dumps(health, indent=2))

# --- 2. Obtener estadísticas globales ---
stats = requests.get(f"{BASE_URL}/stats").json()
print("\n📊 Estadísticas del sistema:")
print(json.dumps(stats, indent=2)[:600])

# --- 3. Calcular un precio dinámico ---
payload = {
    "property_id": "moon_cancun",
    "room_type": "suite_swim_up",
    "check_in_date": "2025-12-20",
    "check_out_date": "2025-12-27",
    "num_guests": 4,
    "customer_segment": "seg_family_traditional"
}

price = requests.post(f"{BASE_URL}/pricing", json=payload).json()
print("\n💰 Resultado del cálculo dinámico:")
print(json.dumps(price, indent=2))
