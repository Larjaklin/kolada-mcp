"""
Kolada MCP Server
==================
MCP-server som exponerar Koladas öppna API (https://api.kolada.se/v2/)
som verktyg för AI-agenter.

Skapad för Länsstyrelsen i Västra Götaland, april 2026.
Baserat på samma FastMCP-mönster som scb-mcp-v2.
"""

import os
import logging
from typing import Optional
from urllib.parse import quote

import httpx
from fastmcp import FastMCP

# ----------------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kolada-mcp")

KOLADA_BASE = "https://api.kolada.se/v2"
HTTP_TIMEOUT = 30.0
USER_AGENT = "LstVG-Kolada-MCP/1.0 (samhällsanalys)"

# Västra Götalands 49 kommuner (källa: SCB, kommunkoder 2026)
# Dessa ID:n används både av SCB och Kolada
VG_MUNICIPALITIES = {
    "1401": "Härryda",
    "1402": "Partille",
    "1407": "Öckerö",
    "1415": "Stenungsund",
    "1419": "Tjörn",
    "1421": "Orust",
    "1427": "Sotenäs",
    "1430": "Munkedal",
    "1435": "Tanum",
    "1438": "Dals-Ed",
    "1439": "Färgelanda",
    "1440": "Ale",
    "1441": "Lerum",
    "1442": "Vårgårda",
    "1443": "Bollebygd",
    "1444": "Grästorp",
    "1445": "Essunga",
    "1446": "Karlsborg",
    "1447": "Gullspång",
    "1452": "Tranemo",
    "1460": "Bengtsfors",
    "1461": "Mellerud",
    "1462": "Lilla Edet",
    "1463": "Mark",
    "1465": "Svenljunga",
    "1466": "Herrljunga",
    "1470": "Vara",
    "1471": "Götene",
    "1472": "Tibro",
    "1473": "Töreboda",
    "1480": "Göteborg",
    "1481": "Mölndal",
    "1482": "Kungälv",
    "1484": "Lysekil",
    "1485": "Uddevalla",
    "1486": "Strömstad",
    "1487": "Vänersborg",
    "1488": "Trollhättan",
    "1489": "Alingsås",
    "1490": "Borås",
    "1491": "Ulricehamn",
    "1492": "Åmål",
    "1493": "Mariestad",
    "1494": "Lidköping",
    "1495": "Skara",
    "1496": "Skövde",
    "1497": "Hjo",
    "1498": "Tidaholm",
    "1499": "Falköping",
}

# Regionen Västra Götaland (landsting/region)
VG_REGION_ID = "14"

# ----------------------------------------------------------------------------
# MCP-server
# ----------------------------------------------------------------------------
mcp = FastMCP("kolada-mcp")

# Gemensam HTTP-klient
_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Lazy-init av gemensam HTTP-klient."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _http_client


async def kolada_get(path: str, params: Optional[dict] = None) -> dict:
    """
    Generisk GET mot Kolada-API:et.
    `path` ska börja med /v2/...
    Returnerar parsed JSON.
    """
    url = f"{KOLADA_BASE}{path}" if not path.startswith("http") else path
    client = await get_http_client()
    logger.info("GET %s params=%s", url, params)
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# ----------------------------------------------------------------------------
# Verktyg 1: Sök efter nyckeltal (KPI:er)
# ----------------------------------------------------------------------------
@mcp.tool()
async def kolada_search_kpi(query: str, max_results: int = 20) -> dict:
    """
    Sök efter nyckeltal (KPI) i Kolada på fritext i titel.

    Args:
        query: Söksträng på svenska, t.ex. "behörighet gymnasiet" eller
               "kostnad grundskola"
        max_results: Maximalt antal träffar att returnera (standard 20)

    Returnerar en lista med KPI:er där varje post innehåller:
      - id: KPI-kod (t.ex. "N15428")
      - title: titel på svenska
      - description: beskrivning
      - operating_area: verksamhetsområde
      - municipality_type: K (kommun), L (landsting/region) eller A (alla)
      - is_divided_by_gender: 1 om data finns uppdelat på kön

    Exempel på användning:
      kolada_search_kpi(query="behörighet gymnasiet")
    """
    encoded = quote(query)
    data = await kolada_get(f"/kpi?title={encoded}")
    values = data.get("values", [])[:max_results]

    return {
        "query": query,
        "total_found": data.get("count", len(values)),
        "returned": len(values),
        "kpis": [
            {
                "id": v.get("id"),
                "title": v.get("title"),
                "description": v.get("description"),
                "operating_area": v.get("operating_area"),
                "municipality_type": v.get("municipality_type"),
                "is_divided_by_gender": v.get("is_divided_by_gender"),
                "publication_date": v.get("publication_date"),
            }
            for v in values
        ],
    }


# ----------------------------------------------------------------------------
# Verktyg 2: Hämta metadata för specifikt KPI
# ----------------------------------------------------------------------------
@mcp.tool()
async def kolada_get_kpi_metadata(kpi_id: str) -> dict:
    """
    Hämta fullständig metadata för ett eller flera nyckeltal (KPI).

    Args:
        kpi_id: KPI-kod, t.ex. "N15428". Flera KPI:er kan anges
                kommaseparerat: "N15428,N11102"

    Returnerar beskrivning, definition, enhet, verksamhetsområde etc.
    Användbart innan man hämtar faktisk data för att förstå vad
    nyckeltalet mäter.
    """
    data = await kolada_get(f"/kpi/{kpi_id}")
    return {
        "kpi_ids": kpi_id,
        "count": data.get("count", 0),
        "metadata": data.get("values", []),
    }


