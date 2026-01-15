@echo off
echo Installing required packages for Airtable sync...
pip install pyairtable
echo.
echo Running Airtable sync...
echo.
python airtable_sync.py
pause