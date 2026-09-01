import os
import sys

# Workaround for importlib.metadata missing package info in PyInstaller
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata

_orig_version = importlib_metadata.version

def _mock_version(package_name):
    if package_name == "streamlit":
        return "1.32.0"
    return _orig_version(package_name)

importlib_metadata.version = _mock_version

import streamlit.web.cli as stcli
from streamlit.runtime import exists  # Import the runtime checker

if __name__ == "__main__":
    # Check if a Streamlit server is already running (e.g., during cloud deployment)
    if not exists():
        if getattr(sys, "frozen", False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        script_path = os.path.join(base_dir, "app.py")

        sys.argv = [
            "streamlit",
            "run",
            script_path,
            "--global.developmentMode=false",
        ]
        sys.exit(stcli.main())