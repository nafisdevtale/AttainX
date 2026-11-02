"""Vercel entry point for Smart CO PO AttainX."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
BUNDLE_CANDIDATES = (
    ROOT / "obe-source.zip",
    ROOT / "obe-source (1).zip",
)
BUNDLE = next((path for path in BUNDLE_CANDIDATES if path.is_file()), None)

EXTRACT_ROOT = Path("/tmp/attainx-source")
APP_DIR = EXTRACT_ROOT / "obe-po-attainment-dashboard-github"
APP_FILE = APP_DIR / "app.py"

if not APP_FILE.is_file():
    if BUNDLE is None:
        expected = ", ".join(path.name for path in BUNDLE_CANDIDATES)
        raise FileNotFoundError(
            f"AttainX source archive not found. Expected one of: {expected}"
        )
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


def _uncapped_target_attainment_percentage(final_score, target_score):
    """Calculate achievement relative to the faculty-entered PO mapping target."""
    if _module.pd.isna(target_score) or float(target_score) <= 0:
        return 0.0
    if _module.pd.isna(final_score):
        return 0.0
    return (float(final_score) / float(target_score)) * 100.0


# The weighted 80:20 contribution calculation remains in the application.
# Only remove the 100% display cap from the target-attainment percentage.
_module.target_attainment_percentage = _uncapped_target_attainment_percentage

# Keep the dashboard's formula/help text consistent with the uncapped result.
dashboard_template = APP_DIR / "templates" / "dashboard.html"
if dashboard_template.is_file():
    template_text = dashboard_template.read_text(encoding="utf-8")
    template_text = template_text.replace(
        "Formula: min((Final PO / Target Mapping) × 100, 100%). Display is capped at 100%.",
        "Formula: (Final PO Attainment / PO Mapping) × 100. Values above 100% are valid when attainment exceeds the mapped target."
    )
    template_text = template_text.replace(
        "Target achievement for {{ row.po }}; capped at 100%",
        "Final PO Attainment / PO Mapping × 100 for {{ row.po }}; not capped"
    )
    dashboard_template.write_text(template_text, encoding="utf-8")

app = _module.app
