"""
Cordial Turismo - extractor de PDFs

Pipeline: URL do PDF -> bytes -> texto (pdfplumber) -> parser.parse_sector

Uso:
  python extractor.py aracruz <url-do-pdf>
  python extractor.py --all (descobre URLs no site e processa os 3 setores)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import pdfplumber  # type: ignore
except ImportError:
    pdfplumber = None  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from parser import parse_sector, trips_to_dict  # noqa: E402

HORARIOS_PAGE = "http://www.cordialturismo.com.br/portal/horarios_geral/"

UA = (
    "Mozilla/5.0 (Linux; cordial-horarios bot; +https://github.com/) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)


def http_get(url: str, *, binary: bool = False) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", errors="replace")


def _url_ok(url: str) -> bool:
    """Faz HEAD/GET leve pra checar se o URL existe."""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return 200 <= r.status < 400
    except Exception:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                return 200 <= r.status < 400
        except Exception:
            return False


def _classify(label: str) -> str | None:
    low = label.lower()
    if "aracruz" in low:
        return "aracruz"
    if "são mateus" in low or "sao mateus" in low:
        return "sao_mateus"
    if "domingos martins" in low or low.startswith("setor dom"):
        return "domingos_martins"
    return None


def discover_pdf_urls() -> dict[str, str]:
    """Lê a página principal e devolve um URL canônico por setor.

    Pode haver mais de um link pro mesmo PDF (um no menu, outro no body).
    Coletamos todos os candidatos, priorizamos URLs com `/downloads/temp/`
    (que é o caminho oficial), e finalmente validamos com HEAD pra escolher
    o que retorna 200.
    """
    html = http_get(HORARIOS_PAGE)
    candidates: dict[str, list[str]] = {"aracruz": [], "sao_mateus": [],
                                        "domingos_martins": []}
    for m in re.finditer(r'href="([^"]+\.pdf)"[^>]*>(.*?)</a>',
                         html, re.IGNORECASE | re.DOTALL):
        href = m.group(1)
        # remove tags HTML internas (ex.: <i>) e normaliza espaços
        label = re.sub(r'<[^>]+>', ' ', m.group(2))
        label = re.sub(r'\s+', ' ', label).strip()
        sec = _classify(label)
        if not sec:
            continue
        if href not in candidates[sec]:
            candidates[sec].append(href)

    def score(url: str) -> int:
        s = 0
        if "/downloads/temp/" in url:
            s += 10
        if "horario" in url.lower() or "horarios" in url.lower():
            s += 2
        return s

    out: dict[str, str] = {}
    for sec, urls in candidates.items():
        urls = sorted(urls, key=score, reverse=True)
        chosen = None
        for u in urls:
            if _url_ok(u):
                chosen = u
                break
        if chosen is None and urls:
            chosen = urls[0]  # último recurso: tenta mesmo assim
        if chosen:
            out[sec] = chosen
    return out


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    if pdfplumber is None:
        raise RuntimeError(
            "pdfplumber não instalado. Rode: pip install pdfplumber"
        )
    out: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                })
            except Exception:
                tables = []
            if tables:
                for tbl in tables:
                    for row in tbl:
                        cells = [(c or "").strip() for c in row]
                        joined = " ".join(c for c in cells if c)
                        if joined:
                            out.append(joined)
            else:
                text = page.extract_text() or ""
                out.append(text)
            out.append("")
    return "\n".join(out)


def build_sector(sector: str, url: str) -> dict:
    pdf = http_get(url, binary=True)
    assert isinstance(pdf, (bytes, bytearray))
    text = extract_text_from_pdf_bytes(pdf)
    trips = parse_sector(text, sector)
    return {
        "sector": sector,
        "source_url": url,
        "trips": trips_to_dict(trips),
        "text_len": len(text),
        "trip_count": len(trips),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", nargs="?",
                    choices=["aracruz", "sao_mateus", "domingos_martins"])
    ap.add_argument("url", nargs="?", help="URL do PDF (override)")
    ap.add_argument("--all", action="store_true",
                    help="processa os 3 setores descobrindo URLs no site")
    ap.add_argument("--out", default=None, help="salva JSON em arquivo")
    args = ap.parse_args()

    if args.all:
        urls = discover_pdf_urls()
        if not urls:
            print("Não encontrei URLs de PDF no site", file=sys.stderr)
            sys.exit(2)
        print("URLs descobertos:", json.dumps(urls, ensure_ascii=False, indent=2),
              file=sys.stderr)
        sectors = []
        for sec, url in urls.items():
            print(f"-> processando {sec}: {url}", file=sys.stderr)
            sectors.append(build_sector(sec, url))
        payload = {"sectors": sectors, "sources": urls}
    else:
        if not args.sector:
            ap.error("informe um setor ou use --all")
        url = args.url
        if not url:
            urls = discover_pdf_urls()
            url = urls.get(args.sector)
            if not url:
                ap.error(f"URL não descoberto pro setor {args.sector}")
        payload = build_sector(args.sector, url)

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"OK -> {args.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
