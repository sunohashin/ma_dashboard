# Mitarbeiter-Dashboard

Dieses Repository enthält ein Flask-Backend und ein statisches Frontend, das ein Mitarbeiter-Dashboard bereitstellt.
Das Backend dient als Proxy zur Factorial-API, sodass der API-Token nicht im Frontend sichtbar ist. Alle Daten werden neutral verarbeitet.

## Zwei Versionen

- **Kürzel-Ansicht** (`/`) – Zeigt Mitarbeiter als Kacheln mit Initialen (z.B. "MK")
- **Vollnamen-Ansicht** (`/fullnames`) – Zeigt Mitarbeiter als Kacheln mit vollem Namen

Beide Versionen zeigen:
- **Anwesenheit** (grüner Hintergrund = eingestempelt)
- **Abwesenheitsart** (farbiger Rahmen: Urlaub, Krank, Überstunden, Elternzeit, Sonstiges)
- **Home Office** (blauer Punkt oben rechts)

## Struktur

- `app.py` – Flask-Anwendung mit API-Endpunkten
- `static/dashboard_initials.html` – Dashboard mit Kürzel-Ansicht
- `static/dashboard_full.html` – Dashboard mit Vollnamen-Ansicht
- `Procfile` – Für den Deployment-Provider (z.B. Render.com)
- `requirements.txt` – Abhängigkeiten

## API-Endpunkte

| Endpunkt | Beschreibung |
|---|---|
| `GET /api/staff` | Mitarbeiterliste mit Initialen |
| `GET /api/staff_full` | Mitarbeiterliste mit vollen Namen |
| `GET /api/time_off?from=YYYY-MM-DD&to=YYYY-MM-DD` | Abwesenheitsdaten |
| `GET /api/presence?ownIds[]=...` | Präsenzdaten (offene Schichten) |

## Deployment

1. Repository auf GitHub bereitstellen.
2. Bei Render.com einen neuen Web Service anlegen und das Repository verbinden.
3. In den Umgebungsvariablen setzen:
   - `FACTORIAL_API_TOKEN` – API-Token für Factorial
   - `ID_SALT` (optional) – Salt für die ID-Generierung
4. Render.com wird das Projekt mithilfe des `Procfile` deployen.

## Lokales Testen

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

pip install -r requirements.txt

export FACTORIAL_API_TOKEN="dein_token"  # Linux/Mac
set FACTORIAL_API_TOKEN=dein_token       # Windows

python app.py
```

Dann im Browser öffnen:
- Kürzel: `http://localhost:5000/`
- Vollnamen: `http://localhost:5000/fullnames`
