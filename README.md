# Finanz-Agent

Persönlicher Finanz-Assistent: erfasst deine Finanzdaten, ruft Markt-/BTC-Daten automatisch ab, berechnet daraus deterministisch Kennzahlen und einen Investment-Score, und lässt ein LLM diese bereits berechneten Daten optional in verständlicher Sprache einordnen.

**Wichtig:** Diese Anwendung ist kein Ersatz für professionelle Finanzberatung. Jede angezeigte Kennzahl/jeder Score ist nachvollziehbar aus den zugrunde liegenden Daten berechnet (nie vom LLM erfunden) und mit Zeitstempel/Quelle versehen. Nicht verfügbare Datenquellen werden explizit als `unavailable` markiert, nie durch Schätzwerte ersetzt.

## Inhalt

- [Architektur](#architektur)
- [Voraussetzungen](#voraussetzungen)
- [Installation & lokaler Start](#installation--lokaler-start)
- [Environment-Variablen](#environment-variablen)
- [Datenbank](#datenbank)
- [API](#api)
- [Tests](#tests)
- [Deployment (Docker)](#deployment-docker)

## Architektur

```
backend/                    FastAPI + SQLAlchemy
  app/
    core/                   Settings, Security (bcrypt/Session), Logging, Rate-Limiting, Deps
    db/                     DB-Engine/Session, Base
    models/                 SQLAlchemy-Modelle (User, FinancialEntry, NetWorthSnapshot,
                             MarketDataPoint, ScoringWeightsConfig, ScoreHistory, Transaction)
    schemas/                Pydantic Request/Response-Schemas
    routers/                HTTP-Layer (dünn, delegiert an services/)
    services/                Business-Logik (Finanzen, Portfolio, Markt, Score, Dashboard, Chat)
    providers/                Provider-Abstraktion für externe Datenquellen (CoinGecko,
                             alternative.me, Mock) — austauschbar, nie direkter API-Zugriff
                             aus services/
    scoring/                  Deterministische Score-Engine (engine.py + subscores/*)
    llm/                       Anthropic-Anbindung, ausschließlich zur Formulierung bereits
                             berechneter Daten ("compute first, phrase second")
  alembic/                    DB-Migrationen (DB-agnostisch: SQLite lokal, Postgres via Docker)
  tests/                       pytest — Scoring, Services, Provider, Router

frontend/                     Next.js 16 (App Router) + TypeScript + Tailwind CSS
  app/                         Seiten (Login, Dashboard, Finanzen, Score, Chat)
  components/                  UI-Komponenten (Dashboard-Cards, Charts, Formulare)
  lib/                          API-Client, React-Query-Hooks, Typen
  proxy.ts                     Next.js 16 "Proxy" (früher middleware.ts) — optimistischer
                             Auth-Check, echte Prüfung erfolgt pro Request im Backend

docker-compose.yml             Postgres + Backend + Frontend (vorbereitet für späteres Deployment)
```

**Kernprinzipien:**
- Jede externe Datenquelle läuft über eine `Provider`-Abstraktion (`app/providers/base.py`); nicht verfügbare/fehlgeschlagene Abrufe werden als `status: unavailable/error` gespeichert, nie stillschweigend durch erfundene Werte ersetzt.
- Jeder Markt-/Finanzdatenpunkt wird mit Zeitstempel und Quelle in `MarketDataPoint` persistiert.
- Der BTC Investment Score wird ausschließlich deterministisch im Backend berechnet (`app/scoring/engine.py`), mit konfigurierbaren, versionierten Gewichtungen (DB-Tabelle `scoring_weights_configs`, initial aus `app/config/default_scoring_weights.yaml` geseedet). Nicht verfügbare Teil-Scores werden transparent aus der Gewichtssumme herausgerechnet (Renormierung), nie stillschweigend als 0 gewertet.
- Das LLM (Anthropic Claude) bekommt beim Chat-Assistenten ausschließlich bereits berechnete Zahlen als JSON — es rechnet nichts selbst. Ohne `ANTHROPIC_API_KEY` degradiert die Funktion sauber zu "nicht konfiguriert", die App bleibt voll nutzbar.

## Voraussetzungen

- Python 3.12+ (getestet mit 3.14)
- Node.js 20+ und npm
- Optional für Postgres/Deployment: Docker + Docker Compose

## Installation & lokaler Start

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; unter Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

cp ../.env.example .env       # dann SECRET_KEY etc. anpassen, siehe unten
python -m alembic upgrade head

# Einmalig den Single-User-Account anlegen (kein öffentliches Signup vorgesehen):
python scripts/create_user.py --username admin --password "dein-passwort"

uvicorn app.main:app --reload --port 8000
```

Backend läuft danach unter `http://localhost:8000` (Health-Check: `GET /api/health`, interaktive Doku: `/docs`).

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # falls vorhanden, sonst manuell NEXT_PUBLIC_API_URL setzen
npm run dev
```

Frontend läuft danach unter `http://localhost:3000` und leitet nicht angemeldete Nutzer automatisch zu `/login` um.

## Environment-Variablen

Siehe [`.env.example`](.env.example) im Root für die vollständige Liste. Wichtigste Variablen:

| Variable | Beschreibung | Default |
|---|---|---|
| `DATABASE_URL` | DB-Verbindung. Lokal SQLite (kein Setup nötig), für Postgres z. B. `postgresql+psycopg2://user:pass@host:5432/db` | SQLite-Datei im `backend/`-Verzeichnis |
| `SECRET_KEY` | Signiert die Session-Cookies. **Muss** in Produktion überschrieben werden. | Platzhalter |
| `ANTHROPIC_API_KEY` | Optional. Ohne Key degradiert der Chat-Assistent sauber zu "nicht konfiguriert". | leer |
| `ANTHROPIC_MODEL` | Anthropic-Modell für den Chat-Assistenten | `claude-sonnet-4-5` |
| `MARKET_DATA_MODE` | `live` (echte APIs) oder `mock` (deterministische Testdaten, kein Netzwerk nötig) | `live` |
| `BOOTSTRAP_USERNAME` / `BOOTSTRAP_PASSWORD` | Nur für `scripts/create_user.py` als Default-Werte | `admin` / `changeme` |
| `NEXT_PUBLIC_API_URL` | Backend-URL, die das Frontend im Browser anspricht | `http://localhost:8000` |

**Nie Secrets ins Repository committen** — `.env`-Dateien sind per `.gitignore` ausgeschlossen.

## Datenbank

- Lokal: SQLite, keine separate Installation nötig. Die Datei liegt in `backend/` (Pfad wird absolut aus `Settings.database_url` aufgelöst, unabhängig vom Arbeitsverzeichnis des Prozesses).
- Migrationen: Alembic (`backend/alembic/`). Alle Modelle sind dialektneutral geschrieben (kein `JSONB`/`ARRAY` etc.), sodass dieselben Migrationen unverändert gegen Postgres laufen.
- Neue Migration nach Modelländerung erzeugen:
  ```bash
  cd backend
  python -m alembic revision --autogenerate -m "beschreibung"
  python -m alembic upgrade head
  ```
- Für Postgres (z. B. via `docker-compose.yml`) einfach `DATABASE_URL` auf die Postgres-Verbindung setzen — keine Codeänderung nötig.

## API

Vollständige, interaktive Dokumentation unter `http://localhost:8000/docs` (Swagger UI), sobald das Backend läuft. Überblick der wichtigsten Endpunkte:

```
POST   /api/auth/login              /api/auth/logout            GET /api/auth/me
GET    /api/financials/entries      POST/PUT/DELETE .../entries/{id}
GET    /api/financials/net-worth-history
GET    /api/financials/net-worth/current
GET    /api/financials/net-worth/change?days=30
GET    /api/portfolio/allocation
GET    /api/market/btc-price        /api/market/fear-greed      /api/market/snapshot
GET    /api/score/current           /api/score/history
GET    /api/dashboard
GET    /api/chat/status             POST /api/chat/message
```

Alle Endpunkte außer `/api/auth/login` erfordern eine authentifizierte Session (httpOnly-Cookie). `/api/auth/login` und `/api/chat/message` sind zusätzlich rate-limitiert.

## Tests

```bash
cd backend
python -m pytest              # läuft komplett gegen In-Memory-SQLite + Mock-Provider, keine Live-API-Calls
```

69 Tests decken ab: Score-Engine (Gewichts-Renormierung, Grenzfälle), Sub-Score-Module, Finanz-/Portfolio-Berechnungen, Provider (gegen Fixtures), Router-Smoke-Tests, sowie die LLM-Graceful-Degradation (mit/ohne API-Key, Fehlerfall).

Frontend-Qualitätssicherung:

```bash
cd frontend
npm run lint     # ESLint
npm run build    # Next.js Build inkl. TypeScript-Check
```

## Deployment (Docker)

`docker-compose.yml` im Root startet Postgres, Backend und Frontend zusammen:

```bash
cp .env.example .env    # Werte anpassen, insbesondere SECRET_KEY, POSTGRES_*, ANTHROPIC_API_KEY
docker compose up --build
```

- `backend`: baut aus `backend/Dockerfile`, wendet beim Start automatisch `alembic upgrade head` an, läuft auf Port 8000.
- `frontend`: baut aus `frontend/Dockerfile` (Next.js `output: "standalone"`), läuft auf Port 3000.
- `db`: `postgres:16-alpine` mit persistentem Volume.

Für eine Cloud-Bereitstellung genügt es, dieselben Images/Env-Variablen gegen eine verwaltete Postgres-Instanz laufen zu lassen; die Architektur ist dafür bereits vorbereitet (keine SQLite-spezifische Logik im Code).
