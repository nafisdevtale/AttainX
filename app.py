"""Vercel entry point for Smart CO PO AttainX."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "obe-source.zip"
EXTRACT_ROOT = Path("/tmp/attainx-source")
APP_DIR = EXTRACT_ROOT / "obe-po-attainment-dashboard-github"
APP_FILE = APP_DIR / "app.py"

if not APP_FILE.is_file():
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE) as archive:
        archive.extractall(EXTRACT_ROOT)

if not APP_FILE.is_file():
    raise RuntimeError("AttainX source bundle is missing its app.py entry point.")

sys.path.insert(0, str(APP_DIR))
_spec = spec_from_file_location("_attainx_application", APP_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Unable to load the AttainX Flask application.")

_module = module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

app = _module.app
