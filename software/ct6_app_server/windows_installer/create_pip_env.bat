REM SET PIPENV_VENV_IN_PROJECT=enabled
python3 -m pipenv --rm
REM Create the .venv dir so that pipenv notices it's presence
REM mkdir .venv
python3 -m pipenv install --verbose
REM Fixup error in the pyreadline module used by rshell
python3 -m pipenv run pip uninstall -y pyreadline
python3 -m pipenv run pip install pyreadline3
