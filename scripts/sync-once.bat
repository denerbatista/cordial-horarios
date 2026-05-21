@echo off
REM Sync local — roda 1 vez agora (build + commit + push).
REM Duplo-clique nesse arquivo OU rode no terminal: scripts\sync-once.bat
REM Requer Python 3.11+ no PATH e o repo clonado nesta máquina.

cd /d "%~dp0\.."
python -m pip install --quiet -r requirements.txt
python scripts\sync_local.py %*
set EC=%ERRORLEVEL%
echo.
echo (codigo de saida: %EC%)
pause
exit /b %EC%
