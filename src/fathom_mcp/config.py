"""Configuration management with Pydantic."""

import os
from pathlib import Path, PurePosixPath
from typing import Any, Literal

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

    engine: Literal["ugrep"] = Field(
        default="ugrep",
        description="Search engine to use (currently only ugrep supported, reserved for future engines)",
    )
    context_lines: int = Field(default=5, ge=0, le=50)
    max_results: int = Field(default=50, ge=1, le=500)
    max_file_size_mb: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=30, ge=5, le=300)


class ExcludeConfig(BaseModel):
    """File exclusion settings."""

    patterns: list[str] = Field(
        default_factory=lambda: [
            ".git/*",
            "__pycache__/*",
            "*.draft.*",
            "_archive/*",
        ]
    )
    hidden_files: bool = True


class LimitsConfig(BaseModel):
    """Performance limits."""

    max_concurrent_searches: int = Field(default=4, ge=1, le=16)
    max_document_read_chars: int = Field(default=100_000, ge=1000)


class PerformanceConfig(BaseModel):
    """Performance optimization settings."""

    # File indexing
    enable_indexing: bool = Field(
        default=False,
        description="Enable document indexing for faster searches",
    )
    index_update_strategy: Literal["auto", "manual", "scheduled"] = Field(
        default="auto",
        description="When to update the index",
    )
    index_formats: list[str] = Field(
        default_factory=lambda: [".pdf", ".md", ".txt"],
        description="File formats to include in index",
    )
    index_path: str = Field(
        default=".fkm_index",
        description="Index storage path (relative to knowledge root)",
    )
    rebuild_index_on_startup: bool = Field(
        default=False,
        description="Rebuild index when server starts",
    )

    # File watching
    enable_file_watching: bool = Field(
        default=False,
        description="Monitor file changes for automatic index updates",
    )

    # Caching
    enable_smart_cache: bool = Field(
        default=True,
        description="Enable file modification time tracking in cache",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache time-to-live in seconds",
    )
    cache_max_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum number of cached entries",
    )

    # Parallel PDF processing
    enable_parallel_pdf: bool = Field(
        default=True,
        description="Process PDF pages in parallel",
    )
    max_pdf_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum parallel workers for PDF processing",
    )


class SecurityConfig(BaseModel):
    """Security settings for filter commands and file access."""

    # Filter command security
    enable_shell_filters: bool = Field(
        default=True,
        description="Global toggle for shell filter execution",
    )
    filter_security_mode: Literal["whitelist", "blacklist", "disabled"] = Field(
        default="whitelist",
        description="Security mode for filter commands",
    )
    allowed_filter_commands: list[str] = Field(
        default_factory=lambda: [
            "pdftotext",
            "pdftotext % -",
            "pandoc",
            "antiword",
            "jq",
            "/usr/bin/pdftotext",
            "/usr/local/bin/pdftotext",
            "/opt/homebrew/bin/pdftotext",
            "/usr/bin/pandoc",
            "/usr/local/bin/pandoc",
            "/opt/homebrew/bin/pandoc",
            "/usr/bin/antiword",
            "/usr/local/bin/antiword",
            "/opt/homebrew/bin/antiword",
            "/usr/bin/jq",
            "/usr/local/bin/jq",
            "/opt/homebrew/bin/jq",
        ],
        description="Whitelist of allowed filter commands and executables",
    )
    blocked_filter_commands: list[str] = Field(
        default_factory=list,
        description="Blacklist of blocked filter commands (when using blacklist mode)",
    )
    sandbox_filters: bool = Field(
        default=True,
        description="Run filters in restricted environment (platform-dependent)",
    )
    filter_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for filter command execution",
    )
    max_filter_memory_mb: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="Memory limit for filter processes (not enforced on all platforms)",
    )

    # Path traversal protection
    restrict_to_knowledge_root: bool = Field(
        default=True,
        description="Prevent access to files outside knowledge root directory",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Allow following symbolic links",
    )


