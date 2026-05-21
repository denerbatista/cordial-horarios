"""
Sync local — Cordial Horários

Roda o build na sua máquina (que está liberada pelo servidor da Cordial),
commita o schedules.json novo e dá push pra atualizar o site.

Modos de uso:

  1) Modo CLI (uma vez):
       python scripts/sync_local.py
     Faz build + commit + push imediatamente.

  2) Modo servidor (fica ligado, escutando):
       python scripts/sync_local.py --server
     Sobe um HTTP local em 127.0.0.1:8765 com endpoint POST /sync.
     A rota oculta `#mode=sync` no site chama esse endpoint.

Flags:
  --dry-run     roda o build mas não commita nem dá push.
  --no-push     commita localmente mas não dá push.
  --server      sobe o HTTP local.
  --port N      porta alternativa pro servidor (default 8765).
  --branch X    branch onde commitar (default: branch atual, mas
                recomendado main).

Requisitos:
  - Python 3.11+
  - `pip install -r requirements.txt`
  - git autenticado nesta máquina (você já tem, já que commita do repo).

Segurança do modo servidor:
  - Bind em 127.0.0.1 só (não acessível pela rede).
  - Valida o header Host (mitiga DNS rebinding).
  - CORS apenas para os origins esperados (site oficial + dev local).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Import tardio dos módulos do projeto (precisa de pdfplumber, etc).
from build import build_from_web, write_sitemap  # noqa: E402

OUT_PATH = ROOT / "site" / "data" / "schedules.json"

ALLOWED_ORIGINS = {
    "https://denerbatista.github.io",
}


def _origin_allowed(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    # Qualquer porta de localhost/127.0.0.1 (uso em dev: file watcher, vite, etc).
    return origin.startswith("http://localhost:") or \
        origin.startswith("http://127.0.0.1:")


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, check=check,
                          capture_output=True, text=True)


def _git_branch() -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def do_sync(*, dry_run: bool = False, no_push: bool = False,
            branch: str | None = None) -> dict:
    """Build + commit + push. Retorna um dict com o resultado."""
    started = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] iniciando build...", flush=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = build_from_web(OUT_PATH)
    except Exception as e:
        return {"ok": False, "phase": "build", "error": f"{type(e).__name__}: {e}"}

    trips = payload.get("totalTrips", 0)
    print(f"   trips extraídos: {trips}", flush=True)
    if trips == 0:
        return {"ok": False, "phase": "build", "error": "totalTrips=0",
                "sectors": {k: v.get("trip_count", 0)
                            for k, v in payload.get("sectors", {}).items()}}

    # Escreve schedules.json e sitemap.xml
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    write_sitemap(payload, OUT_PATH.parent.parent)

    result = {
        "ok": True,
        "totalTrips": trips,
        "generatedAt": payload["generatedAt"],
        "duration_s": round(time.time() - started, 1),
    }

    if dry_run:
        result["dry_run"] = True
        return result

    # git: detecta branch alvo e dá pull antes pra evitar conflito
    current = _git_branch()
    target = branch or current
    if target != current:
        # checa working tree limpo antes de trocar branch
        st = _run(["git", "status", "--porcelain"], check=False)
        if st.stdout.strip():
            return {**result, "ok": False, "phase": "git",
                    "error": f"working tree não está limpo (branch atual={current})"}
        _run(["git", "checkout", target])
    try:
        _run(["git", "pull", "--rebase", "origin", target], check=False)
        _run(["git", "add", "site/data/schedules.json", "site/sitemap.xml"])
        diff = _run(["git", "diff", "--staged", "--quiet"], check=False)
        if diff.returncode == 0:
            result["changed"] = False
            return result
        ts = time.strftime("%Y-%m-%d %H:%M", time.gmtime()) + " UTC"
        _run(["git", "commit", "-m",
              f"data: atualizar horários ({ts}) [sync local]"])
        result["changed"] = True
        if not no_push:
            _run(["git", "push", "origin", target])
            result["pushed"] = True
        return result
    finally:
        if target != current:
            _run(["git", "checkout", current], check=False)


# ---------- servidor HTTP local ----------

def _make_handler(port: int):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            origin = self.headers.get("Origin", "")
            if _origin_allowed(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            return host in {f"localhost:{port}", f"127.0.0.1:{port}"}

        def _json(self, code: int, body: dict):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if not self._host_ok():
                self._json(403, {"ok": False, "error": "host_not_allowed"})
                return
            if self.path == "/health":
                self._json(200, {"ok": True,
                                 "service": "cordial-sync-local",
                                 "version": 1})
                return
            self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            if not self._host_ok():
                self._json(403, {"ok": False, "error": "host_not_allowed"})
                return
            if self.path != "/sync":
                self._json(404, {"ok": False, "error": "not_found"})
                return
            try:
                result = do_sync()
                self._json(200 if result.get("ok") else 500, result)
            except Exception as e:
                self._json(500, {"ok": False, "phase": "server",
                                 "error": f"{type(e).__name__}: {e}"})

        def log_message(self, fmt, *args):  # silencia logs verbosos do http.server
            sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {fmt % args}\n")

    return Handler


def serve(port: int):
    handler = _make_handler(port)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    print(f"sync local: escutando em http://127.0.0.1:{port}", flush=True)
    print(f"  GET  /health   -> ping", flush=True)
    print(f"  POST /sync     -> roda build + commit + push", flush=True)
    print(f"Pra parar: Ctrl+C", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nparando.", flush=True)
        httpd.server_close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", action="store_true",
                    help="sobe servidor HTTP local em 127.0.0.1:PORT")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dry-run", action="store_true",
                    help="não commita nem dá push")
    ap.add_argument("--no-push", action="store_true",
                    help="commita mas não dá push")
    ap.add_argument("--branch", default=None,
                    help="branch alvo (default: branch atual)")
    args = ap.parse_args()

    if args.server:
        serve(args.port)
        return 0

    result = do_sync(dry_run=args.dry_run, no_push=args.no_push,
                     branch=args.branch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
