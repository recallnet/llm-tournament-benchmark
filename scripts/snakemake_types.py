"""Type stubs for Snakemake global objects."""

from pathlib import Path
from typing import Any, Dict, List, Union


class SnakemakeInput:
    """Snakemake input object with dynamic attributes."""

    def __getattr__(self, name: str) -> Union[str, Path, List[str]]:
        return ""


class SnakemakeOutput:
    """Snakemake output object with dynamic attributes."""

    def __getitem__(self, index: int) -> Union[str, Path]:
        return ""

    def __getattr__(self, name: str) -> Union[str, Path, List[str]]:
        return ""


class SnakemakeParams:
    """Snakemake params object with dynamic attributes."""

    def __getattr__(self, name: str) -> Any:
        return None


class SnakemakeConfig:
    """Snakemake config object."""

    def get(self, key: str, default: Any = None) -> Any:
        return default


class SnakemakeObject:
    """Main Snakemake object available in scripts."""

    input: SnakemakeInput
    output: SnakemakeOutput
    params: SnakemakeParams
    config: SnakemakeConfig
    threads: int
    resources: Dict[str, Any]

    def __init__(self) -> None:
        self.input = SnakemakeInput()
        self.output = SnakemakeOutput()
        self.params = SnakemakeParams()
        self.config = SnakemakeConfig()
        self.threads = 1
        self.resources = {}


# Global Snakemake object (injected by Snakemake at runtime)
snakemake: SnakemakeObject
