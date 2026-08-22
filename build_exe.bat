@echo off
rem Compatibility wrapper. build_release.bat is the canonical builder.
call "%~dp0build_release.bat"
exit /b %ERRORLEVEL%
