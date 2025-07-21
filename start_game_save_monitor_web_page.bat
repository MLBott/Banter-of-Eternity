@echo off
echo 🎭 Pillars of Eternity II - Vignette Generator and Web Interface
echo ================================================================

echo 📦 Installing required packages...
pip install flask flask-cors

echo.
echo 📂 Setting up game save monitoring...
echo 📖 Setting up vignette generation...
echo 🚀 Starting web server...
echo 🔗 Open your browser at http://localhost:5000
python main_start.py

pause
