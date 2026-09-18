@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo Proje Analiz Asistani baslatiliyor...

rem Proje kok dizini = bu bat dosyasinin bulundugu klasor (surucu harfinden bagimsiz)
set "PROJECT_DIR=%~dp0"
set "PYEXE=%PROJECT_DIR%Python_Ortami\envs\ds_agent\python.exe"

echo Proje dizini: %PROJECT_DIR%
if not exist "%PYEXE%" (
    echo HATA: Python bulunamadi: %PYEXE%
    echo Yeni PC'de ilk kurulum icin env_create.bat dosyasini calistirin.
    pause
    exit /b 1
)

echo GUI baslatiliyor...
"%PYEXE%" "%PROJECT_DIR%gui_main.py"

if errorlevel 1 (
    echo.
    echo HATA: GUI baslatilamadi!
    pause
    exit /b 1
)

echo.
echo Program sonlandi.
pause
