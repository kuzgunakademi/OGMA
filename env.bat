@echo off
rem Proje kok dizini = bu bat dosyasinin bulundugu klasor (surucu harfinden bagimsiz)
set "PROJECT_DIR=%~dp0"
set "PATH=%PROJECT_DIR%Python_Ortami\Scripts;%PROJECT_DIR%Python_Ortami\condabin"
call "%PROJECT_DIR%Python_Ortami\Scripts\activate.bat" "%PROJECT_DIR%Python_Ortami\envs\ds_agent"

cmd
