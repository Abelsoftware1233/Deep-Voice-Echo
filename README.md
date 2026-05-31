# AI-Resilience Threat monitor 

Real-time AI security assessment dashboard with Flask backend, live system scanning, and SQLite history.

## Projectstructuur

```
ai-resilience/
├── app.py                  ← Flask server + API routes
├── requirements.txt
├── resilience.db           ← SQLite database (aangemaakt automatisch)
├── modules/
│   ├── scanner.py          ← Echte systeemscans (psutil, socket, subprocess)
│   └── database.py         ← SQLite init, opslaan, queries
├── templates/
│   └── index.html          ← Frontend (geserveerd door Flask)
└── static/
    ├── style.css
    └── script.js
```

## Installatie & starten

```bash
# 1. Installeer dependencies
pip install -r requirements.txt

# 2. Start de server
python app.py

# 3. Open in browser
http://localhost:5000
```

## API Endpoints

| Method | Route          | Beschrijving                            |
|--------|----------------|-----------------------------------------|
| GET    | /              | Frontend dashboard                      |
| POST   | /api/scan      | Run scan (body: `{"vector": "full"}`)   |
| GET    | /api/snapshot  | Live systeem metrics (geen DB write)    |
| GET    | /api/history   | Scan geschiedenis uit SQLite DB         |
| GET    | /api/stats     | Geaggregeerde statistieken per vector   |

### Vector opties voor /api/scan
- `full` — volledige spectrum scan
- `cognitive` — cognitieve hijacking analyse
- `llm` — LLM prompt injection check
- `audio` — audio deepfake analyse
- `adversarial` — adversarial input check
- `crypto` — cryptografische gereedheid
- `supply` — supply chain integriteit

## Wat er echt gescand wordt

- **Poorten** — luisterende TCP/UDP poorten via psutil, risico-classificatie
- **Processen** — actieve AI/LLM gerelateerde processen (ollama, flask, uvicorn, etc.)
- **Netwerk** — actieve verbindingen, externe IPs
- **Crypto** — OpenSSL versie, GPG aanwezigheid, SSH key types
- **Systeem** — CPU, geheugen, disk, hostname

Alle bevindingen zijn theoretische risico-assessments gebaseerd op echte systeemdata.

## Noot

Vereist `psutil` voor systeemscans. Op Linux/Mac zijn sommige netwerk-checks beperkt
zonder root/sudo — draai met `sudo python app.py` voor volledige poort/connectie info.
