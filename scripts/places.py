"""
Canonical places: normaliza nomes de lugares vindos dos PDFs.

Os PDFs têm typos ("Aracrux"), abreviações ("Sta Cruz"), vias coladas em
destinos ("Aracruz Barra do Sahy") e variantes ("Domingo Martins" vs
"Domingos Martins"). Esse módulo resolve tudo isso para um conjunto fixo
de lugares canônicos.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


# Lista mestra de lugares canônicos (forma de exibição final).
# A ordem importa: mais longos primeiro pra prefixo greedy.
CANONICAL_PLACES = [
    # Cidades / municípios
    "Aracruz", "João Neiva", "Ibiraçu", "Domingos Martins", "Marechal Floriano",
    "Santa Maria de Jetibá", "São Mateus", "Boa Esperança", "Sobradinho",
    "São João do Sobrado",

    # Bairros e localidades (Aracruz)
    "Praia Formosa", "Santa Cruz", "Coqueiral", "Itaparica", "Mar Azul",
    "Sauê", "Irajá", "Barra do Sahy", "Barra do Riacho", "Vila do Riacho",
    "Pau Brasil", "Praia dos Padres", "Cachoeirinha do Riacho", "Biriricas",
    "Jacupemba", "Assentamento", "Desengano", "Guaraná", "Comboios",
    "Pólo Industrial", "Polo Industrial", "Portaria da Fábrica",

    # Bairros (Aracruz municipal)
    "Cohab IV", "Limão", "Por do Sol", "Cupido", "São Marcos", "Vista Linda",
    "Nova Conquista", "Itaputera", "Jardins", "Câmara", "Centro",
    "Bairro de Fátima", "Portelinha", "Clemente II", "SENAI", "Shopping",
    "Hospital", "Pedrinhas", "Recanto Feliz",

    # Domingos Martins
    "Araguaia", "Peróbas", "Santa Isabel", "Paraju",
]

# Forma normalizada (sem acento, lowercase) → forma canônica
_NORM_TO_CANON: dict[str, str] = {_norm(p): p for p in CANONICAL_PLACES}

# Aliases manuais (typos, abreviações, variantes)
ALIASES = {
    # typos do PDF da Cordial
    "aracrux": "Aracruz",
    "aracrz": "Aracruz",
    "aracruz x": "Aracruz",
    "araccruz": "Aracruz",
    "cohab ix": "Cohab IV",
    "cohab iv x": "Cohab IV",
    "cohab iv": "Cohab IV",
    "cohab": "Cohab IV",

    # abreviações comuns
    "sta cruz": "Santa Cruz",
    "sra cruz": "Santa Cruz",
    "s. pedro": "São Pedro",
    "s pedro": "São Pedro",
    "sao pedro": "São Pedro",
    "sao mateus": "São Mateus",
    "sao mateu": "São Mateus",
    "joao neiva": "João Neiva",
    "domingo martins": "Domingos Martins",
    "perobas": "Peróbas",
    "ibiracu": "Ibiraçu",
    "guarana": "Guaraná",
    "saue": "Sauê",
    "iraja": "Irajá",
    "polo industrial": "Pólo Industrial",
    "fabrica": "Fábrica",
    "fábrica": "Fábrica",
    "camara": "Câmara",
    "portaria da fabrica": "Portaria da Fábrica",

    # variantes "P/ Boa Esperança" no PDF do São Mateus
    "boa esperanca": "Boa Esperança",
    "sao joao do sobrado": "São João do Sobrado",
}

# Adiciona aliases ao mapa principal
_NORM_TO_CANON.update(ALIASES)

# Termos que indicam "via" (não são destinos por si só) — usados pra detectar
# quando um destino veio colado com a via
VIA_TERMS = {
    "direto", "shopping", "hospital", "centro", "barra", "fabrica", "fábrica",
    "guaraná", "guarana", "câmara", "camara", "sauê", "saue", "iraja", "irajá",
    "coqueiral", "santa cruz", "barra do sahy", "barra do riacho",
    "ibiraçu", "ibiracu", "monsenhor", "santa isabel", "paraju",
    "santa maria", "santa rita", "marechal", "marechal/santa maria",
    "marechal/santa", "san. luzia", "santa luzia", "sesc", "primo bitti",
    "córrego d'água", "corrego d'agua", "córrego d agua",
}

# Sufixos a remover dos extremos do nome
TRAILING_GARBAGE_RE = re.compile(
    r"\s+(?:Direto|Direto\.|via|VIA|Shopping|Hospital|Centro|Barra|São Pedro|"
    r"Fábrica|Fabrica|Guaraná|Guarana|Coqueiral|Ibiraçu|Ibiracu|"
    r"Santa Cruz|Itaparica|Barra do Sahy|Barra do Riacho|"
    r"Paraju/.*|Marechal/.*|Santa Maria.*|Recanto.*)$",
    re.IGNORECASE,
)



# Aliases extras pra casos colados/typados (descobertos em produção)
EXTRA_ALIASES = {
    "aracruz guarana": "Aracruz",
    "aracruz guaraná": "Aracruz",
    "aracruz x guarana": "Aracruz",
    "aracruz x guaraná": "Aracruz",
    "aracrux jacupemba": "Aracruz",
    "aracrux x jacupemba": "Aracruz",
    "aracruz coqueiral": "Aracruz",
    "aracruz coqueiral x": "Aracruz",
    "aracruz fabrica": "Aracruz",
    "aracruz x guarana": "Aracruz",
    "aracruz centro": "Aracruz",
    "aracruz x": "Aracruz",
    "ix cupido": "Cohab IV",   # Cohab IX (typo) → Cohab IV
    "cohab ix cupido": "Cohab IV",
    "sao marcos": "São Marcos",
    "sao mateus": "São Mateus",
    "boa esperanca": "Boa Esperança",
    "sao joao do sobrado": "São João do Sobrado",
    "santa maria de jetiba": "Santa Maria de Jetibá",
    "premier ifes": "Premier",
    "ciclos rodoviaria": "Centro",
    "centro shoping": "Centro",
    "barra do sahy direto": "Barra do Sahy",
    "saue coqueiral primo bitti": "Sauê",
    "barra do riacho": "Barra do Riacho",
    "vila do riacho": "Vila do Riacho",
    "comboios vila do riacho": "Vila do Riacho",
    "praia formosa shopping": "Praia Formosa",
    "sesc itaparica": "Itaparica",
    "santa cruz sesc": "Santa Cruz",
    "domingo martins": "Domingos Martins",
    "perobas": "Peróbas",
    "iraja": "Irajá",
    "saue": "Sauê",
    "ibiracu": "Ibiraçu",
    "guarana": "Guaraná",
    "iraja x aracruz": "Irajá",
    "centro x cohab iv": "Centro",
    "centro x clemente": "Centro",
    "cohab iv x sao marcos": "Cohab IV",
    "cohab iv x cupido": "Cohab IV",
    "polo industrial x cupido": "Pólo Industrial",
    "pólo industrial x cupido": "Pólo Industrial",
    "vista linda x cohab": "Vista Linda",
    "vista linda x cohab iv": "Vista Linda",
    "biriricas via mucurata": "Biriricas",
    "biriricas via mucuruta": "Biriricas",
}
ALIASES.update(EXTRA_ALIASES)
_NORM_TO_CANON.update(EXTRA_ALIASES)


def canonicalize(name: str) -> str:
    """Recebe um nome cru e devolve a forma canônica.

    Se não bater com nada conhecido, devolve o nome com `.strip()` e
    title-case razoável (não inventa nada).
    """
    if not name:
        return name
    s = re.sub(r"\s+", " ", name).strip(" -\t:")
    if not s:
        return s

    # remove pontuação à direita
    s = s.rstrip(" .,;-")

    # 1) match direto (norm full)
    n = _norm(s)
    if n in _NORM_TO_CANON:
        return _NORM_TO_CANON[n]

    # 2) prefixo greedy: tenta casar prefixo cada vez maior contra a lista
    tokens = s.split(" ")
    for k in range(len(tokens), 0, -1):
        prefix = " ".join(tokens[:k])
        n2 = _norm(prefix)
        if n2 in _NORM_TO_CANON:
            return _NORM_TO_CANON[n2]

    # 3) sufixo: a parte do meio/fim pode ser um lugar conhecido
    for k in range(1, len(tokens) + 1):
        suffix = " ".join(tokens[-k:])
        n2 = _norm(suffix)
        if n2 in _NORM_TO_CANON:
            return _NORM_TO_CANON[n2]

    # 4) fallback: title case decente
    return _title(s)


def split_place_and_via(raw: str) -> tuple[str, Optional[str]]:
    """Recebe `Aracruz Barra do Sahy` ou similar e devolve (destino, via).

    Estratégia:
      1) tenta prefixo greedy contra CANONICAL_PLACES → destino é o prefixo,
         o resto vira via;
      2) se a string toda casa com um canônico, via = None;
      3) se nada bater, devolve (canonicalize(raw), None).
    """
    if not raw:
        return raw, None
    s = re.sub(r"\s+", " ", raw).strip(" -")
    if not s:
        return s, None

    # match total
    n = _norm(s)
    if n in _NORM_TO_CANON:
        return _NORM_TO_CANON[n], None

    tokens = s.split(" ")
    # prefixo greedy: pega o MAIOR prefixo que casa com lugar canônico
    for k in range(min(len(tokens), 6), 0, -1):
        prefix = " ".join(tokens[:k])
        np = _norm(prefix)
        if np in _NORM_TO_CANON:
            dest = _NORM_TO_CANON[np]
            via = " ".join(tokens[k:]).strip(" +,/-")
            return dest, (via or None)

    # nada bateu como prefixo — tenta separar por "+" ou "/"
    if "+" in s or "/" in s:
        # destino = até o primeiro "+/", via = resto
        m = re.split(r"\s*[+/]\s*", s, maxsplit=1)
        if len(m) == 2:
            dest = canonicalize(m[0])
            return dest, m[1].strip() or None

    # fallback
    return canonicalize(s), None


def _title(s: str) -> str:
    minor = {"de", "da", "do", "das", "dos", "e", "x", "via", "ao"}
    parts = []
    for i, w in enumerate(s.split(" ")):
        wl = w.lower()
        if i > 0 and wl in minor:
            parts.append(wl)
        else:
            parts.append(w[:1].upper() + w[1:].lower() if w else w)
    return " ".join(parts)
