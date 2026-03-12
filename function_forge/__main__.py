"""Enables `python -m function_forge` — launches the Streamlit app."""
import subprocess
import sys
import os

here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app  = os.path.join(here, "streamlit_app.py")
subprocess.run(["streamlit", "run", app], check=True)
