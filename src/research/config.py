"""Central config.

Import this module BEFORE cognee anywhere, so .env is loaded first.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# src/research/config.py -> repo root is three levels up
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"

# Cognee storage must live on a SHORT path. Under site-packages the LanceDB
# file paths exceed the Windows 260 character limit and cognify fails.
COGNEE_ROOT = Path(os.getenv("COGNEE_ROOT", "D:/cg"))

# One Cognee dataset per workspace. Sprint 1 uses a single default workspace.
DEFAULT_WORKSPACE = os.getenv("WORKSPACE", "ws_default")

# Pages with fewer characters than this after extraction are skipped.
# Chosen arbitrarily for now, record any change in PROCESS_LOG.md.
MIN_PAGE_CHARS = 20