class HTTPLimitsConfig(BaseModel):
    """HTTP request/response limits and timeouts.

    These settings control resource usage and prevent DoS attacks.
    Adjust based on your deployment requirements.
    """

    max_request_body_size: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        ge=1024,  # min 1KB
        le=100 * 1024 * 1024,  # max 100MB
        description="Maximum request body size in bytes",
    )

    max_concurrent_connections: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum concurrent HTTP connections",
    )

    connection_timeout: int = Field(
        default=60,
        ge=5,
        le=300,
        description="Connection timeout in seconds",
    )

    read_timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Read timeout in seconds (for long-running operations)",
    )

    write_timeout: int = Field(
        default=60,
        ge=5,
        le=300,
        description="Write timeout in seconds",
    )

    keepalive_timeout: int = Field(
        default=5,
        ge=0,
        le=300,
        description="Keep-alive timeout in seconds",
    )


class TransportConfig(BaseModel):
    """Transport protocol configuration with production security.

    Configures the MCP server transport layer. Supports:
    - stdio: Standard input/output (default, for Claude Desktop)
    - streamable-http: Streamable HTTP protocol

    Attributes:
        type: Transport protocol type (stdio, streamable-http)
        host: Server host address (127.0.0.1 for local, 0.0.0.0 for Docker)
        port: Server port number (>= 1024 for non-root)
        base_path: Streamable HTTP endpoint path (default: /mcp)
        healthcheck_endpoint: Health check endpoint path (default: /_health)
        enable_cors: Enable CORS middleware (default: False)
        allowed_origins: CORS allowed origins (never use ["*"] in production!)
        allowed_methods: CORS allowed HTTP methods
        allowed_headers: CORS allowed headers
        max_age: CORS preflight cache duration in seconds
        limits: HTTP request/response limits
        log_level: Uvicorn log level
        structured_logging: Use JSON logs (recommended for production)
        access_log: Enable HTTP access log
        reload: Auto-reload for development (disable in production)

    Security:
        - CORS wildcard (*) is BLOCKED in production environment
        - Origins must use http:// or https:// protocol
        - Port must be >= 1024 for non-root users
        - Default port 8765 avoids common conflicts
        - Structured logging recommended for production

    Examples:
        Stdio transport (default):
            >>> config = TransportConfig()
            >>> config.type
            'stdio'

        HTTP transport for Docker:
            >>> config = TransportConfig(
            ...     type="streamable-http",
            ...     host="0.0.0.0",
            ...     port=8765,
            ...     enable_cors=True,
            ...     allowed_origins=["https://app.example.com"],
            ...     structured_logging=True,
            ... )

        From environment variables:
            >>> os.environ["FMCP_TRANSPORT__TYPE"] = "streamable-http"
            >>> os.environ["FMCP_TRANSPORT__PORT"] = "8765"
            >>> config = Config()
            >>> config.transport.type
            'streamable-http'

    Environment Variables:
        All fields can be overridden via FMCP_TRANSPORT__* variables:
        - FMCP_TRANSPORT__TYPE=streamable-http
        - FMCP_TRANSPORT__HOST=0.0.0.0
        - FMCP_TRANSPORT__PORT=8765
        - FMCP_TRANSPORT__ENABLE_CORS=true
        - FMCP_TRANSPORT__ALLOWED_ORIGINS='["https://app.example.com"]'

    See Also:
        - HTTPLimitsConfig: HTTP-specific limits and timeouts
        - Config: Main configuration class
        - create_http_app: Creates Starlette app from this config
    """

    # Transport type
    type: Literal["stdio", "streamable-http"] = Field(
        default="stdio",
        description="Transport protocol type",
    )

    # HTTP settings (ignored for stdio)
    host: str = Field(
        default="127.0.0.1",
        description="Server host address (use 0.0.0.0 for Docker)",
    )

    port: int = Field(
        default=8765,
        ge=1024,
        le=65535,
        description="Server port number (must be >= 1024 for non-root)",
    )

    # Endpoints
    base_path: str = Field(
        default="/mcp",
        description="Streamable HTTP endpoint path",
    )

    healthcheck_endpoint: str = Field(
        default="/_health",
        description="Health check endpoint path",
    )

    # CORS Security (CRITICAL #7)
    enable_cors: bool = Field(
        default=False,
        description="Enable CORS middleware (disabled by default for security)",
    )

    allowed_origins: list[str] = Field(
        default_factory=list,
        description="CORS allowed origins (never use ['*'] in production!)",
    )

    allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "OPTIONS"],
        description="CORS allowed HTTP methods",
    )

    allowed_headers: list[str] = Field(
        default_factory=lambda: ["Content-Type"],
        description="CORS allowed headers",
    )

    max_age: int = Field(
        default=600,
        ge=0,
        le=86400,
        description="CORS preflight cache duration in seconds",
    )

    limits: HTTPLimitsConfig = Field(
        default_factory=HTTPLimitsConfig,
        description="HTTP request/response limits",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Uvicorn log level",
    )

    structured_logging: bool = Field(
        default=False,
        description="Use structured JSON logging (recommended for production)",
    )

    access_log: bool = Field(
        default=True,
        description="Enable HTTP access log",
    )

    reload: bool = Field(
        default=False,
        description="Auto-reload for development (disable in production)",
    )

    # Validators
    @field_validator("allowed_origins")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        """Validate CORS origins with strict security checks.

        CRITICAL #7: Blocks wildcard (*) in production environment.
        """
        import logging

        logger = logging.getLogger(__name__)

        # Check for wildcard
        if "*" in v:
            # Only allow wildcard in development
            env = os.getenv("ENVIRONMENT", "production").lower()
            if env == "production":
                raise ValueError(
                    "Wildcard CORS origin (*) is FORBIDDEN in production. "
                    "Set specific origins in transport.allowed_origins. "
                    "Example: allowed_origins: ['https://app.example.com']"
                )
            logger.warning(
                "⚠️  CORS allows ALL origins (*). "
                "This is ONLY safe for development. "
                "NEVER use in production!"
            )

        # Validate origin format
        for origin in v:
            if origin == "*":
                continue

            # Must be valid URL
            if not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid CORS origin '{origin}': must start with http:// or https://. "
                    f"Example: 'https://app.example.com'"
                )

            # Warn about http:// in production
            if origin.startswith("http://") and "localhost" not in origin:
                env = os.getenv("ENVIRONMENT", "production").lower()
                if env == "production":
                    logger.warning(
                        f"⚠️  CORS origin '{origin}' uses insecure HTTP. "
                        f"Consider using HTTPS in production."
                    )

        return v

    @field_validator("allowed_methods")
    @classmethod
    def validate_allowed_methods(cls, v: list[str]) -> list[str]:
        """Validate HTTP methods."""
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}

        for method in v:
            if method.upper() not in valid_methods:
                raise ValueError(
                    f"Invalid HTTP method: {method}. Valid methods: {', '.join(valid_methods)}"
                )

        return [m.upper() for m in v]

    @field_validator("base_path", "healthcheck_endpoint")
    @classmethod
    def validate_url_path(cls, v: str) -> str:
        """Ensure URL paths use forward slashes (cross-platform).

        Converts to POSIX paths even on Windows.
        This ensures HTTP URL paths always use forward slashes,
        regardless of the platform.

        Args:
            v: URL path to validate

        Returns:
            Normalized POSIX path with forward slashes

        Examples:
            >>> TransportConfig.validate_url_path("\\mcp")
            '/mcp'
            >>> TransportConfig.validate_url_path("mcp")
            '/mcp'
            >>> TransportConfig.validate_url_path("/_health")
            '/_health'
        """
        # Convert to POSIX path (forward slashes)
        posix_path = PurePosixPath(v)

        # Ensure starts with /
        path_str = str(posix_path)
        if not path_str.startswith("/"):
            return f"/{path_str}"

        return path_str


