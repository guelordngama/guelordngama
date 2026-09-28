@echo off
chcp 65001 >nul
setlocal
REM =====================================================================
REM  SafeCity - Mise a jour du poste operateur (installation par le code)
REM  A lancer par double-clic. Les reglages du poste (adresse du serveur,
REM  theme, son, notifications) sont conserves : ils sont dans Windows.
REM =====================================================================
set BRANCH=claude/safecity-alert-platform-yohh1v
cd /d "%~dp0\..\.."

echo.
echo [1/3] Recuperation de la derniere version...
where git >nul 2>nul
if errorlevel 1 (
    echo    Git n'est pas installe sur ce poste.
    echo    Telechargez le ZIP a jour depuis GitHub, branche %BRANCH%,
    echo    puis remplacez le dossier SafeCity par son contenu.
    goto :deps
)
if not exist ".git" (
    echo    Ce dossier n'est pas un clone Git : telechargez le ZIP a jour
    echo    depuis GitHub, branche %BRANCH%, et remplacez ce dossier.
    goto :deps
)
git fetch origin %BRANCH% || goto :fail
git checkout %BRANCH% || goto :fail
git pull --ff-only origin %BRANCH% || goto :fail

:deps
echo.
echo [2/3] Mise a jour des composants (PySide6, temps reel)...
py -3 -m pip install --upgrade -r desktop\requirements.txt || python -m pip install --upgrade -r desktop\requirements.txt || goto :fail

echo.
echo [3/3] Version installee :
type VERSION
echo.
echo Mise a jour terminee. Lancement du poste operateur...
where pyw >nul 2>nul && (start "" pyw -3 desktop\main.py) || (start "" pythonw desktop\main.py)
exit /b 0

:fail
echo.
echo *** La mise a jour a echoue. Verifiez la connexion Internet puis relancez. ***
pause
exit /b 1
