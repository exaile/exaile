@echo off
REM 
REM Win32 launch script for Exaile
REM
REM Since GStreamer SDK and OSSBuild are a bit difficult to work with, we
REM go through and set things up for the user so they don't need to worry
REM too much about PATH variables being set properly and other madness. 
REM
REM Additionally, this script tries to be a bit more verbose and let the 
REM user know more about the errors that they are seeing, instead of just a
REM stack trace.
REM

setlocal

set EXAILE_CONSOLE=N
set PYTHON_EXE=pythonw.exe

if "%1" == "console" set EXAILE_CONSOLE=Y
if "%1" == "console" shift

REM If certain arguments are passed, we must start in a console or the user
REM will be a bit confused... 

for %%I in (%*) DO (
    if "%%I" == "--help" set EXAILE_CONSOLE=Y
    if "%%I" == "--debug" set EXAILE_CONSOLE=Y
    if "%%I" == "--version" set EXAILE_CONSOLE=Y
)

if "%EXAILE_CONSOLE%" == "Y" set PYTHON_EXE=python.exe

echo Detecting Exaile requirements (this may take a minute or two): 

REM Detect Python in the path
for %%X in (%PYTHON_EXE%) do (set PYTHON_BIN=%%~$PATH:X)
if defined PYTHON_BIN goto python_found

REM No python in path, see if its in a default location. Prefer
REM Python 2.7, since our installer ships with that as default
set PYTHON_BIN=C:\Python27\%PYTHON_EXE%
if exist %PYTHON_BIN% goto python_found

set PYTHON_BIN=C:\Python26\%PYTHON_EXE%
if not exist %PYTHON_BIN% goto nopython

:python_found
echo     Python                     : %PYTHON_BIN%

REM See if pygst *just works*
set PYGST_BINDINGS=In python path
%PYTHON_BIN% -c "import pygst;pygst.require('0.10');import gst" 
if %ERRORLEVEL% == 0 goto pygst_found

REM Nope... detect GStreamer SDK
set GST_VIA=environment
set GST_SDK=N
if defined GSTREAMER_SDK_ROOT_X86 set GST_SDK=%GSTREAMER_SDK_ROOT_X86%
if defined GSTREAMER_SDK_ROOT_X64 set GST_SDK=%GSTREAMER_SDK_ROOT_X64%

if not "%GST_SDK%" == "N" goto pygst_env_found

REM For some reason the GStreamer SDK doesn't define the environment
REM variables globally, so we just have to cheat if we can't do it
REM the 'correct' way
if exist C:\gstreamer-sdk\0.10\x86\bin goto found_pygst_x86_hardcoded
if exist C:\gstreamer-sdk\0.10\x64\bin goto found_pygst_x64_hardcoded
goto nogst

:found_pygst_x86_hardcoded
set GSTREAMER_SDK_ROOT_X86=C:\gstreamer-sdk\0.10\x86
set GST_SDK=%GSTREAMER_SDK_ROOT_X86%
set GST_VIA=hardcoded path
goto pygst_env_found

:found_pygst_x64_hardcoded
set GSTREAMER_SDK_ROOT_X64=C:\gstreamer-sdk\0.10\x64
set GST_SDK=%GSTREAMER_SDK_ROOT_X64%
set GST_VIA=hardcoded path
goto pygst_env_found


:pygst_env_found
echo     GStreamer SDK Runtime      : %GST_SDK% (via %GST_VIA%)

REM
REM Then try to setup the environment properly for GStreamer SDK
REM -> Note that we put the GST path first, so that any needed DLLs
REM    are searched for there first, hopefully avoiding DLL hell
REM 

set PATH=%GST_SDK%\bin;%PATH%
set PYGST_BINDINGS=%GST_SDK%\lib\python2.7\site-packages
if defined PYTHONPATH set PYTHONPATH=%PYGST_BINDINGS%;%PYTHONPATH%
if not defined PYTHONPATH set PYTHONPATH=%PYGST_BINDINGS%

%PYTHON_BIN% -c "import pygst;pygst.require('0.10');import gst"
if not %ERRORLEVEL% == 0 goto badgst

:pygst_found
echo     GStreamer Python Bindings  : %PYGST_BINDINGS%

REM Detect PyGTK. We do detection here since it may be in the GStreamer SDK
%PYTHON_BIN% -c "import pygtk;pygtk.require('2.0');import gtk"
if not %ERRORLEVEL% == 0 goto badgtk

echo     PyGTK                      : OK

REM Detect Mutagen now
%PYTHON_BIN% -c "import mutagen" 2> nul
if not %ERRORLEVEL% == 0 goto badmutagen

echo     Mutagen                    : OK
echo.

echo Dependencies good, starting exaile.
echo.

goto start_exaile

REM Various errors

:nopython
echo Python 2.7 was not detected. Please include the python directory in your
echo PATH, or install it. You can download it at http://www.python.com/
echo.
pause && goto end

:nogst
echo     GStreamer SDK Runtime      : not found
echo.
echo GStreamer SDK Runtime was not found. 
echo.
echo You can download the GST SDK runtime at http://www.gstreamer.com/
echo.
echo See %~dp0\README.Win32 for more information. 
echo.
pause && goto end

:badgst
echo     GStreamer Python Bindings  : not found
echo.
echo The python bindings for GStreamer could not be imported. Please re-run the
echo installer and ensure that the python bindings are selected for 
echo installation (they should be selected by default). 
echo.
echo You can download the GST SDK runtime at http://www.gstreamer.com/
echo.
echo See %~dp0\README.Win32 for more information. 
echo.
pause && goto end

:badgtk
echo.
echo PyGTK 2.x could not be imported. It is installed by default with the
echo GStreamer SDK (select GTK Python Bindings), or you can use the 
echo PyGTK all-in-one installer from http://www.pygtk.org/
echo.
echo Note that the PyGTK all-in-one installer is NOT compatible with
echo the GStreamer SDK.
echo.
echo You can download the GST SDK runtime at http://www.gstreamer.com/
echo.
echo See %~dp0\README.Win32 for more information. 
echo.
pause && goto end

:badmutagen
echo.
echo The Mutagen python module could not be imported. It can be downloaded 
echo from http://code.google.com/p/mutagen/
echo.
echo See %~dp0\README.Win32 for more information. 
echo.
pause && goto end

:start_exaile

pushd %~dp0
if "%EXAILE_CONSOLE%" == "Y" goto start_exaile_in_console
start %PYTHON_BIN% exaile.py --startgui --no-dbus --no-hal %*
popd
goto end

:start_exaile_in_console
REM Note: Cannot use %* here because we use 'shift' above
%PYTHON_BIN% exaile.py --startgui --no-dbus --no-hal %1 %2 %3 %4 %5 %6 %7 %8 %9
popd
goto end

:end
endlocal
