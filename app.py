from flask import Flask, jsonify, request, send_from_directory
from datetime import date, timedelta
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

# Detailliertes Mapping: Behält Krankheits-Subtypen bei
LEAVE_TYPE_DETAIL = {
    'urlaub': 'Urlaub',
    'unbezahlter urlaub': 'Urlaub',
    'sonderurlaub': 'Urlaub',
    'bildungsurlaub': 'Urlaub',
    'sabbatical': 'Urlaub',
    'krankheit': 'Krankheit',
    'krankheit ohne au': 'Krankheit ohne AU',
    'kindkrank': 'Kindkrank',
    'ausgleich für zusätzliche arbeitszeit': 'Überstunden',
    'elternzeit': 'Elternzeit',
    'sonstiges': 'Sonstiges'
}

ALL_CATEGORIES = ['Urlaub', 'Krankheit', 'Krankheit ohne AU', 'Kindkrank',
                  'Überstunden', 'Elternzeit', 'Sonstiges']

def fetch_active_employees():
    """Holt alle aktiven Mitarbeiter von der Factorial-API."""
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json().get("data", [])

def fetch_all_leaves(from_date, to_date):
    """Holt alle Leave-Daten für einen Zeitraum mit Paginierung."""
    all_leaves = []
    page = 1
    while page <= 50:
        url = (f"{BASE_URL}/resources/timeoff/leaves?"
               f"from={from_date}&to={to_date}"
               f"&include_leave_type=true&include_duration=true"
               f"&page={page}")
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        all_leaves.extend(data)
        page += 1
    return all_leaves

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

# Endpunkt: Abwesenheitsbericht – Urlaubs- und Krankheitstage je Mitarbeiter pro Monat
@app.route("/api/leave_report", methods=["GET"])
def get_leave_report():
    year = request.args.get("year", str(date.today().year))
    try:
        year_int = int(year)
    except ValueError:
        return jsonify({"data": [], "error": "Ungültiges Jahr"}), 400

    from_date = f"{year_int}-01-01"
    to_date = f"{year_int}-12-31"

    try:
        employees = fetch_active_employees()
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Mitarbeiter: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

    emp_map = {}
    for emp in employees:
        api_id = emp.get("id")
        own_id = generate_own_id(api_id)
        full_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        emp_map[api_id] = {"ownId": own_id, "fullName": full_name}

    try:
        leaves = fetch_all_leaves(from_date, to_date)
    except requests.RequestException as e:
        logger.error("Fehler beim Abrufen der Leave-Daten: %s", e)
        return jsonify({"data": [], "error": "API-Fehler"}), 502

    # Report initialisieren: ownId -> {fullName, months: {1..12: {Kategorie: Tage}}}
    report = {}
    for api_id, info in emp_map.items():
        report[info["ownId"]] = {
            "fullName": info["fullName"],
            "months": {str(m): {} for m in range(1, 13)}
        }

    for leave in leaves:
        emp_id = leave.get("employee_id")
        if emp_id not in emp_map:
            continue

        leave_type = leave.get("leave_type_name") or leave.get("translated_name")
        if not leave_type:
            continue

        lt_lower = leave_type.lower().strip()
        if lt_lower in ("home office", "wfh"):
            continue

        category = LEAVE_TYPE_DETAIL.get(lt_lower, "Sonstiges")
        own_id = emp_map[emp_id]["ownId"]

        start_str = leave.get("start_on")
        finish_str = leave.get("finish_on")
        is_half = leave.get("half_day", False)

        if not start_str or not finish_str:
            continue

        try:
            start_d = date.fromisoformat(start_str)
            finish_d = date.fromisoformat(finish_str)
        except (ValueError, TypeError):
            continue

        # Halber Tag: nur bei eintägiger Abwesenheit
        if is_half and start_d == finish_d:
            if start_d.year == year_int and start_d.weekday() < 5:
                ms = str(start_d.month)
                report[own_id]["months"][ms][category] = \
                    report[own_id]["months"][ms].get(category, 0) + 0.5
        else:
            current = start_d
            while current <= finish_d:
                if current.year == year_int and current.weekday() < 5:
                    ms = str(current.month)
                    report[own_id]["months"][ms][category] = \
                        report[own_id]["months"][ms].get(category, 0) + 1
                current += timedelta(days=1)

    result = []
    for own_id, data in report.items():
        result.append({
            "ownId": own_id,
            "fullName": data["fullName"],
            "months": data["months"]
        })

    return jsonify({"data": result, "categories": ALL_CATEGORIES})

# Liefert das statische Frontend für die Initialen-Version
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard_initials.html")

# Liefert das statische Frontend für die Vollnamen-Version
@app.route("/fullnames")
def fullnames():
    return send_from_directory(app.static_folder, "dashboard_full.html")

# Liefert den Abwesenheitsbericht
@app.route("/leave-report")
def leave_report():
    return send_from_directory(app.static_folder, "leave_report.html")

if __name__ == '__main__':
    app.run(debug=True)
