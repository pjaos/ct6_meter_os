REM python -m nsist --no-makensis installer.cfg
git rev-parse --short HEAD > ../assets/git_hash.txt
python3 -m nsist installer.cfg
