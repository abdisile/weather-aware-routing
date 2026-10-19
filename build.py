"""Build the React app into the folder Django serves on Vercel."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DEST = ROOT / "backend" / "spa"


def main() -> None:
    subprocess.check_call(["npm", "ci"], cwd=FRONTEND)
    subprocess.check_call(["npm", "run", "build"], cwd=FRONTEND)
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(FRONTEND / "dist", DEST)


if __name__ == "__main__":
    main()
