# Mitarbeiter-Dashboard

Dieses Repository enthält ein Flask-Backend und ein statisches Frontend, das ein Mitarbeiter-Dashboard bereitstellt.  
Das Backend dient als Proxy zur Factorial-API, sodass der API-Token nicht im Frontend sichtbar ist. Alle Daten werden neutral verarbeitet.

## Struktur

- `app.py` – Flask-Anwendung mit API-Endpunkten
- `Procfile` – Für den Deployment-Provider (z.B. Render.com)
- `requirements.txt` – Abhängigkeiten
- `static/dashboard.html` – Das Frontend-Dashboard
- `README.md` – Diese Anleitung

## Deployment

1. Repository auf GitHub (oder einem anderen Git-Provider) bereitstellen.
2. Bei Render.com einen neuen Web Service anlegen und das Repository verbinden.
3. In den Umgebungsvariablen den API-Token unter `FACTORIAL_API_TOKEN` setzen.
4. Render.com wird das Projekt mithilfe des `Procfile` deployen.

## Lokales Testen

1. Erstelle ein virtuelles Environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
