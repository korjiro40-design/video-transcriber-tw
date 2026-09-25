@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="" (
  echo 請把影片或音訊拖到這個檔案上。
  pause
  exit /b
)
影片逐字稿.exe %*
