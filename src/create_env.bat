@echo off
REM Windows cmd setup — same role as create_env.sh (venv in current directory).
REM
REM   cd src\tests\integration
REM   ..\..\create_env.bat
REM
REM Activate later (cmd):
REM   venv\Scripts\activate.bat

setlocal EnableExtensions

echo ==^> Creating venv in current directory: %CD%

if exist "venv" (
    echo Removing existing venv...
    rmdir /s /q "venv"
)

REM --- resolve Python (prefer 3.9) ---
py -3.9 -c "import sys" >nul 2>&1
if not errorlevel 1 goto use_py39

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    echo WARNING: Python 3.9 preferred for Pi parity; using py -3.
    goto use_py3
)

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto use_python

echo.
echo ERROR: Python 3.9+ not found.
echo Install from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH" and the py launcher, then reopen cmd.
echo.
echo Test:  py -3.9 --version
echo        python --version
exit /b 1

:use_py39
echo ==^> Using: py -3.9
py -3.9 -m venv venv --system-site-packages
if errorlevel 1 goto venv_failed
goto activate

:use_py3
echo ==^> Using: py -3
py -3 -m venv venv --system-site-packages
if errorlevel 1 goto venv_failed
goto activate

:use_python
echo ==^> Using: python
python -m venv venv --system-site-packages
if errorlevel 1 goto venv_failed
goto activate

:activate
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: venv\Scripts\activate.bat not found after venv create.
    exit /b 1
)

echo ==^> Activating venv...
call "venv\Scripts\activate.bat"

echo ==^> Python version:
python --version

echo ==^> Upgrading pip...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto pip_failed

echo ==^> Installing dependencies...
python -m pip install "numpy<2"
if errorlevel 1 goto pip_failed
python -m pip install opencv-python==4.8.1.78
if errorlevel 1 goto pip_failed
python -m pip install pillow==11.3.0
if errorlevel 1 goto pip_failed
python -m pip install scikit-learn joblib
if errorlevel 1 goto pip_failed
REM greenlet 3.2+ has no cp39 Windows wheel; SQLAlchemy would try to compile it.
python -m pip install greenlet==3.1.1
if errorlevel 1 goto pip_failed
python -m pip install sqlmodel==0.0.34
if errorlevel 1 goto pip_failed
python -m pip install alembic==1.15.2
if errorlevel 1 goto pip_failed
REM cp39 wheels; used by TP-33/TP-39 Supabase Postgres (SQLAlchemy).
python -m pip install psycopg2-binary==2.9.10
if errorlevel 1 goto pip_failed
REM Pydantic 2 on Python 3.9 cannot evaluate `int | None` without this.
python -m pip install eval_type_backport
if errorlevel 1 goto pip_failed
python -m pip install python-dotenv==1.0.1
if errorlevel 1 goto pip_failed
python -m pip install pydantic-settings==2.5.2
if errorlevel 1 goto pip_failed
REM FastAPI ingest (TP-34/35); cp39 wheels
python -m pip install fastapi==0.115.8
if errorlevel 1 goto pip_failed
python -m pip install uvicorn==0.32.1
if errorlevel 1 goto pip_failed
python -m pip install httpx==0.27.2
python -m pip install boto3==1.35.99
if errorlevel 1 goto pip_failed

echo ==^> Installing tflite-runtime...
python -m pip install --extra-index-url https://google-coral.github.io/py-repo/ tflite-runtime==2.5.0.post1
if errorlevel 1 (
    echo.
    echo WARNING: tflite-runtime install failed ^(expected on Windows; Coral wheels are Linux/Pi^).
    echo For AT-3.4 clip replay on this PC, after activate run:
    echo   pip install tensorflow
    echo.
)

echo.
echo ==^> Setup complete!
echo.
echo To activate later in cmd, run:
echo   venv\Scripts\activate.bat
exit /b 0

:venv_failed
echo.
echo ERROR: Failed to create venv.
exit /b 1

:pip_failed
echo.
echo ERROR: pip install failed.
exit /b 1
