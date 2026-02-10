@echo off
REM Quick PyPI Authentication Test using curl (simpler than PowerShell)
REM This uses curl's built-in authentication which handles base64 encoding automatically

setlocal enabledelayedexpansion

REM Parse command line arguments
set URL=%~1
set USERNAME=%~2
set PASSWORD=%~3

if "%URL%"=="" (
    echo ================================================================================
    echo PyPI Authentication Test - Using curl
    echo ================================================================================
    echo.
    echo Usage: test-pypi-auth-curl.bat URL USERNAME PASSWORD
    echo.
    echo Example:
    echo   test-pypi-auth-curl.bat ^
    echo     "https://artifactory.example.com/artifactory/api/pypi/pypi-remote/pypi/joblib/json" ^
    echo     "myuser" ^
    echo     "your-password"
    echo.
    echo Or set environment variables first:
    echo   set PYPI_URL=https://artifactory.example.com/artifactory/api/pypi/pypi-remote
    echo   set PYPI_USERNAME=myuser
    echo   set PYPI_PASSWORD=your-password
    echo   test-pypi-auth-curl.bat "%%PYPI_URL%%/pypi/joblib/json" "%%PYPI_USERNAME%%" "%%PYPI_PASSWORD%%"
    echo.
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

echo ================================================================================
echo PyPI Authentication Test - Matching K6 Headers
echo ================================================================================
echo.
echo URL: %URL%
echo Username: %USERNAME%
echo Password: ********
echo.
echo Headers (matching K6 getPypiAuthHeaders):
echo   User-Agent: pip/23.0 CPython/3.11.0
echo   Accept: */*
echo   Authorization: Basic ^<base64^(username:password^)^>
echo.
echo ================================================================================
echo Making request...
echo ================================================================================
echo.

REM Make curl request with exact headers matching K6
curl -v ^
  -u "%USERNAME%:%PASSWORD%" ^
  -H "User-Agent: pip/23.0 CPython/3.11.0" ^
  -H "Accept: */*" ^
  "%URL%"

set CURL_EXIT=%ERRORLEVEL%

echo.
echo ================================================================================
echo Result
echo ================================================================================
echo.

if %CURL_EXIT% equ 0 (
    echo ✓ Request completed successfully
    echo.
    echo Check the HTTP status code above:
    echo   - 200: Success - Package found
    echo   - 401: Authentication failed
    echo   - 404: Auth OK, but package not found ^(this is fine for testing^)
    echo   - 403: Auth OK, but no permission
) else (
    echo ✗ Request failed with exit code %CURL_EXIT%
    echo.
    echo Common curl errors:
    echo   - 6: Couldn't resolve host
    echo   - 7: Failed to connect
    echo   - 35: SSL connection error
    echo   - 60: SSL certificate problem
)

echo.
echo To test with SSL verification disabled ^(self-signed certs^):
echo   curl -k -v -u "%USERNAME%:%PASSWORD%" ^
echo     -H "User-Agent: pip/23.0 CPython/3.11.0" ^
echo     -H "Accept: */*" ^
echo     "%URL%"
echo.

exit /b %CURL_EXIT%
