@echo off
REM Manual Package Cache Script for Artifactory
REM Usage: cache-packages.bat <input-file>
REM 
REM Input file format:
REM #npm - https://artifactory.example.com/artifactory/api/npm/npm-registry-proxy-remote
REM package, version
REM
REM #maven - https://artifactory.example.com/artifactory/api/maven/maven-central-proxy-remote
REM group:artifact, version
REM
REM #pypi - https://artifactory.example.com/artifactory/api/pypi/pypi-python-wf-proxy-proxy-remote
REM package, version

setlocal enabledelayedexpansion

if "%~1"=="" (
    echo Usage: %0 ^<input-file^>
    echo.
    echo Example input file format:
    echo #npm - https://artifactory.example.com/artifactory/api/npm/npm-registry-proxy-remote
    echo @babel/core, 7.23.7
    echo react, 18.2.0
    echo.
    echo #maven - https://artifactory.example.com/artifactory/api/maven/maven-central-proxy-remote
    echo junit:junit, 4.13.2
    echo.
    echo #pypi - https://artifactory.example.com/artifactory/api/pypi/pypi-python-wf-proxy-proxy-remote
    echo requests, 2.32.3
    exit /b 1
)

set INPUT_FILE=%~1
set CURRENT_ECOSYSTEM=
set CURRENT_BASE_URL=
set SUCCESS_COUNT=0
set FAIL_COUNT=0

if not exist "%INPUT_FILE%" (
    echo Error: File '%INPUT_FILE%' not found
    exit /b 1
)

echo Starting package caching...
echo ================================

