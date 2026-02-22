@echo off
SET ROOT=%~dp0
SET setenv=8)Soft\setenv3.bat
CALL %setenv%

"%PYTHON_EXECUTABLE%" "%FACEJAPP%\gui.py" %ROOT% %PYTHON_EXECUTABLE% %ROOT%\%setenv%

set res=%errorlevel%

if %res% == 1 CALL 8)Soft\get_license.bat

if %res% == 1 %PYTHON_EXECUTABLE% %FACEJAPP%\gui.py %ROOT% %PYTHON_EXECUTABLE% %ROOT%\%setenv%

pause
