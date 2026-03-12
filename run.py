"""Launch Function Forge (Streamlit web app)."""
import subprocess
import sys
import os

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    app  = os.path.join(here, "streamlit_app.py")
    subprocess.run(["streamlit", "run", app], check=True)
