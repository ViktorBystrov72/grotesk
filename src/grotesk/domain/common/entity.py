from abc import ABC
from dataclasses import dataclass


@dataclass(eq=False)
class Entity(ABC):
    """Base class for entities."""
