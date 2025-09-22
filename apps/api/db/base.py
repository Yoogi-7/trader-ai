"""
Globalny Base dla modeli + automatyczne wczytywanie modułów z apps.api.models.*

Uwaga:
- Każdy model powinien dziedziczyć z `Base` importowanego STĄD:
  `from apps.api.db.base import Base`
- Nie twórz własnych `declarative_base()` w modelach – to rozdziela metadane.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from sqlalchemy.orm import declarative_base

# Wspólny Base dla całej aplikacji
Base = declarative_base()


def _iter_submodules(package_name: str) -> Iterable[str]:
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        return
    for module_info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        yield module_info.name


def load_all_model_modules() -> None:
    """
    Importuje wszystkie moduły z `apps.api.models.*`, aby klasy modeli
    zostały zarejestrowane w Base.metadata przed migracjami.
    """
    for mod_name in _iter_submodules("apps.api.models"):
        importlib.import_module(mod_name)


# Załaduj modele od razu przy imporcie base.py
try:
    load_all_model_modules()
except ModuleNotFoundError:
    # Jeśli paczka jeszcze nie istnieje – to nie blokuje startu,
    # ale warto ją utworzyć (patrz apps/api/models/__init__.py).
    pass
