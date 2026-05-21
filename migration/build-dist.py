"""
build-dist.py — Gera site/ minificado para o repo público.

Lê os arquivos do diretório `site/` (versão lida-humano) e produz `dist/` com:
- index.html minificado (HTML + CSS inline + JS inline tudo comprimido)
- JS adicionalmente ofuscado com javascript-obfuscator (opcional via --obfuscate)
- demais arquivos (schedules.json, ícones, manifest, sitemap, etc.) copiados.

Requisitos:
  - Node.js 18+
  - As tools são baixadas via `npx` na primeira execução.

Uso:
  python migration/build-dist.py
  python migration/build-dist.py --src site --out dist --obfuscate

Pra rodar offline depois da 1ª vez, instale localmente:
  npm install html-minifier-terser javascript-obfuscator terser
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ASSET_FILES = [
    "icon-192.png", "icon-512.png", "favicon-32.png",
    "og-image.png", "og-image-v2.png",
    "manifest.webmanifest", "sitemap.xml", "robots.txt",
    "404.html", "googleae6d8b54ec09de5a.html",
    "data/schedules.json",
]


def copy_assets(src: Path, dst: Path):
    for name in ASSET_FILES:
        s = src / name
        if not s.exists():
            print(f"  [skip] {name}", file=sys.stderr)
            continue
        d = dst / name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        print(f"  [copy] {name}")


def minify_html(src_html: Path, dst_html: Path):
    """Usa html-minifier-terser pra minificar HTML+CSS+JS inline."""
    cmd = [
        "npx", "--yes", "html-minifier-terser@7",
        "--collapse-whitespace",
        "--remove-comments",
        "--minify-js", "true",
        "--minify-css", "true",
        "--remove-redundant-attributes",
        "--remove-empty-attributes",
        "--use-short-doctype",
        # Preserva JSON-LD e SVG indentados (não confundir com JS)
        "--ignore-custom-fragments", "/<script type=\"application\\/ld\\+json\">[^]*?<\\/script>/",
        str(src_html),
        "-o", str(dst_html),
    ]
    subprocess.check_call(cmd)


def obfuscate_inline_js(html_path: Path):
    """Pega cada <script> sem 'src' nem 'type=ld+json' e ofusca via javascript-obfuscator."""
    import re
    text = html_path.read_text(encoding="utf-8")
    pat = re.compile(r'(<script(?![^>]*\bsrc=)(?![^>]*type="application/ld\+json")[^>]*>)([^]*?)(</script>)',
                     re.IGNORECASE)
    matches = list(pat.finditer(text))
    if not matches:
        return
    print(f"  ofuscando {len(matches)} bloco(s) <script> inline…")
    # Gera um arquivo temp por bloco e roda javascript-obfuscator nele
    out_parts = []
    last = 0
    for m in matches:
        out_parts.append(text[last:m.start()])
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        if not body.strip():
            out_parts.append(m.group(0))
            last = m.end()
            continue
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False, encoding="utf-8") as tf:
            tf.write(body)
            tmp_in = tf.name
        tmp_out = tmp_in + ".obf.js"
        try:
            subprocess.check_call([
                "npx", "--yes", "javascript-obfuscator@4", tmp_in,
                "--output", tmp_out,
                "--compact", "true",
                "--control-flow-flattening", "false",  # mais leve, evita bugs
                "--identifier-names-generator", "mangled",
                "--string-array", "true",
                "--string-array-threshold", "0.75",
                "--simplify", "true",
                "--rename-globals", "false",
                "--target", "browser",
            ])
            obf_body = Path(tmp_out).read_text(encoding="utf-8")
        finally:
            try: Path(tmp_in).unlink()
            except FileNotFoundError: pass
            try: Path(tmp_out).unlink()
            except FileNotFoundError: pass
        out_parts.append(open_tag + obf_body + close_tag)
        last = m.end()
    out_parts.append(text[last:])
    html_path.write_text("".join(out_parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="site", help="dir fonte (default: site/)")
    ap.add_argument("--out", default="dist", help="dir destino (default: dist/)")
    ap.add_argument("--obfuscate", action="store_true",
                    help="aplica javascript-obfuscator após o minify")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    if not (src / "index.html").exists():
        print(f"ERRO: {src}/index.html não existe", file=sys.stderr)
        sys.exit(2)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    print(f"Copiando assets {src} -> {out}")
    copy_assets(src, out)

    print(f"Minificando index.html…")
    minify_html(src / "index.html", out / "index.html")
    size_before = (src / "index.html").stat().st_size
    size_after = (out / "index.html").stat().st_size
    print(f"  {size_before} -> {size_after} bytes ({size_after*100//size_before}%)")

    if args.obfuscate:
        print("Ofuscando JS inline (pode demorar 30-60s)…")
        obfuscate_inline_js(out / "index.html")
        size_obf = (out / "index.html").stat().st_size
        print(f"  após ofuscação: {size_obf} bytes")

    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
