import subprocess
import webbrowser
from pathlib import Path
import sys

print("🚀 Run unit tests with coverage...")
result = subprocess.run(["coverage", "run", "-m", "pytest"])

# return code 0 = tests failed
if result.returncode != 0:
    print(f"❌ Unit tests failed (Code {result.returncode}).")
    sys.exit(result.returncode)

print("📊 Generating HTML report...")
subprocess.run(["coverage", "html"])

report_path = Path("htmlcov/index.html").resolve()
if report_path.exists():
    print("✨ Opening report in web browser !")
    webbrowser.open(report_path.as_uri())
else:
    print("❌ Error : HTML report not found !.")