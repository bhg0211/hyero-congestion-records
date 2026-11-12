@echo off
rem Daily backup of the forward-validation records into this repo.
rem Windows Task Scheduler: hyero\congestion_backup_records (23:40 every day)
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
"..\hyero-ev-charging-app\congestion\.venv\Scripts\python.exe" backup_records.py >> backup.log 2>&1
