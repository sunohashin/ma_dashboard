from flask import Flask, jsonify, request, send_from_directory
import requests, os

app = Flask(__name__, static_folder="static")

# Den API-Token über eine Umgebungsvariable setzen
API_TOKEN = os.environ.get('FACTORIAL_API_TOKEN', 'YOUR_API_TOKEN_HERE')
HEADERS = {
    'accept': 'application/json',
    'x-api-key': API_TOKEN
}
BASE_URL = "https://api.factorialhr.com/api/2025-01-01"

# Mapping der von Factorial gelieferten Leave-Typen auf neutrale Kategorien
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

@app.route("/fullnames")
def fullnames():
    return send_from_directory(app.static_folder, "fullnames.html")

@app.route("/api/staff", methods=["GET"])
def get_staff():
    url = f"{BASE_URL}/resources/employees/employees?only_active=true&only_managers=false"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    staff = []
    for emp in data:
        staff.append({
            "staffId": emp.get("id"),
            "firstName": emp.get("first_name"),
            "lastName": emp.get("last_name")
        })
    return jsonify({"data": staff})

@app.route("/api/time_off", methods=["GET"])
def get_time_off():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    url = f"{BASE_URL}/resources/timeoff/leaves?from={from_date}&to={to_date}&include_leave_type=true&include_duration=true"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    time_off = []
    for record in data:
        staff_id = record.get("employee_id")
        leave_type = record.get("leave_type_name") or record.get("translated_name")
        # "Home Office" behandeln wir separat – er soll nur den Remote-Indikator auslösen
        if leave_type == "Home Office":
            time_off.append({
                "staffId": staff_id,
                "isHomeOffice": True
            })
        else:
            category = LEAVE_MAPPING.get(leave_type, "other")
            time_off.append({
                "staffId": staff_id,
                "category": category,
                "isHomeOffice": False
            })
    return jsonify({"data": time_off})

@app.route("/api/presence", methods=["GET"])
def get_presence():
    staff_ids = request.args.getlist("employee_ids[]")
    params = []
    for sid in staff_ids:
        params.append(f"employee_ids[]={sid}")
    query = "&".join(params)
    url = f"{BASE_URL}/resources/attendance/open_shifts?{query}"
    response = requests.get(url, headers=HEADERS)
    data = response.json().get("data", [])
    presence = {}
    for record in data:
        staff_id = record.get("employee_id")
        if record.get("status") == "opened":
            presence[staff_id] = True
    result = []
    for sid in staff_ids:
        result.append({
            "staffId": int(sid),
            "present": presence.get(int(sid), False)
        })
    return jsonify({"data": result})

# Liefert das statische Frontend (dashboard.html)
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "dashboard.html")

if __name__ == '__main__':
    app.run(debug=True)
