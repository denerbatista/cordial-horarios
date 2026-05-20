"""
Cordial Turismo - build do schedules.json

Gera o arquivo único `site/data/schedules.json` consumido pelo site estático.
Roda na GitHub Action diariamente.

Modo padrão: descobre URLs no site, baixa PDFs, extrai e parsea.
Modo --from-fixtures: usa fixtures de texto (sem rede) — útil em dev.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parser import parse_sector, trips_to_dict  # noqa: E402

SECTORS = ["aracruz", "sao_mateus", "domingos_martins"]
SECTOR_LABELS = {
    "aracruz": "Setor Aracruz",
    "sao_mateus": "Setor São Mateus",
    "domingos_martins": "Setor Domingos Martins",
}
FIXTURE_NAMES = {
    "aracruz": "aracruz.txt",
    "sao_mateus": "sao_mateus.txt",
    "domingos_martins": "dom_martins.txt",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def build_from_fixtures(out_path: Path) -> dict:
    fixtures_dir = ROOT / "fixtures"
    sectors_out = {}
    all_trips = []
    for sec in SECTORS:
        fix = fixtures_dir / FIXTURE_NAMES[sec]
        if not fix.exists():
            print(f"[!] sem fixture pra {sec}: {fix}", file=sys.stderr)
            sectors_out[sec] = {
                "label": SECTOR_LABELS[sec],
                "source_url": None,
                "trip_count": 0,
                "text_hash": None,
                "trips": [],
            }
            continue
        text = fix.read_text(encoding="utf-8")
        trips = parse_sector(text, sec)
        trips_d = trips_to_dict(trips)
        for t in trips_d:
            t["sector_label"] = SECTOR_LABELS[sec]
        all_trips.extend(trips_d)
        sectors_out[sec] = {
            "label": SECTOR_LABELS[sec],
            "source_url": None,
            "trip_count": len(trips_d),
            "text_hash": _hash(text),
            "trips": trips_d,
        }
    return _assemble(sectors_out, all_trips, source="fixtures")


def build_from_web(out_path: Path) -> dict:
    from extractor import discover_pdf_urls, build_sector  # type: ignore
    sectors_out = {}
    all_trips = []
    urls = discover_pdf_urls()
    print(f"URLs descobertos: {urls}", file=sys.stderr)
    for sec in SECTORS:
        url = urls.get(sec)
        if not url:
            print(f"[!] URL não encontrado pra {sec}", file=sys.stderr)
            sectors_out[sec] = {
                "label": SECTOR_LABELS[sec],
                "source_url": None,
                "trip_count": 0,
                "text_hash": None,
                "trips": [],
            }
            continue
        result = build_sector(sec, url)
        for t in result["trips"]:
            t["sector_label"] = SECTOR_LABELS[sec]
        all_trips.extend(result["trips"])
        sectors_out[sec] = {
            "label": SECTOR_LABELS[sec],
            "source_url": url,
            "trip_count": result["trip_count"],
            "text_hash": _hash(str(result["text_len"])),
            "trips": result["trips"],
        }
    return _assemble(sectors_out, all_trips, source="web", urls=urls)


def _assemble(sectors_out: dict, all_trips: list[dict], *, source: str,
              urls: dict | None = None) -> dict:
    for i, t in enumerate(all_trips):
        t["id"] = f"{t['sector'][:2]}-{i:05d}"
    places = set()
    for t in all_trips:
        places.add(t["origin"])
        places.add(t["destination"])
    return {
        "schemaVersion": 1,
        "generatedAt": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source": source,
        "sectors": sectors_out,
        "totalTrips": len(all_trips),
        "places": sorted(places, key=lambda s: s.lower()),
        "trips": all_trips,
        "sourceUrls": urls or {},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-fixtures", action="store_true",
                    help="usa fixtures locais em vez de baixar PDFs")
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "schedules.json"))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.from_fixtures:
        payload = build_from_fixtures(out_path)
    else:
        payload = build_from_web(out_path)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding="utf-8")
    print(f"OK -> {out_path}")
    print(f"   sectors: {len(payload['sectors'])}")
    print(f"   trips:   {payload['totalTrips']}")
    print(f"   places:  {len(payload['places'])}")


if __name__ == "__main__":
    main()
