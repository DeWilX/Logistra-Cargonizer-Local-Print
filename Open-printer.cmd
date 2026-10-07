@echo off
cd /d "%~dp0"
py -3 printer_setup.py
if errorlevel 1 pause
