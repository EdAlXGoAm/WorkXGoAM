@echo off
REM **********************************************
REM Script to compile WorkXFlaskServer, copy the executable
REM and run tauri build using relative paths.
REM **********************************************

REM 1. Compile WorkXFlaskServer using PyInstaller
pushd "flask_server"
echo Compiling WorkXFlaskServer with PyInstaller...
pyinstaller "WorkXFlaskServer.spec"
if errorlevel 1 (
    echo An error occurred during WorkXFlaskServer compilation.
    popd
    pause
    exit /b 1
)
popd
echo WorkXFlaskServer compilation completed.
echo.

REM 2. Copy WorkXFlaskServer.exe after removing destination file (if exists)
set "SOURCE_EXE=flask_server\dist\WorkXFlaskServer.exe"
set "DEST_EXE1=src-tauri\WorkXFlaskServer.exe"
set "DEST_EXE2=src-tauri\target\debug\WorkXFlaskServer.exe"
set "DEST_EXE3=src-tauri\target\release\WorkXFlaskServer.exe"

echo Removing file %DEST_EXE1% if exists...
if exist "%DEST_EXE1%" del /f /q "%DEST_EXE1%"
echo Copying WorkXFlaskServer.exe to %DEST_EXE1%...
copy /Y "%SOURCE_EXE%" "%DEST_EXE1%"
echo.

echo Removing file %DEST_EXE2% if exists...
if exist "%DEST_EXE2%" del /f /q "%DEST_EXE2%"
echo Copying WorkXFlaskServer.exe to %DEST_EXE2%...
copy /Y "%SOURCE_EXE%" "%DEST_EXE2%"
echo.

echo Removing file %DEST_EXE3% if exists...
if exist "%DEST_EXE3%" del /f /q "%DEST_EXE3%"
echo Copying WorkXFlaskServer.exe to %DEST_EXE3%...
copy /Y "%SOURCE_EXE%" "%DEST_EXE3%"
echo.
echo WorkXFlaskServer.exe copy completed.
echo.

REM 3. Copy complete flask_server folder for development
set "SOURCE_DIR_FLASK=flask_server"
set "DEST_FLASK1=src-tauri\flask_server"
set "DEST_FLASK2=src-tauri\target\debug\flask_server"
set "DEST_FLASK3=src-tauri\target\release\flask_server"

echo Removing folder %DEST_FLASK1% if exists...
if exist "%DEST_FLASK1%" rd /s /q "%DEST_FLASK1%"
echo Copying flask_server folder to %DEST_FLASK1%...
xcopy "%SOURCE_DIR_FLASK%\*.py" "%DEST_FLASK1%\" /I /Y
echo.

echo Removing folder %DEST_FLASK2% if exists...
if exist "%DEST_FLASK2%" rd /s /q "%DEST_FLASK2%"
echo Copying flask_server folder to %DEST_FLASK2%...
xcopy "%SOURCE_DIR_FLASK%\*.py" "%DEST_FLASK2%\" /I /Y
echo.

echo Removing folder %DEST_FLASK3% if exists...
if exist "%DEST_FLASK3%" rd /s /q "%DEST_FLASK3%"
echo Copying flask_server folder to %DEST_FLASK3%...
xcopy "%SOURCE_DIR_FLASK%\*.py" "%DEST_FLASK3%\" /I /Y
echo.
echo flask_server folder copy completed.
echo.

REM 4. Run "npm run tauri build" in current directory
echo Running "npm run tauri build"...

REM 5. Open File Explorer in application location
set "APP_DIR=src-tauri\target\release\bundle\nsis"
echo Opening Explorer in %APP_DIR%...
if exist "%APP_DIR%" (
    start explorer.exe "%APP_DIR%"
) else (
    echo Folder %APP_DIR% not found.
)

npm run tauri build
if errorlevel 1 (
    echo An error occurred during Tauri compilation.
    pause
    exit /b 1
)
echo Tauri compilation completed.

echo Process completed.
pause