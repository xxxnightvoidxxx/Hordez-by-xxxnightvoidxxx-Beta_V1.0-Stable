@echo off
title HORDEZ - Survival Game
color 07
cd /d "%~dp0"

cls
echo.
echo     =================================================================
echo     =                                                               =                                 
echo     =                          H O R D E Z                          =
echo     =                                                               =                                
echo     =                     The Dead Are Coming...                    =  
echo     =                                                               =                     
echo     =                        [ LAUNCHING... ]                       =
echo     =                                                               =                                    
echo     =================================================================
echo.
echo.

:: Check if Python exists
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed!
    echo.
    echo  Download Python: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Display Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo  [OK] %%i
echo.

:: Setup virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created
) else (
    echo  [1/3] Virtual environment already exists
)

:: Activate virtual environment
echo  [2/3] Activating environment...
call .venv\Scripts\activate.bat >nul 2>&1
echo  [OK] Environment activated

:: Install requirements
echo  [3/3] Installing requirements...
pip install pygame colorama -q >nul 2>&1
echo  [OK] Requirements satisfied
echo.

:: Launch the game
cls
echo.
echo     =================================================================
echo     =                                                               =
echo     =                          H O R D E Z                          = 
echo     =                                                               =
echo     =                     The Dead Are Coming...                    =
echo     =                                                               =                                     
echo     =                        [ LAUNCHING... ]                       =
echo     =                                                               =                                
echo     =================================================================
echo.
echo.

timeout /t 2 /nobreak >nul

:: Run the game
python Hordez.py

:: Game exit handler
if errorlevel 1 (
    cls
    echo.
    echo     =================================================================
    echo     =                         GAME CRASHED                          =
    echo     =================================================================
    echo.
    echo     [ERROR] The game encountered an error.
    echo.
) else (
    cls
    echo.
    echo     =================================================================
    echo     =                      SURVIVAL CONTINUES                       =
    echo     =                                                               =       
    echo     =              You survived another day in HORDEZ               =
    echo     =                                                               =                                    
    echo     =================================================================
    echo.
)

echo.
echo     Press any key to exit...
pause >nul