# ----------------------------------------------------------------------------
# Verktyg 3: Hämta data
# ----------------------------------------------------------------------------
@mcp.tool()
async def kolada_get_data(
    kpi_id: str,
    municipality_id: str,
    year: Optional[str] = None,
) -> dict:
    """
    Hämta värden för ett eller flera KPI × kommun(er) × år.

    Args:
        kpi_id: KPI-kod(er), kommaseparerat. T.ex. "N15428" eller
                "N15428,N11102"
        municipality_id: Kommun-ID (SCB-kod), kommaseparerat.
                T.ex. "1493" (Mariestad) eller "1480,1493,1496"
                Regionen Västra Götaland har ID "14".
        year: Årtal, kommaseparerat. T.ex. "2024" eller "2020,2021,2022,2023,2024".
              Om None hämtas alla tillgängliga år.

    Returnerar data uppdelad per KPI × kommun × år × kön (T=Totalt, K=Kvinnor, M=Män).

    Obs: Minst två av tre dimensioner (kpi, municipality, year) måste anges
    för att Kolada ska svara med data.

    Exempel:
      # Behörighet till gymnasiet i Mariestad alla år
      kolada_get_data(kpi_id="N15428", municipality_id="1493")

      # Jämför tre kommuner för ett specifikt år
      kolada_get_data(kpi_id="N15428",
                      municipality_id="1480,1493,1496",
                      year="2024")
    """
    path = f"/data/kpi/{kpi_id}/municipality/{municipality_id}"
    if year:
        path += f"/year/{year}"

    data = await kolada_get(path)

    # Strukturera för läsbarhet
    rows = []
    for record in data.get("values", []):
        kpi = record.get("kpi")
        muni = record.get("municipality")
        period = record.get("period")
        for v in record.get("values", []):
            rows.append({
                "kpi": kpi,
                "municipality_id": muni,
                "municipality_name": VG_MUNICIPALITIES.get(muni, muni),
                "year": period,
                "gender": v.get("gender"),  # T/K/M
                "value": v.get("value"),
                "count": v.get("count"),
                "status": v.get("status"),
            })

    return {
        "kpi_id": kpi_id,
        "municipality_id": municipality_id,
        "year": year,
        "row_count": len(rows),
        "data": rows,
    }


# ----------------------------------------------------------------------------
# Verktyg 4: Lista VG-kommuner
# ----------------------------------------------------------------------------
@mcp.tool()
async def kolada_list_vg_municipalities() -> dict:
    """
    Lista Västra Götalands 49 kommuner med deras Kolada-ID
    (samma som SCB:s kommunkoder).

    Användbart för att slå upp rätt kommun-ID innan anrop till
    kolada_get_data. Region Västra Götaland själv har ID "14".
    """
    return {
        "region_id": VG_REGION_ID,
        "region_name": "Västra Götalands län (region)",
        "municipality_count": len(VG_MUNICIPALITIES),
        "municipalities": [
            {"id": mid, "name": name}
            for mid, name in sorted(VG_MUNICIPALITIES.items(), key=lambda x: x[1])
        ],
    }


# ----------------------------------------------------------------------------
# Verktyg 5: Jämför kommuner
# ----------------------------------------------------------------------------
@mcp.tool()
async def kolada_compare_municipalities(
    kpi_id: str,
    municipality_ids: str,
    year: Optional[str] = None,
) -> dict:
    """
    Hämta och strukturera jämförelse av ett KPI mellan flera kommuner.

    Till skillnad från kolada_get_data presenteras resultatet här som en
    jämförelsetabell — en rad per kommun — snarare än rådata.

    Args:
        kpi_id: Ett enskilt KPI (inte kommaseparerat). T.ex. "N15428"
        municipality_ids: Kommaseparerad lista, t.ex. "1480,1493,1496"
        year: Enskilt år eller None (senaste tillgängliga år per kommun)

    Returnerar en tabell med {kommun_id, kommun_namn, år, värde_totalt,
    värde_kvinnor, värde_män} för snabb visuell jämförelse.
    """
    path = f"/data/kpi/{kpi_id}/municipality/{municipality_ids}"
    if year:
        path += f"/year/{year}"
    data = await kolada_get(path)

    # Strukturera till en rad per kommun × år
    table: dict[tuple[str, str], dict] = {}
    for record in data.get("values", []):
        muni = record.get("municipality")
        period = record.get("period")
        key = (muni, period)
        row = table.setdefault(key, {
            "municipality_id": muni,
            "municipality_name": VG_MUNICIPALITIES.get(muni, muni),
            "year": period,
            "value_total": None,
            "value_women": None,
            "value_men": None,
        })
        for v in record.get("values", []):
            g = v.get("gender")
            val = v.get("value")
            if g == "T":
                row["value_total"] = val
            elif g == "K":
                row["value_women"] = val
            elif g == "M":
                row["value_men"] = val

    return {
        "kpi_id": kpi_id,
        "municipality_ids": municipality_ids,
        "year": year,
        "row_count": len(table),
        "comparison": sorted(
            table.values(),
            key=lambda r: (r["year"] or "", r["municipality_name"]),
        ),
    }


# ----------------------------------------------------------------------------
# Startpunkt
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info("Startar Kolada MCP-server på %s:%s", host, port)
    # HTTP Streamable transport (samma som scb-mcp-v2)
    mcp.run(transport="http", host=host, port=port)
