from importlib import import_module

_backend_main = import_module("backend.app.main")
app = _backend_main.app
create_app = _backend_main.create_app

__all__ = ["app", "create_app"]
