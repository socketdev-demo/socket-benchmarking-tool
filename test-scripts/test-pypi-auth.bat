@echo off
REM PyPI Authentication Test - Windows Batch Wrapper
REM This script calls the PowerShell script to test PyPI authentication

REM Check if PowerShell script exists
if not exist "%~dp0test-pypi-auth.ps1" (
    echo Error: test-pypi-auth.ps1 not found!
    exit /b 1
)

REM Parse command line arguments
set URL=%1
set USERNAME=%2
set PASSWORD=%3

if "%URL%"=="" (
    echo Usage: test-pypi-auth.bat URL USERNAME PASSWORD
    echo.
    echo Example (using Simple API - PEP 503):
    echo   test-pypi-auth.bat "https://artifactory.example.com/artifactory/api/pypi/pypi-remote/simple/joblib/" "myuser" "your-password"
    echo.
    echo Or use environment variables:
    echo   set PYPI_URL=https://...
    echo   set PYPI_USERNAME=myuser
    echo   set PYPI_PASSWORD=your-password
    echo   test-pypi-auth.bat "%%PYPI_URL%%/simple/joblib/" "%%PYPI_USERNAME%%" "%%PYPI_PASSWORD%%"
    exit /b 1
)

if "%USERNAME%"=="" (
    echo Error: USERNAME is required
    exit /b 1
)

if "%PASSWORD%"=="" (
    echo Error: PASSWORD is required
    exit /b 1
)

REM Call PowerShell script with parameters
powershell -ExecutionPolicy Bypass -File "%~dp0test-pypi-auth.ps1" -Url %URL% -Username %USERNAME% -Password %PASSWORD% -Verbose

exit /b %ERRORLEVEL%
