@echo off
chcp 65001 >nul
setlocal
REM =====================================================================
REM  SafeCity - Construction de l'executable Windows du poste operateur
REM  Resultat : dist\SafeCityOperateur\SafeCityOperateur.exe
REM             + SafeCityOperateur-<version>.zip a copier sur les postes.
REM  A lancer sur UN poste Windows avec Python 3.10+ (une seule fois par
REM  version), puis distribuer le ZIP.
REM =====================================================================
cd /d "%~dp0\..\.."
set /p VER=<VERSION

echo [1/3] Installation des outils...
py -3 -m pip install --upgrade -r desktop\requirements.txt pyinstaller || goto :fail

echo [2/3] Construction de l'executable (quelques minutes)...
REM --paths : modules du poste (pages, widgets, theme...) ; map.html et
REM vendor\ (Leaflet) copies a cote des modules, la ou la carte les cherche.
py -3 -m PyInstaller --noconfirm --clean --windowed --name SafeCityOperateur ^
  --paths desktop ^
  --add-data "desktop\map.html;." ^
  --add-data "desktop\vendor;vendor" ^
  desktop\main.py || goto :fail

echo [3/3] Creation de l'archive a distribuer...
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\SafeCityOperateur' -DestinationPath 'SafeCityOperateur-%VER%.zip'" || goto :fail

echo.
echo Termine : SafeCityOperateur-%VER%.zip
echo Sur chaque poste : fermer SafeCity, remplacer le dossier SafeCityOperateur
echo par celui du ZIP, puis relancer SafeCityOperateur.exe.
pause
exit /b 0

:fail
echo *** Echec de la construction. ***
pause
exit /b 1
