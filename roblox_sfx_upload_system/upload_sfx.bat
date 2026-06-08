@echo off
setlocal
title Roblox Sound Uploader
set "BUNDLED_PY=C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PY%" (
  set "PYTHON_CMD=%BUNDLED_PY%"
) else (
  where py >nul 2>nul
  if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=py"
  ) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
      set "PYTHON_CMD=python"
    ) else (
      echo Python was not found. Install Python 3 or add it to PATH.
      pause
      exit /b 1
    )
  )
)

"%PYTHON_CMD%" --version >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo Python was found, but it did not run correctly.
  echo If Windows opened the Microsoft Store prompt, disable the Python app execution alias
  echo in Settings ^> Apps ^> Advanced app settings ^> App execution aliases.
  echo.
  pause
  exit /b 1
)

if not "%~1"=="" (
  "%PYTHON_CMD%" "%~dp0upload_sfx.py" %*
  echo.
  pause
  exit /b %ERRORLEVEL%
)

echo Roblox Sound Uploader
echo.
echo This uploads every .mp3, .ogg, .wav, and .flac in a folder.
echo Results will be saved in the output folder.
echo.
echo Tip: You can drag the SFX folder into this window, then press Enter.
echo.
set /p "SFX_FOLDER=SFX folder path: "
set "SFX_FOLDER=%SFX_FOLDER:"=%"

if "%SFX_FOLDER%"=="" (
  echo No folder was entered.
  echo.
  pause
  exit /b 1
)

echo.
echo Who should own the uploaded audio?
echo   1 = Group
echo   2 = User
set /p "OWNER_TYPE=Choose 1 or 2: "

if "%OWNER_TYPE%"=="1" (
  set /p "OWNER_ID=Group ID: "
  set "OWNER_ARG=--group-id"
) else if "%OWNER_TYPE%"=="2" (
  set /p "OWNER_ID=User ID: "
  set "OWNER_ARG=--user-id"
) else (
  echo Invalid choice.
  echo.
  pause
  exit /b 1
)

if "%OWNER_ID%"=="" (
  echo No ID was entered.
  echo.
  pause
  exit /b 1
)

echo.
set /p "RECURSIVE=Include subfolders? y/N: "
set "EXTRA_ARGS="
if /I "%RECURSIVE%"=="y" set "EXTRA_ARGS=--recursive"

echo.
echo Starting upload...
echo.
"%PYTHON_CMD%" "%~dp0upload_sfx.py" "%SFX_FOLDER%" %OWNER_ARG% %OWNER_ID% %EXTRA_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
