@echo off
echo Installing required packages...
pip install -r requirements.txt
echo.
echo Starting dashboard...
echo The dashboard will open in your browser automatically.
echo.
streamlit run dashboard.py
pause