from flask import Flask, jsonify, request, send_from_directory
import requests, os, hashlib

app = Flask(__name__, static_folder="static")

# API-Token und Salt aus Umgebungsvariablen; standardmäßig Platzhalter
API_TOKEN = os.environ.get('FACTORIAL_API_TOKEN', 'YOUR_API_TOKEN_HERE')
SALT = os.environ.get('ID_SALT', 'my_secret_salt')
HEADERS = {
    'accept': 'application/json',
    'x-api-key': API_TOKEN
}
BASE_URL = "https://api.factorialhr.com/api/2025-01-01"

def generate_own_id(api_id):
    """
    Generiert eine eigene, neutrale ID aus der API-ID mithilfe eines SHA-256-Hashes.
    Es werden die ersten 8 Hex-Zeichen zurückgegeben.
    """
    h = hashlib.sha256(f"{SALT}_{api_id}".encode('utf-8')).hexdigest()
    return h[:8]

# Mapping der von der API gelieferten Leave-Typen auf neutrale Kategorien.
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

# Endpunkt: Liefert Mitarbeiterdaten mit Initialen (nur Kürzel)
@app.route("/api/staff", methods=["GET"])
def get_staff_initials():
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    staff = []
    for emp in data:
        own_id = generate_own_id(emp.get("id"))
        initials = (emp.get("first_name", "")[:1].upper() + emp.get("last_name", "")[:1].upper())
        staff.append({
            "ownId": own_id,
            "initials": initials
        })
    return jsonify({"data": staff})

# Endpunkt: Liefert Mitarbeiterdaten mit vollen Namen
@app.route("/api/staff_full", methods=["GET"])
def get_staff_full():
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    staff = []
    for emp in data:
        own_id = generate_own_id(emp.get("id"))
        full_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        staff.append({
            "ownId": own_id,
            "fullName": full_name
        })
    return jsonify({"data": staff})

# Endpunkt: Liefert Time-Off-Daten (Leave-Daten) für einen bestimmten Zeitraum
@app.route("/api/time_off", methods=["GET"])
def get_time_off():
    print("DEBUG: Time off API called")
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    url = f"{BASE_URL}/resources/timeoff/leaves?from={from_date}&to={to_date}&include_leave_type=true&include_duration=true"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    time_off = []
    for record in data:
        staff_id = record.get("employee_id")
        leave_type = record.get("leave_type_name") or record.get("translated_name")
        if not leave_type:
            continue
        lt_lower = leave_type.lower()
        # Falls der Leave-Type "Home Office" oder "wfh" (case-insensitive) ist, setzen wir den Home-Office-Indikator
        if lt_lower in ["home office", "wfh"]:
            time_off.append({
                "ownId": generate_own_id(staff_id),
                "isHomeOffice": True
            })
        else:
            # Case-insensitive Suche im Mapping
            category = "other"
            for key, value in LEAVE_MAPPING.items():
                if key.lower() == lt_lower:
                    category = value
                    break
            time_off.append({
                "ownId": generate_own_id(staff_id),
                "category": category,
                "isHomeOffice": False
            })
    return jsonify({"data": time_off})

# Endpunkt: Liefert Präsenzdaten basierend auf offenen Schichten
@app.route("/api/presence", methods=["GET"])
def get_presence():
    print("DEBUG: Presence API called")
    # Das Frontend übermittelt eigene IDs (ownIds[]), nicht die API-ID
    own_ids = request.args.getlist("ownIds[]")
    # Erzeuge ein Mapping: eigene ID -> API-ID
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    mapping = {}
    for emp in data:
        mapping[generate_own_id(emp.get("id"))] = emp.get("id")
    # Erzeuge eine Liste von API-IDs basierend auf den angefragten eigenen IDs
    api_ids = []
    for oid in own_ids:
        if oid in mapping:
            api_ids.append(mapping[oid])

    # Debug logging
    print(f"DEBUG: Requested own_ids: {own_ids}")
    print(f"DEBUG: Mapped to API IDs: {api_ids}")

    # Don't proceed if no valid IDs
    if not api_ids:
        print("DEBUG: No valid employee IDs found!")
        return jsonify({"data": [], "error": "No valid employee IDs found"})

    params = []
    for aid in api_ids:
        params.append(f"employee_ids[]={aid}")
    query = "&".join(params)
    url = f"{BASE_URL}/resources/attendance/open_shifts?{query}"

    print(f"DEBUG: Calling API with URL: {url}")
    response = requests.get(url, headers=HEADERS)

    # Check if API call succeeded
    if response.status_code != 200:
        print(f"DEBUG: API error: {response.status_code}, {response.text}")
        return jsonify({"data": [], "error": f"API error: {response.status_code}"})

    data = response.json().get("data", [])
    print(f"DEBUG: API returned {len(data)} records")

    presence = {}
    for record in data:
        employee_id = record.get("employee_id")
        status = record.get("status")
        print(f"DEBUG: Record - Employee ID: {employee_id}, Status: {status}")

        if status == "opened":
            presence[employee_id] = True

    result = []
    for oid in own_ids:
        api_id = mapping.get(oid)
        present_status = presence.get(api_id, False)
        print(f"DEBUG: Setting employee {oid} (API ID: {api_id}) presence to {present_status}")

        result.append({
            "ownId": oid,
            "present": present_status
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
