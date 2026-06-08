@echo off
setlocal
title Opus to MP3 Converter

where ffmpeg >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo FFmpeg was not found.
  echo.
  echo Install it with:
  echo winget install Gyan.FFmpeg
  echo.
  pause
  exit /b 1
)

echo Opus to MP3 Converter
echo.
echo This converts .opus files into Roblox-compatible .mp3 files.
echo Converted files are saved in this tool's converted folder.
echo.
echo Tip: Drag your folder into this window, then press Enter.
echo.
set /p "SOURCE_FOLDER=Folder with .opus files: "
set "SOURCE_FOLDER=%SOURCE_FOLDER:"=%"

if "%SOURCE_FOLDER%"=="" (
  echo No folder was entered.
  echo.
  pause
  exit /b 1
)

if not exist "%SOURCE_FOLDER%" (
  echo Folder not found:
  echo %SOURCE_FOLDER%
  echo.
  pause
  exit /b 1
)

set "OUTPUT_FOLDER=%~dp0converted"
if not exist "%OUTPUT_FOLDER%" mkdir "%OUTPUT_FOLDER%"

echo.
set /p "RECURSIVE=Include subfolders? y/N: "
echo.
echo Converting...
echo.

if /I "%RECURSIVE%"=="y" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%SOURCE_FOLDER%' -Recurse -Filter *.opus | ForEach-Object { $relative = [System.IO.Path]::GetRelativePath('%SOURCE_FOLDER%', $_.DirectoryName); $destDir = Join-Path '%OUTPUT_FOLDER%' $relative; New-Item -ItemType Directory -Force -Path $destDir | Out-Null; ffmpeg -y -i $_.FullName -codec:a libmp3lame -b:a 192k (Join-Path $destDir ($_.BaseName + '.mp3')) }"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%SOURCE_FOLDER%' -Filter *.opus | ForEach-Object { ffmpeg -y -i $_.FullName -codec:a libmp3lame -b:a 192k (Join-Path '%OUTPUT_FOLDER%' ($_.BaseName + '.mp3')) }"
)

echo.
echo Done. Converted files are here:
echo %OUTPUT_FOLDER%
echo.
pause
