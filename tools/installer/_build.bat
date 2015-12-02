set PATH=%PATH%;C:\Python27\

set GI_TYPELIB_PATH=%~dp0\_build_env_installer\deps\lib\girepository-1.0
set PATH=%PATH%;%~dp0\_build_env_installer\deps;

python -m PyInstaller --clean --distpath _dist --workpath _build --paths %~dp0\_inst\usr\lib\exaile exaile.spec
