cd ~/Downloads/HandPilot_2.1.0-2
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/download_model.py
python tools/doctor.py
python main.py

USE THIS COMMAND PROMPT FOR RUNNING!!
