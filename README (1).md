# Kolada MCP Server

MCP-server som exponerar [Koladas öppna API](https://api.kolada.se/v2/) som verktyg för AI-agenter (t.ex. n8n AI Agent).

Byggd för Länsstyrelsen i Västra Götaland. Samma tech-stack som `scb-mcp-v2`: **FastMCP + httpx + Render.com**.

## Verktyg som exponeras

| Verktyg | Beskrivning |
|---|---|
| `kolada_search_kpi` | Sök efter nyckeltal (KPI) på fritext i titel |
| `kolada_get_kpi_metadata` | Hämta fullständig metadata för ett KPI |
| `kolada_get_data` | Hämta värden (KPI × kommun × år) |
| `kolada_list_vg_municipalities` | Lista VG:s 49 kommuner med ID |
| `kolada_compare_municipalities` | Jämförelsetabell mellan flera kommuner |

## Deploy på Render — steg för steg

### 1. Skapa nytt GitHub-repo

1. Gå till `github.com/Larjaklin` → **New repository**
2. Namn: `kolada-mcp` (eller valfritt)
3. Välj **Public** eller **Private** (båda fungerar med Render)
4. Initiera med README (klicka i rutan)
5. Klicka **Create repository**

### 2. Ladda upp filerna

I det nya repot, klicka **Add file → Create new file** för var och en:

| Filnamn | Innehåll |
|---|---|
| `server.py` | Kopiera innehållet från motsvarande fil i detta paket |
| `requirements.txt` | Kopiera innehållet |
| `render.yaml` | Kopiera innehållet (valfritt, men rekommenderas) |

Alternativt: klistra in alla filer direkt via **Add file → Upload files**.

### 3. Skapa tjänst på Render

1. Gå till `dashboard.render.com` → **New → Web Service**
2. Välj **Build and deploy from a Git repository**
3. Anslut ditt `kolada-mcp`-repo
4. Inställningar:
   - **Name:** `kolada-mcp` (eller valfritt)
   - **Region:** Frankfurt (samma som scb-mcp-v2)
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Plan:** Free
5. Klicka **Create Web Service**

Första bygget tar 2–3 minuter.

### 4. Testa att servern svarar

När Render visar "Live" (grön badge), öppna Logs-fliken. Du ska se en rad med:
```
Startar Kolada MCP-server på 0.0.0.0:8000
```

Servern är nu nåbar på `https://<ditt-servicenamn>.onrender.com/mcp`.

### 5. Anslut i n8n

I ditt `SCB agent`-workflow, öppna `MCP Client Kolada`-noden och ange:

- **Endpoint URL:** `https://<ditt-servicenamn>.onrender.com/mcp`
- **Server Transport:** `HTTP Streamable`
- **Authentication:** None

Klicka **Execute step** — om det fungerar ser du listan med 5 verktyg.

## Testfrågor att ställa agenten

- *"Vilka KPI:er finns i Kolada som handlar om behörighet till gymnasiet?"*
- *"Jämför andelen elever i årskurs 9 som är behöriga till gymnasiet i Mariestad, Lidköping och Skövde 2023."*
- *"Hur har nettokostnaden per invånare för grundskola utvecklats i Göteborg de senaste fem åren?"*

## Felsökning

### Första anropet tar 50+ sekunder
Normalt på Render Free — tjänsten spinnar ner efter 15 min inaktivitet. Uppgradera till Starter ($7/mån) om det är problem.

### "Service Suspended"
Du har slut på månatliga free-timmar (750h/mån). Vänta till månadsskifte eller uppgradera.

### Agent hittar inte verktygen
Kontrollera att URL:en slutar med `/mcp` och att Transport är satt till `HTTP Streamable`.

## Källor

- Kolada API v2: https://github.com/Hypergene/kolada
- FastMCP: https://github.com/jlowin/fastmcp
- Kommunkoder: SCB, 2026
