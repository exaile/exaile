@echo off
REM 
REM Win32 launch script for Exaile
REM

setlocal

set EXAILE_CONSOLE=N

if "%1" == "--console" set EXAILE_CONSOLE=Y
if "%1" == "--console" shift

REM If certain arguments are passed, we must start in a console or the user
REM will be a bit confused... 

for %%I in (%*) DO (
    if "%%I" == "--help" set EXAILE_CONSOLE=Y
    if "%%I" == "--debug" set EXAILE_CONSOLE=Y
    if "%%I" == "--version" set EXAILE_CONSOLE=Y

    if "%%I" == "--help-gst" set EXAILE_CONSOLE=Y
    if "%%I" == "--gst-version" set EXAILE_CONSOLE=Y
    if "%%I" == "--gst-debug-help" set EXAILE_CONSOLE=Y

    if "%%I" == "--get-title" set EXAILE_CONSOLE=Y
    if "%%I" == "--get-album" set EXAILE_CONSOLE=Y
    if "%%I" == "--get-artist" set EXAILE_CONSOLE=Y
    if "%%I" == "--get-length" set EXAILE_CONSOLE=Y
    if "%%I" == "--get-rating" set EXAILE_CONSOLE=Y
)

set PYTHON_SUFFIX=w.exe
if "%EXAILE_CONSOLE%" == "Y" set PYTHON_SUFFIX=.exe

REM Detect py[w].exe in the path
for %%X in (py%PYTHON_SUFFIX%) do (set PYTHON_BIN=%%~$PATH:X)
if not "%PYTHON_BIN%" == "" goto python_found

set PYTHON_EXE=python%PYTHON_SUFFIX%

REM Detect python[w].exe in the path
for %%X in (%PYTHON_EXE%) do (set PYTHON_BIN=%%~$PATH:X)
if not "%PYTHON_BIN%" == "" goto python_found

REM No python in path, see if its in a default location. Prefer
REM Python 2.7, since our installer ships with that as default
set PYTHON_BIN=C:\Python27\%PYTHON_EXE%
if exist "%PYTHON_BIN%" goto python_found

set PYTHON_BIN=C:\Python26\%PYTHON_EXE%
if not exist "%PYTHON_BIN%" goto nopython

:python_found
if "%EXAILE_CONSOLE%" == "Y" (
    echo INFO    : Python: %PYTHON_BIN%>&2
)

goto start_exaile

REM Various errors

:nopython
echo Python 2.7 was not detected. Please include the python directory in your>&2
echo PATH, or install it. You can download it at https://www.python.org/>&2
if not "%EXAILE_CONSOLE%" == "Y" (
	echo.>&2
	pause
)
endlocal
exit /B 1

:start_exaile

pushd %~dp0
if "%EXAILE_CONSOLE%" == "Y" goto start_exaile_in_console
start "" "%PYTHON_BIN%" exaile_win.py --startgui --no-dbus --no-hal %*
popd
goto end

:start_exaile_in_console
REM Note: Cannot use %* here because we use 'shift' above
"%PYTHON_BIN%" exaile_win.py --startgui --no-dbus --no-hal %1 %2 %3 %4 %5 %6 %7 %8 %9
popd
goto end

:end
endlocal
