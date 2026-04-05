from pathlib import Path

# Compatibility namespace: allow imports like app.api.* to resolve from backend/app.
_BACKEND_APP_PATH = Path(__file__).resolve().parent.parent / "backend" / "app"
if _BACKEND_APP_PATH.exists():
	__path__.append(str(_BACKEND_APP_PATH))
