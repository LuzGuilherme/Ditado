@echo off
echo ====================================
echo  Ditado - Build Executable
echo ====================================
echo.
echo Building with PyInstaller...
pyinstaller --clean ditado.spec
echo.
echo Build complete! Executable is in the 'dist' folder.
pause
