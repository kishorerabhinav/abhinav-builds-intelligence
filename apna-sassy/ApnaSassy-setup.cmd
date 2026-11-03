@echo off
setlocal
chcp 65001 >nul
title Apna Sassy setup

echo.
echo  Apna Sassy - setting up the project on your Desktop
echo  ===================================================
echo.

rem Find the real Desktop folder (works when OneDrive moves it too)
for /f "usebackq delims=" %%d in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%d"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
set "PROJECT=%DESKTOP%\abhinav-builds-intelligence"
set "GIT=C:\Program Files\Git\cmd\git.exe"
set "CLAUDE=%USERPROFILE%\.local\bin\claude.exe"

echo  Desktop folder: %DESKTOP%
echo.

rem 1. Git
if exist "%GIT%" (
  echo  [1/4] Git is already installed.
) else (
  echo  [1/4] Installing Git...
  winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
  if not exist "%GIT%" (
    echo.
    echo  Git did not install. Install it from https://git-scm.com/download/win and run this file again.
    pause
    exit /b 1
  )
)

rem 2. Claude Code
if exist "%CLAUDE%" (
  echo  [2/4] Claude Code is already installed.
) else (
  echo  [2/4] Installing Claude Code...
  curl -fsSL https://claude.ai/install.cmd -o "%TEMP%\claude-install.cmd" && call "%TEMP%\claude-install.cmd"
  del "%TEMP%\claude-install.cmd" 2>nul
  if not exist "%CLAUDE%" (
    echo.
    echo  Claude Code did not install. See https://code.claude.com/docs and run this file again.
    pause
    exit /b 1
  )
)

rem 3. The project, with everything done so far
if exist "%PROJECT%\.git" (
  echo  [3/4] Project already on Desktop - getting the latest changes...
  "%GIT%" -C "%PROJECT%" fetch origin claude/sprout-platformer
  "%GIT%" -C "%PROJECT%" checkout claude/sprout-platformer
  "%GIT%" -C "%PROJECT%" pull origin claude/sprout-platformer
) else (
  echo  [3/4] Downloading the project to your Desktop...
  echo        If a GitHub sign-in window opens, log in as kishorerabhinav.
  "%GIT%" clone -b claude/sprout-platformer https://github.com/kishorerabhinav/abhinav-builds-intelligence.git "%PROJECT%"
  if errorlevel 1 (
    echo.
    echo  Download failed. Check your internet connection and GitHub login, then run this file again.
    pause
    exit /b 1
  )
)

rem 4. Open Claude Code in the game folder; it reads CLAUDE.md automatically
echo  [4/4] Starting Claude Code in %PROJECT%\apna-sassy
echo.
echo  When it is ready, type:
echo    Read CLAUDE.md and help me install Apna Sassy on my iPhone with Sideloadly.
echo.
cd /d "%PROJECT%\apna-sassy"
"%CLAUDE%"
