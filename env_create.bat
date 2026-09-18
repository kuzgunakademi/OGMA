@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ============================================================
echo  Proje Analiz Asistani - Temiz Ortam Kurulumu (yeni PC)
echo ============================================================
echo.
echo Bu betik, proje klasoru farkli bir yola/surucuye tasindiginda
echo veya Python ortami bozuldugunda ortami sifirdan kurar.
echo Gereken: Miniconda kurulu olmali (proje kokundeki
echo Miniconda_Kurulum.exe ile kurulabilir) + internet baglantisi.
echo.

set "PROJECT_DIR=%~dp0"
set "ENV_PATH=%PROJECT_DIR%Python_Ortami\envs\ds_agent"

where conda >nul 2>nul
if errorlevel 1 (
    echo HATA: 'conda' bulunamadi!
    echo Once Miniconda'yu kurun (Miniconda_Kurulum.exe), sonra tekrar deneyin.
    pause
    exit /b 1
)

echo [1/3] Conda ortami olusturuluyor: %ENV_PATH%
call conda create -y -p "%ENV_PATH%" python=3.11
if errorlevel 1 (
    echo HATA: Ortam olusturulamadi!
    pause
    exit /b 1
)

echo [2/3] pip paketleri kuruluyor (requirements.txt)...
call conda run -p "%ENV_PATH%" python -m pip install -r "%PROJECT_DIR%requirements.txt"
if errorlevel 1 (
    echo HATA: pip paketleri kurulamadi!
    pause
    exit /b 1
)

echo [3/3] Kurulum dogrulaniyor...
call conda run -p "%ENV_PATH%" python -c "import llama_cpp; print('llama-cpp-python:', llama_cpp.__version__)"

echo.
echo Kurulum tamamlandi. run_gui.bat ile baslatabilirsiniz.
echo NOT: GPU destegi libs/llama-server-cuda ile gomulu gelir, ek kurulum gerekmez.
pause
