@echo off
setlocal enabledelayedexpansion

:: ==========================================
:: 1. Define Tool Version URLs
:: ==========================================
set GIT_PORTABLE_X64=https://github.com/git-for-windows/git/releases/download/v2.54.0.windows.1/PortableGit-2.54.0-64-bit.7z.exe
set NODEJS=https://nodejs.org/dist/v22.23.1/node-v22.23.1-win-x64.zip
set HUGO=https://github.com/gohugoio/hugo/releases/download/v0.153.5/hugo_extended_0.153.5_windows-amd64.zip
set VSCODE=https://update.code.visualstudio.com/latest/win32-x64-archive/stable

:: Define local directory structures
set "TOOLS_DIR=%CD%\Tools"
set "NEED_PATH_UPDATE=0"
set "NEW_PATHS="

echo Checking environment availability...
echo ------------------------------------------

:: ==========================================
:: 2. Check and Setup GIT
:: ==========================================
where git >nul 2>nul
if %errorlevel% equ 0 (
    echo [✓] Git is already available in PATH.
) else (
    echo [X] Git not found. Preparing localized deployment...
    if not exist "%TOOLS_DIR%\Git" mkdir "%TOOLS_DIR%\Git"
    
    if not exist "%TOOLS_DIR%\Git\cmd\git.exe" (
        echo Downloading Git...
        curl -L -o "%TOOLS_DIR%\git_setup.exe" "%GIT_PORTABLE_X64%"
        echo Extracting Git...
        "%TOOLS_DIR%\git_setup.exe" -y -o"%TOOLS_DIR%\Git" >nul
        del "%TOOLS_DIR%\git_setup.exe"
    )
    set "NEED_PATH_UPDATE=1"
    set "NEW_PATHS=!NEW_PATHS!%TOOLS_DIR%\Git\cmd;"
)

:: ==========================================
:: 3. Check and Setup NODEJS
:: ==========================================
where node >nul 2>nul
if %errorlevel% equ 0 (
    echo [✓] Node.js is already available in PATH.
) else (
    echo [X] Node.js not found. Preparing localized deployment...
    if not exist "%TOOLS_DIR%\Node" mkdir "%TOOLS_DIR%\Node"
    
    set "NODE_EXE="
    for /r "%TOOLS_DIR%\Node" %%f in (node.exe) do if exist "%%f" set "NODE_EXE=%%f"
    
    if "!NODE_EXE!"=="" (
        echo Downloading Node.js...
        curl -L -o "%TOOLS_DIR%\node.zip" "%NODEJS%"
        echo Extracting Node.js...
        tar -xf "%TOOLS_DIR%\node.zip" -C "%TOOLS_DIR%\Node"
        del "%TOOLS_DIR%\node.zip"
        for /r "%TOOLS_DIR%\Node" %%f in (node.exe) do if exist "%%f" set "NODE_EXE=%%f"
    )
    
    for %%I in ("!NODE_EXE!") do set "NODE_BIN_DIR=%%~dpI"
    set "NEED_PATH_UPDATE=1"
    set "NEW_PATHS=!NEW_PATHS!!NODE_BIN_DIR!;"
)

:: ==========================================
:: 4. Check and Setup HUGO
:: ==========================================
where hugo >nul 2>nul
if %errorlevel% equ 0 (
    echo [✓] Hugo is already available in PATH.
) else (
    echo [X] Hugo not found. Preparing localized deployment...
    if not exist "%TOOLS_DIR%\Hugo" mkdir "%TOOLS_DIR%\Hugo"
    
    if not exist "%TOOLS_DIR%\Hugo\hugo.exe" (
        echo Downloading Hugo...
        curl -L -o "%TOOLS_DIR%\hugo.zip" "%HUGO%"
        echo Extracting Hugo...
        tar -xf "%TOOLS_DIR%\hugo.zip" -C "%TOOLS_DIR%\Hugo"
        del "%TOOLS_DIR%\hugo.zip"
    )
    set "NEED_PATH_UPDATE=1"
    set "NEW_PATHS=!NEW_PATHS!%TOOLS_DIR%\Hugo;"
)

:: ==========================================
:: 5. Check and Setup VSCODE
:: ==========================================
where code >nul 2>nul
if %errorlevel% equ 0 (
    echo [✓] VS Code is already available in PATH.
) else (
    echo [X] VS Code not found. Preparing localized deployment...
    if not exist "%TOOLS_DIR%\VSCode" mkdir "%TOOLS_DIR%\VSCode"
    
    set "CODE_EXE="
    for /r "%TOOLS_DIR%\VSCode" %%f in (code.exe) do if exist "%%f" set "CODE_EXE=%%f"
    
    if "!CODE_EXE!"=="" (
        echo Downloading VS Code Archive...
        curl -L -o "%TOOLS_DIR%\vscode.zip" "%VSCODE%"
        echo Extracting VS Code...
        tar -xf "%TOOLS_DIR%\vscode.zip" -C "%TOOLS_DIR%\VSCode"
        del "%TOOLS_DIR%\vscode.zip"
        for /r "%TOOLS_DIR%\VSCode" %%f in (code.exe) do if exist "%%f" set "CODE_EXE=%%f"
    )
    
    for %%I in ("!CODE_EXE!") do set "VSCODE_BASE_DIR=%%~dpI"
    set "CODE_BIN_DIR=!VSCODE_BASE_DIR!bin"
    
    set "NEED_PATH_UPDATE=1"
    set "NEW_PATHS=!NEW_PATHS!!CODE_BIN_DIR!;"
)

:: ==========================================
:: 6. Apply Environmental Upgrades
:: ==========================================
if "%NEED_PATH_UPDATE%"=="1" (
    echo Update detected. Appending environment paths for this terminal session...
    set "PATH=!PATH!;!NEW_PATHS!"
)

:: ==========================================
:: 7. Output Final Status Summary & Versions
:: ==========================================
echo.
echo ==========================================
echo      FINAL RUNTIME VERSION SUMMARY        
echo ==========================================

for /f "tokens=*" %%a in ('git --version 2^>nul') do set "GIT_VER=%%a"
if not defined GIT_VER set "GIT_VER=Not available"

for /f "tokens=*" %%a in ('node --version 2^>nul') do set "NODE_VER=%%a"
if not defined NODE_VER set "NODE_VER=Not available"

for /f "tokens=*" %%a in ('hugo version 2^>nul') do set "HUGO_VER=%%a"
if not defined HUGO_VER set "HUGO_VER=Not available"

:: Parse the redirect URL using corrected headers token loops
set "VSCODE_VER=Not available"
for /f "tokens=2 delims= " %%g in ('curl -sI "%VSCODE%" ^| findstr /I "location:"') do (
    set "RAW_URL=%%g"
    :: Clean carriage returns
    set "RAW_URL=!RAW_URL:~0,-1!"
    
    :: Parse the version sequence out from the resolved name structural string
    for /f "tokens=6 delims=/" %%v in ("!RAW_URL!") do (
        set "VSCODE_VER=%%v"
    )
)

:: Fallback fallback check: If network parse missed it, just verify the dynamic bin directory path exists locally
if "%VSCODE_VER%"=="Not available" (
    where code >nul 2>nul
    if !errorlevel! equ 0 (
        set "VSCODE_VER=Available (Local Archive)"
    )
)

echo GIT_PORTABLE_X64 : %GIT_VER%
echo NODEJS           : %NODE_VER%
echo HUGO             : %HUGO_VER%
echo VSCODE           : %VSCODE_VER%
echo ==========================================

endlocal & set "PATH=%PATH%"
