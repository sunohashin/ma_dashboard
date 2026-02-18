from flask import Flask, jsonify, request, send_from_directory
import requests, os, hashlib, logging

app = Flask(__name__, static_folder="static")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API-Token und Salt aus Umgebungsvariablen
API_TOKEN = os.environ.get('FACTORIAL_API_TOKEN', 'YOUR_API_TOKEN_HERE')
SALT = os.environ.get('ID_SALT', 'my_secret_salt')
HEADERS = {
    'accept': 'application/json',
    'x-api-key': API_TOKEN
}
BASE_URL = "https://api.factorialhr.com/api/2025-01-01"

def generate_own_id(api_id):
    """Generiert eine eigene, neutrale ID aus der API-ID mithilfe eines SHA-256-Hashes."""
    h = hashlib.sha256(f"{SALT}_{api_id}".encode('utf-8')).hexdigest()
    return h[:8]

# Mapping der Leave-Typen auf neutrale Kategorien
LEAVE_MAPPING = {
    'urlaub': 'vacation',
    'unbezahlter urlaub': 'vacation',
    'sonderurlaub': 'vacation',
    'bildungsurlaub': 'vacation',
    'sabbatical': 'vacation',
    'krankheit': 'sick',
    'krankheit ohne au': 'sick',
    'kindkrank': 'sick',
    'ausgleich für zusätzliche arbeitszeit': 'overtime',
    'elternzeit': 'parental',
    'sonstiges': 'other'
}

def fetch_active_employees():
    """Holt alle aktiven Mitarbeiter von der Factorial-API."""
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json().get("data", [])

# Endpunkt: Liefert Mitarbeiterdaten mit Initialen (nur Kürzel)
@app.route("/api/staff", methods=["GET"])
def get_staff_initials():
    try:
        data = fetch_active_employees()
        staff = []
        for emp in data:
            own_id = generate_own_id(emp.get("id"))
            first = emp.get("first_name", "")
            last = emp.get("last_name", "")
            initials = (first[:1] + last[:1]).upper()
            staff.append({"ownId": own_id, "initials": initials})
        return jsonify({"data": staff})
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Mitarbeiter: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

# Endpunkt: Liefert Mitarbeiterdaten mit vollen Namen
@app.route("/api/staff_full", methods=["GET"])
def get_staff_full():
    try:
        data = fetch_active_employees()
        staff = []
        for emp in data:
            own_id = generate_own_id(emp.get("id"))
            full_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
            staff.append({"ownId": own_id, "fullName": full_name})
        return jsonify({"data": staff})
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Mitarbeiter: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

# Endpunkt: Liefert Time-Off-Daten (Leave-Daten) für einen bestimmten Zeitraum
@app.route("/api/time_off", methods=["GET"])
def get_time_off():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    if not from_date or not to_date:
        return jsonify({"data": [], "error": "Parameter 'from' und 'to' erforderlich"}), 400
    try:
        url = f"{BASE_URL}/resources/timeoff/leaves?from={from_date}&to={to_date}&include_leave_type=true&include_duration=true"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json().get("data", [])
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Time-Off-Daten: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

    time_off = []
    for record in data:
        staff_id = record.get("employee_id")
        leave_type = record.get("leave_type_name") or record.get("translated_name")
        if not leave_type:
            continue
        lt_lower = leave_type.lower().strip()
        if lt_lower in ("home office", "wfh"):
            time_off.append({
                "ownId": generate_own_id(staff_id),
                "isHomeOffice": True
            })
        else:
            category = LEAVE_MAPPING.get(lt_lower, "other")
            time_off.append({
                "ownId": generate_own_id(staff_id),
                "category": category,
                "isHomeOffice": False
            })
    return jsonify({"data": time_off})

# Endpunkt: Liefert Präsenzdaten basierend auf offenen Schichten
@app.route("/api/presence", methods=["GET"])
def get_presence():
    own_ids = request.args.getlist("ownIds[]")
    if not own_ids:
        return jsonify({"data": []})
    try:
        data = fetch_active_employees()
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Mitarbeiter: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

    # Mapping: eigene ID -> API-ID
    mapping = {}
    for emp in data:
        mapping[generate_own_id(emp.get("id"))] = emp.get("id")

    api_ids = [mapping[oid] for oid in own_ids if oid in mapping]
    if not api_ids:
        return jsonify({"data": []})

    try:
        query = "&".join(f"employee_ids[]={aid}" for aid in api_ids)
        url = f"{BASE_URL}/resources/attendance/open_shifts?{query}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        shift_data = response.json().get("data", [])
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Präsenzdaten: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

    presence = {}
    for record in shift_data:
        if record.get("status") == "opened":
            presence[record.get("employee_id")] = True

    result = []
    for oid in own_ids:
        api_id = mapping.get(oid)
        result.append({
            "ownId": oid,
            "present": presence.get(api_id, False)
        })
    return jsonify({"data": result})

# Liefert das statische Frontend für die Initialen-Version
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard_initials.html")

# Liefert das statische Frontend für die Vollnamen-Version
@app.route("/fullnames")
def fullnames():
    return send_from_directory(app.static_folder, "dashboard_full.html")

if __name__ == '__main__':
    app.run(debug=True)
