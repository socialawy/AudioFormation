@echo off
echo 🔍 Audio Formation Quick Check
echo ================================

echo.
echo 📦 Installing dependencies...
python -m pip install pydub soundfile edge-tts pyloudnorm midiutil

echo.
echo 🏃 Running fast check...
python fast_check.py

echo.
echo ✅ Quick check complete!
