# class_icons.py

from PyQt6.QtGui import QIcon
import functional.resources
from functional.heroicons_map import HEROICONS

ICON_MAP = HEROICONS
DEFAULT_ICON_NAME = list(ICON_MAP.keys())[0]
class Icons:

    _paths = HEROICONS

    _cache = {}

    @classmethod
    def icon(cls, name: str) -> QIcon:
        if name not in cls._cache:
            cls._cache[name] = QIcon(cls._paths.get(name,DEFAULT_ICON_NAME))
        return cls._cache[name]
    
    @classmethod
    def resource(cls, name: str) -> str:
        return cls._paths.get(name)
        