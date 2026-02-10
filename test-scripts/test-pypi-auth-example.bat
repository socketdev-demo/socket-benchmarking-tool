@echo off
REM Quick PyPI Authentication Test - Edit this file with your credentials
REM Copy this file, edit the values below, and run it

REM ===== EDIT THESE VALUES =====
set PYPI_URL=https://artifactory.example.com/artifactory/api/pypi/pypi-remote
set PYPI_USERNAME=myuser
set PYPI_PASSWORD=your-password-here
REM =============================

echo.
echo Testing PyPI authentication with K6-compatible headers...
echo.
echo URL: %PYPI_URL%
echo Username: %PYPI_USERNAME%
echo.

REM Test with a common package
call test-pypi-auth-curl.bat "%PYPI_URL%/pypi/joblib/json" "%PYPI_USERNAME%" "%PYPI_PASSWORD%"

if %ERRORLEVEL% equ 0 (
    echo.
    echo ================================================================================
    echo SUCCESS! Authentication is working.
    echo ================================================================================
    echo.
    echo You can now run the full load test with:
    echo.
    echo   socket-load-test setup \
    echo     --ecosystems pypi \
    echo     --pypi-url "%PYPI_URL%" \
    echo     --pypi-username "%PYPI_USERNAME%" \
    echo     --pypi-password "%PYPI_PASSWORD%" \
    echo     --verbose
    echo.
) else (
    echo.
    echo ================================================================================
    echo FAILED - Check the error messages above
    echo ================================================================================
    echo.
)

pause
