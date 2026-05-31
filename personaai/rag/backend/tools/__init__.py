import importlib
from typing import Any

_module_lookup = {
    "GoogleNews": "tools.news",
    "TavilySearch": "tools.tavily",
    "DocumentRetrievalChain": "tools.retrieval",
}

from backend.tools.news import GoogleNews
from backend.tools.tavily import TavilySearch
from backend.tools.retrieval import DocumentRetrievalChain

def __getattr__(name: str) -> Any:
    if name in _module_lookup:
        module = importlib.import_module(_module_lookup[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "GoogleNews",
    "TavilySearch",
    "DocumentRetrievalChain",
]