class ServerConfig(BaseModel):
    """Server metadata."""

    name: str = "fathom-mcp"
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
        env_prefix="FMCP_",
        env_nested_delimiter="__",
    )

    knowledge: KnowledgeConfig
    server: ServerConfig = Field(default_factory=ServerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    exclude: ExcludeConfig = Field(default_factory=ExcludeConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    transport: TransportConfig = Field(
        default_factory=TransportConfig,
        description="Transport protocol configuration",
    )
    formats: dict[str, FormatConfig] = Field(
        default_factory=lambda: {
            # === Existing formats ===
            "pdf": FormatConfig(
                extensions=[".pdf"],
                filter="pdftotext % -",
                enabled=True,  # Already working
            ),
            "markdown": FormatConfig(
                extensions=[".md", ".markdown"],
                filter=None,
                enabled=True,
            ),
            "text": FormatConfig(
                extensions=[".txt", ".rst"],
                filter=None,
                enabled=True,
            ),
            # === NEW: Tier 1 - Office Documents ===
            "word_doc": FormatConfig(
                extensions=[".doc"],
                filter="antiword -t -w 0 %",
                enabled=False,  # Requires antiword
            ),
            "word_docx": FormatConfig(
                extensions=[".docx"],
                filter="pandoc --wrap=preserve -f docx -t plain % -o -",
                enabled=False,  # Requires pandoc
            ),
            "opendocument": FormatConfig(
                extensions=[".odt"],
                filter="pandoc --wrap=preserve -f odt -t plain % -o -",
                enabled=False,
            ),
            "epub": FormatConfig(
                extensions=[".epub"],
                filter="pandoc --wrap=preserve -f epub -t plain % -o -",
                enabled=False,
            ),
            "html": FormatConfig(
                extensions=[".html", ".htm"],
                filter="pandoc --wrap=preserve -f html -t plain % -o -",
                enabled=False,
            ),
            # === NEW: Tier 2 - Additional Formats ===
            "rtf": FormatConfig(
                extensions=[".rtf"],
                filter="pandoc --wrap=preserve -f rtf -t plain % -o -",
                enabled=False,
            ),
            "csv": FormatConfig(
                extensions=[".csv"],
                filter=None,  # Direct search
                enabled=True,  # No dependencies
            ),
            "json": FormatConfig(
                extensions=[".json"],
                filter="jq -r '.'",
                enabled=False,  # Requires jq
            ),
            "xml": FormatConfig(
                extensions=[".xml"],
                filter="pandoc --wrap=preserve -f html -t plain % -o -",
                enabled=False,
            ),
        }
    )

    @property
    def supported_extensions(self) -> set[str]:
        """Get all enabled file extensions."""
        exts = set()
        for fmt in self.formats.values():
            if fmt.enabled:
                exts.update(fmt.extensions)
        return exts

    def get_filter_for_extension(self, ext: str) -> str | None:
        """Get filter command for a file extension.

        Args:
            ext: File extension (with or without leading dot)

        Returns:
            Filter command string, or None if no filter needed
        """
        ext = ext.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        for fmt_config in self.formats.values():
            if fmt_config.enabled and ext in fmt_config.extensions:
                return fmt_config.filter

        return None

    def needs_document_filters(self) -> bool:
        """Check if any enabled formats require filter commands.

        Returns:
            True if at least one enabled format has a filter command
        """
        return any(fmt.enabled and fmt.filter is not None for fmt in self.formats.values())

    def prepare_filter_for_stdin(self, filter_cmd: str) -> str:
        """Convert ugrep filter syntax (%) to stdin-compatible syntax (-).

        Args:
            filter_cmd: Filter command with % placeholder

        Returns:
            Filter command with stdin syntax
        """
        # Only replace % when it's used as a filename placeholder
        # ugrep uses % as the filename placeholder
        if " % " in filter_cmd:
            return filter_cmd.replace(" % ", " - ")
        elif filter_cmd.endswith(" %"):
            return filter_cmd[:-2] + " -"
        # If no %, assume stdin already
        return filter_cmd


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
    config_data: dict[str, Any] = {}

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
