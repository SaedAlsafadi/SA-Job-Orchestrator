import sys
import os
from pathlib import Path

# Insert local backend dir at the front of sys.path to mimic normal run
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

try:
    import app
except ImportError:
    print("[FAIL] Failed to import 'app' module.")
    sys.exit(1)

app_path = getattr(app, "__file__", "UNKNOWN")
print("=== AutoApply Environment Diagnostic ===")
print(f"Project Root: {project_root}")
print(f"Python Executable: {sys.executable}")
print(f"Application Module Path: {app_path}")

if "site-packages" in app_path or "dist-packages" in app_path:
    print("\n[CRITICAL ERROR] 'app' is being imported from a cached package installation!")
    print("This means changes to your local code will NOT be reflected.")
    print(r"Fix: Run `.venv\Scripts\pip.exe uninstall -y app autoapply`")
    sys.exit(1)
else:
    print("\n[SUCCESS] Environment is healthy! Importing from local working tree.")
    sys.exit(0)
