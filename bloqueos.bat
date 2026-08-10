@echo off
rem ============================================================================
rem  Ciclo completo del control de bloqueos, de doble clic.
rem
rem    bloqueos.bat                     baja el stock, cruza, genera y sube
rem    bloqueos.bat sinstock            usa el stock ya bajado (mas rapido)
rem    bloqueos.bat sinsubir            no toca Postgres
rem    bloqueos.bat sinstock sinsubir   las dos cosas
rem    bloqueos.bat revisar             solo comprueba la configuracion
rem
rem  Las credenciales NO van aqui: se leen de .env, que esta en .gitignore.
rem  Copia .env.ejemplo a .env y completalo. Si prefieres tenerlas como
rem  variables de usuario de Windows, tambien sirve: .env solo las agrega.
rem ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
set "INICIO=%TIME%"

set "SINSTOCK="
set "SINSUBIR="
set "REVISAR="
:args
if "%~1"=="" goto :finargs
if /i "%~1"=="sinstock" set "SINSTOCK=1"
if /i "%~1"=="sinsubir" set "SINSUBIR=1"
if /i "%~1"=="revisar"  set "REVISAR=1"
shift
goto :args
:finargs

if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    if not "%%~A"=="" set "%%~A=%%~B"
  )
)

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo  No se encuentra python en el PATH.
  goto :fin
)

echo.
echo  ================================================================
echo   CONTROL DE BLOQUEOS - %DATE% %TIME:~0,5%
echo  ================================================================

if defined REVISAR (
  echo.
  echo  Revisando la configuracion, sin correr nada.
  echo.
  if defined SINSTOCK (echo   sinstock ............ activo, no bajaria el stock)
  if defined SINSUBIR (echo   sinsubir ............ activo, no subiria a Postgres)
  if exist ".env" (echo   .env ................ presente) else (echo   .env ................ no esta, se usan las variables de Windows)
  if "%FISHKEN_USER%%FISHKEN_USUARIO%"=="" (echo   Fishken ............. SIN credenciales, no se puede bajar stock) else (echo   Fishken ............. listo)
  if "%BLOQUEOS_DB_URL%"=="" (echo   Postgres ............ SIN cadena, no se puede subir) else (echo   Postgres ............ listo)
  python -c "import os,config,glob;print('  Carpeta de datos ....', config.BASE);print('  Laboratorio .........', 'listo' if os.path.isdir(config.DIR_LAB) else 'NO se llega a '+config.DIR_LAB);print('  Materia prima .......', 'listo' if os.path.isdir(config.DIR_MP) else 'NO se llega a '+config.DIR_MP);print('  Archivos de stock ...', len([x for x in glob.glob(config.ruta('FRIG*.xlsx'))]));print('  LAB-REG-08 ..........', len(glob.glob(config.ruta(config.GLOB_LAB))));print('  PRO-REG-46 ..........', len(glob.glob(config.ruta(config.GLOB_MP))))"
  python -c "import psycopg" 2>nul && (echo   Driver de Postgres .. listo) || (echo   Driver de Postgres .. FALTA: python -m pip install "psycopg[binary]")
  goto :fin
)

rem ---- 1. stock desde Fishken
if defined SINSTOCK (
  echo.
  echo  [1/3] Stock: se usa el que ya esta bajado.
  goto :cruce
)
if "%FISHKEN_USER%%FISHKEN_USUARIO%"=="" (
  echo.
  echo  [1/3] Stock: sin FISHKEN_USER ni FISHKEN_PWD, se usa el ya bajado.
  echo        Un stock viejo no es un stock liberado: revisa la fecha en la pagina.
  goto :cruce
)
echo.
echo  [1/3] Bajando el stock de las tres bodegas...
python descargar_fishken.py
if errorlevel 1 (
  echo.
  echo  La descarga fallo. Se sigue con el stock anterior, que puede estar viejo.
)

:cruce
rem ---- 2. sincroniza laboratorio y materia prima, cruza y genera la pagina
echo.
echo  [2/3] Cruzando y generando la pagina, toma unos minutos...
python -u actualizar.py
if errorlevel 1 (
  echo.
  echo  El cruce fallo. NO se sube nada a Postgres.
  goto :fin
)

rem ---- 3. carga a Postgres
if defined SINSUBIR (
  echo.
  echo  [3/3] Carga a Postgres omitida.
  goto :fin
)
if "%BLOQUEOS_DB_URL%"=="" (
  echo.
  echo  [3/3] Sin BLOQUEOS_DB_URL: no se sube a Postgres.
  echo        El Excel y la pagina local quedaron al dia igual.
  goto :fin
)
echo.
echo  [3/3] Subiendo a Postgres...
python -u cargar_supabase.py
if errorlevel 1 (
  echo.
  echo  La carga fallo. El Excel y la pagina local quedaron al dia igual.
  echo  Si dice que los criterios no coinciden, falta aplicar la migracion
  echo  de criterio_version en el SQL Editor. Ver supabase/migrations/.
)

:fin
echo.
echo  Empezo %INICIO:~0,8%  -  termino %TIME:~0,8%
echo.
pause
endlocal