REM Read file line by line
for /f "usebackq delims=" %%a in ("%INPUT_FILE%") do (
    set "line=%%a"
    
    REM Skip empty lines
    if not "!line!"=="" (
        REM Check if this is an ecosystem header (#ecosystem - url)
        set "first_char=!line:~0,1!"
        if "!first_char!"=="#" (
            REM Parse ecosystem header
            for /f "tokens=1,2 delims=-" %%b in ("!line!") do (
                set "eco=%%b"
                set "url=%%c"
                REM Remove # and whitespace from ecosystem
                set "eco=!eco:~1!"
                set "eco=!eco: =!"
                REM Remove leading whitespace from URL
                set "url=!url:~1!"
                set CURRENT_ECOSYSTEM=!eco!
                set CURRENT_BASE_URL=!url!
                echo.
                echo Ecosystem: !CURRENT_ECOSYSTEM!
                echo Base URL: !CURRENT_BASE_URL!
                echo --------------------------------
            )
        ) else (
            REM Process package line
            if not "!CURRENT_ECOSYSTEM!"=="" (
                REM Parse package, version
                for /f "tokens=1,2 delims=," %%b in ("!line!") do (
                    set "package=%%b"
                    set "version=%%c"
                    REM Trim whitespace
                    set "package=!package: =!"
                    set "version=!version: =!"
                    
                    if "!CURRENT_ECOSYSTEM!"=="npm" (
                        call :cache_npm "!package!" "!version!" "!CURRENT_BASE_URL!"
                    ) else if "!CURRENT_ECOSYSTEM!"=="maven" (
                        call :cache_maven "!package!" "!version!" "!CURRENT_BASE_URL!"
                    ) else if "!CURRENT_ECOSYSTEM!"=="pypi" (
                        call :cache_pypi "!package!" "!version!" "!CURRENT_BASE_URL!"
                    )
                )
            )
        )
    )
)

echo ================================
echo Caching complete!
echo Success: %SUCCESS_COUNT%
echo Failed: %FAIL_COUNT%
exit /b 0

REM ============ NPM Cache Function ============
:cache_npm
setlocal
set "pkg=%~1"
set "ver=%~2"
set "base=%~3"

echo   [NPM] Caching %pkg%@%ver%

REM Get metadata first
set "metadata_url=%base%/%pkg%"
echo     - Fetching metadata: %metadata_url%

curl -f -s -o nul -w "%%{http_code}" "%metadata_url%" > temp_status.txt
set /p status_code=<temp_status.txt
del temp_status.txt

if "%status_code%"=="200" (
    echo     √ Metadata cached ^(200 OK^)
) else (
    echo     × Metadata failed
    set /a FAIL_COUNT+=1
    endlocal
    goto :eof
)

REM Download the package tarball
REM Handle scoped packages (@org/package)
set "first_char=%pkg:~0,1%"
if "%first_char%"=="@" (
    REM Extract package name after last /
    for %%i in ("%pkg:/=" "%") do set "pkg_name=%%~i"
    set "download_url=%base%/%pkg%/-/!pkg_name!-%ver%.tgz"
) else (
    set "download_url=%base%/%pkg%/-/%pkg%-%ver%.tgz"
)

echo     - Downloading package: !download_url!

curl -f -s -o nul -w "%%{http_code}" "!download_url!" > temp_status.txt
set /p status_code=<temp_status.txt
del temp_status.txt

if "%status_code%"=="200" (
    echo     √ Package downloaded ^(200 OK^)
    set /a SUCCESS_COUNT+=1
) else (
    echo     × Package download failed ^(HTTP %status_code%^)
    set /a FAIL_COUNT+=1
)

echo.
endlocal
goto :eof

REM ============ Maven Cache Function ============
:cache_maven
setlocal
set "pkg=%~1"
set "ver=%~2"
set "base=%~3"

REM Split group:artifact
for /f "tokens=1,2 delims=:" %%a in ("%pkg%") do (
    set "group=%%a"
    set "artifact=%%b"
)

if "!artifact!"=="" (
    echo   [MAVEN] Invalid format for %pkg% ^(expected group:artifact^)
    set /a FAIL_COUNT+=1
    endlocal
    goto :eof
)

REM Convert dots to slashes for group path
set "group_path=!group:.=/!"

echo   [MAVEN] Caching !group!:!artifact!@%ver%

REM Get metadata first
set "metadata_url=%base%/!group_path!/!artifact!/maven-metadata.xml"
echo     - Fetching metadata: !metadata_url!

curl -f -s -o nul -w "%%{http_code}" "!metadata_url!" > temp_status.txt
set /p status_code=<temp_status.txt
del temp_status.txt

if "%status_code%"=="200" (
    echo     √ Metadata cached ^(200 OK^)
) else (
    echo     × Metadata failed
    set /a FAIL_COUNT+=1
    endlocal
    goto :eof
)

REM Download the JAR file
set "download_url=%base%/!group_path!/!artifact!/%ver%/!artifact!-%ver%.jar"
echo     - Downloading artifact: !download_url!

curl -f -s -o nul -w "%%{http_code}" "!download_url!" > temp_status.txt
set /p status_code=<temp_status.txt
del temp_status.txt

if "%status_code%"=="200" (
    echo     √ Artifact downloaded ^(200 OK^)
    set /a SUCCESS_COUNT+=1
) else (
    echo     × Artifact download failed ^(HTTP %status_code%^)
    set /a FAIL_COUNT+=1
)

echo.
endlocal
goto :eof

REM ============ PyPI Cache Function ============
:cache_pypi
setlocal
set "pkg=%~1"
set "ver=%~2"
set "base=%~3"

echo   [PYPI] Caching %pkg%@%ver%

REM Get metadata first
set "metadata_url=%base%/simple/%pkg%/"
echo     - Fetching metadata: !metadata_url!

curl -f -s -o nul -w "%%{http_code}" "!metadata_url!" > temp_status.txt
set /p status_code=<temp_status.txt
del temp_status.txt

if "%status_code%"=="200" (
    echo     √ Metadata cached ^(200 OK^)
    echo     i Metadata cached. To cache specific wheel/tar.gz, access the download URL directly.
    set /a SUCCESS_COUNT+=1
) else (
    echo     × Metadata failed
    set /a FAIL_COUNT+=1
)

echo.
endlocal
goto :eof
