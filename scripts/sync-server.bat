@echo off
REM Sync local — sobe o servidor HTTP em 127.0.0.1:8765 e fica esperando
REM o site chamar /sync. Pra autostart no Windows: adicione um atalho deste
REM arquivo em "shell:startup" (Win+R, digite "shell:startup", arraste o atalho).

cd /d "%~dp0\.."
python -m pip install --quiet -r requirements.txt
python scripts\sync_local.py --server %*
