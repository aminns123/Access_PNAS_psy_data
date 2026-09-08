from abc import ABC, abstractmethod
from pathlib import Path


class DatasetError(ValueError):
    """A readable dataset/configuration error."""


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise DatasetError(f"Source path escapes dataset root: {relative}")
    return path


class DatasetAdapter(ABC):
    @abstractmethod
    def load(self, root): ...

    @abstractmethod
    def levels(self): ...

    @abstractmethod
    def get_values(self, level, current_filters): ...

    @abstractmethod
    def get_plot(self, level, current_filters): ...

    def get_metadata(self, current_filters):
        return dict(current_filters)
