"""Configuration management with Pydantic."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FormatConfig(BaseModel):
    """Document format configuration."""

    enabled: bool = True
    filter: str | None = None  # None = read directly, str = shell command
    extensions: list[str]


class SearchConfig(BaseModel):
    """Search engine settings."""

    engine: Literal["ugrep"] = "ugrep"
    context_lines: int = Field(default=5, ge=0, le=50)
    max_results: int = Field(default=50, ge=1, le=500)
    max_file_size_mb: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class ExcludeConfig(BaseModel):
    """File exclusion settings."""

    patterns: list[str] = Field(default_factory=lambda: [
        ".git/*",
        "__pycache__/*",
        "*.draft.*",
        "_archive/*",
    ])
    hidden_files: bool = True


class LimitsConfig(BaseModel):
    """Performance limits."""

    max_concurrent_searches: int = Field(default=4, ge=1, le=16)
    max_document_read_chars: int = Field(default=100_000, ge=1000)


class ServerConfig(BaseModel):
    """Server metadata."""

    name: str = "file-knowledge-mcp"
    version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class KnowledgeConfig(BaseModel):
    """Knowledge base root configuration."""

    root: Path

    @field_validator("root")
    @classmethod
    def validate_root_exists(cls, v: Path) -> Path:
        path = Path(v).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Knowledge root does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Knowledge root is not a directory: {path}")
        return path


class Config(BaseSettings):
    """Main configuration."""

    model_config = SettingsConfigDict(
        env_prefix="FKM_",
        env_nested_delimiter="__",
    )

    knowledge: KnowledgeConfig
    server: ServerConfig = Field(default_factory=ServerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    exclude: ExcludeConfig = Field(default_factory=ExcludeConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    formats: dict[str, FormatConfig] = Field(default_factory=lambda: {
        "pdf": FormatConfig(
            extensions=[".pdf"],
            filter="pdftotext - -",
        ),
        "markdown": FormatConfig(
            extensions=[".md", ".markdown"],
            filter=None,
        ),
        "text": FormatConfig(
            extensions=[".txt", ".rst"],
            filter=None,
        ),
    })

    @property
    def supported_extensions(self) -> set[str]:
        """Get all enabled file extensions."""
        exts = set()
        for fmt in self.formats.values():
            if fmt.enabled:
                exts.update(fmt.extensions)
        return exts

    def get_filter_for_extension(self, ext: str) -> str | None:
        """Get filter command for file extension."""
        for fmt in self.formats.values():
            if fmt.enabled and ext.lower() in fmt.extensions:
                return fmt.filter
        return None


class ConfigError(Exception):
    """Configuration loading error."""
    pass


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file or defaults.

    Args:
        config_path: Path to config.yaml. If None, tries ./config.yaml

    Returns:
        Validated Config instance

    Raises:
        ConfigError: If configuration is invalid
    """
    config_data: dict = {}

    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        config_data = yaml.safe_load(path.read_text()) or {}
    else:
        # Try default locations
        for default in [Path("./config.yaml"), Path("./config.yml")]:
            if default.exists():
                config_data = yaml.safe_load(default.read_text()) or {}
                break

    try:
        return Config(**config_data)
    except Exception as e:
        raise ConfigError(f"Invalid configuration: {e}") from e
