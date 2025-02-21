from flask import Flask, jsonify, request, send_from_directory
import requests, os, hashlib

app = Flask(__name__, static_folder="static")

# API-Token über Umgebungsvariable; ansonsten ein Platzhalter
API_TOKEN = os.environ.get('FACTORIAL_API_TOKEN', 'YOUR_API_TOKEN_HERE')
HEADERS = {
    'accept': 'application/json',
    'x-api-key': API_TOKEN
}
BASE_URL = "https://api.factorialhr.com/api/2025-01-01"

# Verwende einen Salt – idealerweise ebenfalls als Umgebungsvariable
SALT = os.environ.get('ID_SALT', 'my_secret_salt')

def generate_own_id(api_id):
    """Erzeugt eine eigene, neutrale ID anhand der originalen API-ID und einem Salt."""
    h = hashlib.sha256(f"{SALT}_{api_id}".encode('utf-8')).hexdigest()
    return h[:8]

# Endpunkt, der nur Initialen liefert (und eigene IDs)
@app.route("/api/staff", methods=["GET"])
def get_staff_initials():
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    staff = []
    for emp in data:
        # Berechne die eigenen ID und nur die Initialen
        own_id = generate_own_id(emp.get("id"))
        initials = (emp.get("first_name", "")[:1].upper() + emp.get("last_name", "")[:1].upper())
        staff.append({
            "ownId": own_id,
            "initials": initials
        })
    return jsonify({"data": staff})

# Endpunkt, der die vollen Namen liefert (mit eigenen IDs)
@app.route("/api/staff_full", methods=["GET"])
def get_staff_full():
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    staff = []
    for emp in data:
        own_id = generate_own_id(emp.get("id"))
        full_name = f"{emp.get('first_name','')} {emp.get('last_name','')}".strip()
        staff.append({
            "ownId": own_id,
            "fullName": full_name
        })
    return jsonify({"data": staff})

@app.route("/api/time_off", methods=["GET"])
def get_time_off():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    url = f"{BASE_URL}/resources/timeoff/leaves?from={from_date}&to={to_date}&include_leave_type=true&include_duration=true"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    # Mapping der Leave-Typen auf neutrale Kategorien
    LEAVE_MAPPING = {
        'Urlaub': 'vacation',
        'Unbezahlter Urlaub': 'vacation',
        'Sonderurlaub': 'vacation',
        'Bildungsurlaub': 'vacation',
        'Sabbatical': 'vacation',
        'Krankheit': 'sick',
        'Krankheit ohne AU': 'sick',
        'Kindkrank': 'sick',
        'Ausgleich für zusätzliche Arbeitszeit': 'overtime',
        'Elternzeit': 'parental',
        'Sonstiges': 'other'
    }
    time_off = []
    for record in data:
        # Transformiere die API-ID in unsere eigene ID
        api_emp_id = record.get("employee_id")
        own_id = generate_own_id(api_emp_id)
        leave_type = record.get("leave_type_name") or record.get("translated_name")
        if leave_type == "Home Office":
            time_off.append({
                "ownId": own_id,
                "isHomeOffice": True
            })
        else:
            category = LEAVE_MAPPING.get(leave_type, "other")
            time_off.append({
                "ownId": own_id,
                "category": category,
                "isHomeOffice": False
            })
    return jsonify({"data": time_off})

@app.route("/api/presence", methods=["GET"])
def get_presence():
    # Hier kommen die eigenen IDs als Query-Parameter (z. B. ownIds[]=...)
    own_ids = request.args.getlist("ownIds[]")
    # Zuerst holen wir die Mitarbeiterliste (original von der API) und erstellen eine Mapping: eigene ID -> API-ID
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    mapping = {}
    for emp in data:
        mapping[generate_own_id(emp.get("id"))] = emp.get("id")
    # Nun erstellen wir eine Liste von API-IDs, basierend auf den angefragten eigenen IDs
    api_ids = []
    for own_id in own_ids:
        if own_id in mapping:
            api_ids.append(mapping[own_id])
    # Anfrage der Anwesenheitsdaten
    params = []
    for aid in api_ids:
        params.append(f"employee_ids[]={aid}")
    query = "&".join(params)
    url = f"{BASE_URL}/resources/attendance/open_shifts?{query}"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    # Erzeuge ein Mapping: API-ID -> Präsenzstatus
    presence = {}
    for record in data:
        if record.get("status") == "opened":
            presence[record.get("employee_id")] = True
    # Konvertiere zurück zu den eigenen IDs
    result = []
    for own_id in own_ids:
        api_id = mapping.get(own_id)
        result.append({
            "ownId": own_id,
            "present": presence.get(api_id, False)
        })
    return jsonify({"data": result})

# Liefert das statische Frontend für Kürzel-Version
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard_initials.html")

# Liefert das statische Frontend für Fullnames-Version
@app.route("/fullnames")
def fullnames():
    return send_from_directory(app.static_folder, "dashboard_full.html")

if __name__ == '__main__':
    app.run(debug=True)
