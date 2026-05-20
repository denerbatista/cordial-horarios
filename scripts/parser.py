"""
Cordial Turismo - parser de horários

Lê texto extraído de PDF (via pdfplumber.extract_text) e devolve lista de
viagens estruturadas. Suporta 3 formatos:

  - Aracruz: linhas tipo `001 05:30 Aracruz X Praia Formosa Coqueiral`
  - Domingos Martins: linhas tipo `06:40 Domingos Martins X Marechal Floriano Direto`
  - São Mateus: linhas tipo `05:00 P/ Boa Esperança (Segunda a Sexta)` (origem implícita)

A função pública é parse_sector(text, sector) -> list[Trip].
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

DAYS_ALL = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "holiday"]
DAYS_WEEK = ["mon", "tue", "wed", "thu", "fri"]


@dataclass
class Trip:
    sector: str
    line: str | None
    origin: str
    destination: str
    time: str
    days: list[str]
    via: str | None = None
    school_only: bool = False
    note: str | None = None
    raw_section: str | None = None
    raw_line: str | None = None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _title(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    minor = {"de", "da", "do", "das", "dos", "e", "x", "via", "ao"}
    out = []
    for i, w in enumerate(s.split(" ")):
        wl = w.lower()
        if i > 0 and wl in minor:
            out.append(wl)
        else:
            out.append(w[:1].upper() + w[1:].lower() if w else w)
    return " ".join(out)


def _fix_time(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h):02d}:{m}"


def _days_from_header(header: str) -> list[str]:
    parts = re.split(r"\s+-\s+", header)
    tail = parts[-1] if parts else header
    h = _norm(tail)
    if "domingo" in h and "feriado" in h:
        return ["sun", "holiday"]
    if "sabado" in h and "domingo" not in h:
        return ["sat"]
    if "domingo" in h and "sabado" not in h:
        return ["sun", "holiday"]
    if "segunda" in h and "sexta" in h:
        return list(DAYS_WEEK)
    if "dias uteis" in h or "dia letivo" in h:
        return list(DAYS_WEEK)
    if "terca" in h:
        return ["tue"]
    return []


def _days_from_parens(note: str) -> tuple[list[str], str]:
    n = _norm(note or "")
    if not n:
        return list(DAYS_WEEK), note
    if "domingo" in n and "feriado" in n:
        return ["sun", "holiday"], note.strip()
    if "segunda a sexta" in n:
        return list(DAYS_WEEK), note.strip()
    if "segunda a sabado" in n:
        return list(DAYS_WEEK) + ["sat"], note.strip()
    if "segunda a domingo" in n:
        return list(DAYS_ALL), note.strip()
    if "sabado" in n and "domingo" not in n:
        days = []
        if "segunda" in n: days.append("mon")
        if "terca" in n: days.append("tue")
        if "quarta" in n: days.append("wed")
        if "quinta" in n: days.append("thu")
        if "sexta" in n: days.append("fri")
        days.append("sat")
        return sorted(set(days), key=DAYS_ALL.index), note.strip()
    days = []
    if "segunda" in n: days.append("mon")
    if "terca" in n: days.append("tue")
    if "quarta" in n: days.append("wed")
    if "quinta" in n: days.append("thu")
    if "sexta" in n: days.append("fri")
    if days:
        return sorted(set(days), key=DAYS_ALL.index), note.strip()
    return list(DAYS_WEEK), note.strip()


RE_LINE_NUMBERED = re.compile(
    r"^\s*(\d{3})\s+(\d{1,2}:\d{2})\s*(\*)?\s+(\S.+?)\s+[Xx]\s+(\S.*)$"
)
RE_LINE_PLAIN = re.compile(
    r"^\s*(\d{1,2}:\d{2})\s*(\*)?\s+(\S.+?)\s+[Xx]\s+(\S.*)$"
)
RE_LINE_SM = re.compile(
    r"^\s*((?:\d{1,2}:\d{2}(?:\s*/\s*\d{1,2}:\d{2})*))\s*(?:[A-ZÁÊÔÍÓÚÂ ]+\s+)?P/\s*(.+?)\s*(?:\(([^)]+)\))?\s*$"
)
RE_SECTION_DAY = re.compile(
    r"(SEGUNDA\s+(?:A|X)\s+SEXTA(?:\s+FEIRA)?|SEGUNDA\s+A\s+S[ÁA]BADO|DOMINGO[S]?\s+E\s+FERIADO[S]?|S[ÁA]BADO|TER[ÇC]AS?\s+FEIRA|DIAS\s+[ÚU]TEIS|DOMINGO\s+E\s+FERIADO)",
    re.IGNORECASE,
)


KNOWN_PLACES = {
    "praia formosa", "santa cruz", "santa cruz - sesc", "santa cruz x aracruz",
    "mar azul", "saue", "sauê", "iraja", "irajá", "coqueiral", "itaparica",
    "sesc - itaparica", "barra do sahy", "barra do riacho", "vila do riacho",
    "pau brasil", "biriricas", "praia dos padres", "jacupemba", "assentamento",
    "desengano", "cohab iv", "cohab", "limao", "limão", "por do sol", "cupido",
    "sao marcos", "são marcos", "vista linda", "shopping", "pólo industrial",
    "polo industrial", "senai", "itaputera", "nova conquista", "centro",
    "marechal floriano", "domingos martins", "araguaia", "perobas", "peróbas",
    "santa isabel", "boa esperanca", "boa esperança", "sobradinho",
    "sao joao do sobrado", "são joão do sobrado", "sao mateus", "são mateus",
    "joao neiva", "joão neiva", "cachoeirinha do riacho", "guarana", "guaraná",
    "clemente ii",
}


def _split_dest_via(rest: str) -> tuple[str, str | None]:
    rest = (rest or "").strip()
    if not rest:
        return rest, None
    tokens = rest.split(" ")
    for n in (5, 4, 3, 2, 1):
        if n > len(tokens):
            continue
        dest_candidate = " ".join(tokens[:n])
        if _norm(dest_candidate) in KNOWN_PLACES:
            via = " ".join(tokens[n:]).strip() or None
            return dest_candidate, via
    if "+" in rest or "/" in rest:
        for i, tk in enumerate(tokens):
            if "+" in tk or "/" in tk:
                if i >= 1:
                    dest = " ".join(tokens[:i]).strip()
                    via = " ".join(tokens[i:]).strip()
                    return dest, via
    m = re.match(r"^(.*?)\s+via\s+(.+)$", rest, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    if len(tokens) > 2:
        last = tokens[-1].lower()
        if last in {"direto", "shopping", "hospital", "centro", "barra",
                    "ibiraçu", "ibiracu", "guaraná", "guarana", "câmara",
                    "camara", "sauê", "saue", "iraja", "irajá", "fábrica",
                    "fabrica", "coqueiral"}:
            return " ".join(tokens[:-1]).strip(), tokens[-1].strip()
    return rest, None


def _parse_data_line(line: str) -> dict | None:
    line = line.rstrip()
    m = RE_LINE_NUMBERED.match(line)
    if m:
        line_num = m.group(1)
        time = _fix_time(m.group(2))
        star = bool(m.group(3))
        origin = m.group(4)
        rest = m.group(5)
        dest, via = _split_dest_via(rest)
        return {
            "line": line_num, "time": time, "star": star,
            "origin": _title(origin), "destination": _title(dest),
            "via": _title(via) if via else None, "raw": line,
        }
    m = RE_LINE_PLAIN.match(line)
    if m:
        time = _fix_time(m.group(1))
        star = bool(m.group(2))
        origin = m.group(3)
        rest = m.group(4)
        dest, via = _split_dest_via(rest)
        return {
            "line": None, "time": time, "star": star,
            "origin": _title(origin), "destination": _title(dest),
            "via": _title(via) if via else None, "raw": line,
        }
    return None


def _extract_section_headers(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    out = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if _parse_data_line(s):
            continue
        sm = RE_SECTION_DAY.search(s)
        if not sm:
            continue
        days = _days_from_header(s)
        if not days:
            continue
        before = s[:sm.start()].strip(" -")
        if not before:
            continue
        bnorm = _norm(before)
        if " x " not in bnorm and " de " not in bnorm and "saida" not in bnorm:
            continue
        out.append((i, s, days))
    return out


def _split_into_blocks(lines: list[str]) -> list[list[int]]:
    blocks: list[list[int]] = []
    current: list[int] = []
    for i, ln in enumerate(lines):
        if _parse_data_line(ln):
            current.append(i)
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def _parse_xy_format(text: str, sector: str) -> list[Trip]:
    lines = text.splitlines()
    blocks = _split_into_blocks(lines)
    section_headers = _extract_section_headers(lines)

    trips: list[Trip] = []
    used_headers: set[int] = set()

    block_routes = []
    for blk in blocks:
        routes: dict[tuple[str, str], int] = {}
        for idx in blk:
            p = _parse_data_line(lines[idx])
            if not p:
                continue
            key = (_norm(p["origin"]), _norm(p["destination"]))
            routes[key] = routes.get(key, 0) + 1
        if routes:
            top = max(routes.items(), key=lambda kv: kv[1])
            block_routes.append(top[0])
        else:
            block_routes.append(("", ""))

    for bi, blk in enumerate(blocks):
        block_first = blk[0]
        block_last = blk[-1]
        route = block_routes[bi]

        best_header = None
        best_dist = 10**9
        for hi, (line_idx, htext, hdays) in enumerate(section_headers):
            if hi in used_headers:
                continue
            mh = re.split(r"\s*-\s*", htext, maxsplit=1)
            if not mh:
                continue
            route_part = _norm(mh[0])
            if not route[0] or not route[1]:
                continue
            pos_o = route_part.find(route[0])
            pos_d = route_part.find(route[1])
            if pos_o < 0 or pos_d < 0 or pos_o >= pos_d:
                continue
            dist = min(abs(line_idx - block_first), abs(line_idx - block_last))
            if dist < best_dist:
                best_dist = dist
                best_header = (hi, line_idx, htext, hdays)

        if best_header:
            used_headers.add(best_header[0])
            section_label = best_header[2]
            section_days = best_header[3]
        else:
            section_label = None
            section_days = list(DAYS_WEEK)

        for idx in blk:
            ln = lines[idx]
            p = _parse_data_line(ln)
            if not p:
                continue
            trips.append(Trip(
                sector=sector,
                line=p["line"],
                origin=p["origin"],
                destination=p["destination"],
                time=p["time"],
                days=section_days,
                via=p["via"],
                school_only=p["star"],
                raw_section=section_label,
                raw_line=p["raw"],
            ))
    return trips


def parse_sao_mateus(text: str) -> list[Trip]:
    trips: list[Trip] = []
    current_origin: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        up = line.upper()
        m = re.match(r"S[ÁA][IÍ]DA\s+DE\s+(.+?)(?:\s*-.*)?$", line, re.IGNORECASE)
        if m:
            current_origin = _title(m.group(1))
            continue
        if up.startswith(("HORÁRIO DE", "HORARIO DE", "HORÁRIOS", "HORARIOS",
                          "HORAIO", "HORIÁIOS", "HORIAIOS", "VÁLIDO",
                          "WWW.", "HTTP", "CORDIAL", "EMAIL",
                          "CONTATO", "WHATSAPP", "CLIQUE")):
            continue
        m = RE_LINE_SM.match(line)
        if not m:
            continue
        times_raw = m.group(1)
        dest = m.group(2).strip()
        days_note = m.group(3)
        if not current_origin:
            current_origin = "São Mateus"
        days, note = _days_from_parens(days_note or "")
        for t in re.split(r"\s*/\s*", times_raw):
            trips.append(Trip(
                sector="sao_mateus",
                line=None,
                origin=current_origin,
                destination=_title(dest),
                time=_fix_time(t.strip()),
                days=days,
                via=None,
                school_only=False,
                note=note or None,
                raw_line=line,
            ))
    return trips


def parse_sector(text: str, sector: str) -> list[Trip]:
    if sector in ("aracruz", "domingos_martins"):
        return _parse_xy_format(text, sector)
    if sector == "sao_mateus":
        return parse_sao_mateus(text)
    raise ValueError(f"Setor desconhecido: {sector}")


def trips_to_dict(trips: list[Trip]) -> list[dict]:
    out = []
    for t in trips:
        d = asdict(t)
        d["days"] = sorted(d["days"], key=DAYS_ALL.index)
        out.append(d)
    return out


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("sector", choices=["aracruz", "sao_mateus", "domingos_martins"])
    ap.add_argument("input")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    text = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    trips = parse_sector(text, args.sector)
    if args.summary:
        print(f"Total: {len(trips)} viagens")
        routes = {}
        for t in trips:
            routes.setdefault((t.origin, t.destination), 0)
            routes[(t.origin, t.destination)] += 1
        for (o, d), n in sorted(routes.items()):
            print(f"  {o:30s} -> {d:30s}  {n}")
    else:
        print(json.dumps(trips_to_dict(trips), ensure_ascii=False, indent=2))
