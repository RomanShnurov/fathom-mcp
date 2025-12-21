# Configuration Reference

Complete reference for all configuration options.

---

## Configuration Loading

Configuration is loaded in this priority order:

1. **CLI arguments** (`--root`, `--log-level`)
2. **Environment variables** (prefix `FKM_`)
3. **Config file** (`config.yaml`)
4. **Defaults**

### Environment Variables

All config options can be set via environment variables:

```bash
# Nested keys use double underscore
FKM_KNOWLEDGE__ROOT=/data/docs
FKM_SERVER__LOG_LEVEL=DEBUG
FKM_SEARCH__MAX_RESULTS=100
FKM_SYNC__ENABLED=true
```

---

## Minimal Configuration

```yaml
# Minimum required config
knowledge:
  root: "./documents"
```

This is sufficient to start the server. All other options have sensible defaults.

---

## Full Configuration

```yaml
# === REQUIRED ===

knowledge:
  root: "./documents"        # Path to documents (required)
                             # Can be relative or absolute


# === SERVER ===

server:
  name: "file-knowledge-mcp" # Server name (shown in MCP clients)
  version: "0.1.0"           # Server version
  log_level: "INFO"          # DEBUG | INFO | WARNING | ERROR


# === DOCUMENT FORMATS ===

formats:
  pdf:
    enabled: true
    filter: "pdftotext - -"  # Shell command for text extraction
    extensions:              # File extensions for this format
      - ".pdf"

  markdown:
    enabled: true
    filter: null             # null = read file directly
    extensions:
      - ".md"
      - ".markdown"

  text:
    enabled: true
    filter: null
    extensions:
      - ".txt"
      - ".rst"

  docx:
    enabled: false           # Disabled by default (needs pandoc)
    filter: "pandoc -f docx -t plain"
    extensions:
      - ".docx"
      - ".doc"


# === SEARCH ===

search:
  engine: "ugrep"            # Search engine (currently only ugrep)
  context_lines: 5           # Lines of context around matches (0-50)
  max_results: 50            # Max results per search (1-500)
  max_file_size_mb: 100      # Skip files larger than this
  timeout_seconds: 30        # Search timeout (5-300)


# === EXCLUSIONS ===

exclude:
  patterns:                  # Glob patterns to ignore
    - ".git/*"
    - "__pycache__/*"
    - "*.draft.*"
    - "_archive/*"
    - "node_modules/*"
  hidden_files: true         # Ignore dotfiles


# === LIMITS ===

limits:
  max_concurrent_searches: 4      # Parallel ugrep processes (1-16)
  max_document_read_chars: 100000 # Max chars when reading document


# === CLOUD SYNC (OPTIONAL) ===

sync:
  enabled: false             # Enable sync features

  remotes:
    # Example: Google Drive
    gdrive:
      rclone_remote: "gdrive:Knowledge"  # rclone remote:path
      local_path: ""                     # Local subdir ("" = root)
      auto_sync: false                   # Sync on startup
      interval_minutes: 0                # Auto-sync interval (0 = manual)

    # Example: Dropbox for specific collection
    dropbox-games:
      rclone_remote: "dropbox:BoardGames/Rules"
      local_path: "games"                # Sync to knowledge/games/
      auto_sync: true
      interval_minutes: 30

    # Example: S3
    s3-backup:
      rclone_remote: "s3:my-bucket/docs"
      local_path: ""
      auto_sync: false
      interval_minutes: 60
```

---

## Configuration Options

### knowledge

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `root` | string | Yes | - | Path to documents directory |

### server

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `name` | string | No | `file-knowledge-mcp` | Server name |
| `version` | string | No | `0.1.0` | Server version |
| `log_level` | enum | No | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |

### formats

Each format is a key with these options:

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `enabled` | bool | No | `true` | Enable this format |
| `filter` | string/null | No | - | Shell command for text extraction |
| `extensions` | list[string] | Yes | - | File extensions |

**Filter command:**
- Receives file content on stdin
- Must output plain text on stdout
- `null` means read file directly (for text files)

**Examples:**
```yaml
# PDF using pdftotext
pdf:
  filter: "pdftotext - -"

# DOCX using pandoc
docx:
  filter: "pandoc -f docx -t plain"

# EPUB using pandoc
epub:
  filter: "pandoc -f epub -t plain"
  extensions: [".epub"]

# Custom script
custom:
  filter: "/path/to/extract.sh"
  extensions: [".xyz"]
```

### search

| Option | Type | Required | Default | Range | Description |
|--------|------|----------|---------|-------|-------------|
| `engine` | enum | No | `ugrep` | ugrep | Search engine |
| `context_lines` | int | No | `5` | 0-50 | Context lines |
| `max_results` | int | No | `50` | 1-500 | Max results |
| `max_file_size_mb` | int | No | `100` | 1+ | Skip large files |
| `timeout_seconds` | int | No | `30` | 5-300 | Timeout |

### exclude

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `patterns` | list[string] | No | (see below) | Glob patterns |
| `hidden_files` | bool | No | `true` | Ignore dotfiles |

**Default exclude patterns:**
```yaml
patterns:
  - ".git/*"
  - "__pycache__/*"
  - "*.draft.*"
  - "_archive/*"
```

### limits

| Option | Type | Required | Default | Range | Description |
|--------|------|----------|---------|-------|-------------|
| `max_concurrent_searches` | int | No | `4` | 1-16 | Parallel searches |
| `max_document_read_chars` | int | No | `100000` | 1000+ | Max read chars |

### sync

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `enabled` | bool | No | `false` | Enable sync features |
| `remotes` | dict | No | `{}` | Remote configurations |

**Remote configuration:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `rclone_remote` | string | Yes | - | rclone remote:path |
| `local_path` | string | No | `""` | Local subdirectory |
| `auto_sync` | bool | No | `false` | Sync on startup |
| `interval_minutes` | int | No | `0` | Auto-sync interval |

---

## Example Configurations

### Simple Local Setup

```yaml
knowledge:
  root: "~/Documents/Knowledge"

search:
  context_lines: 10
```

### Production Server

```yaml
knowledge:
  root: "/data/knowledge"

server:
  log_level: "WARNING"

search:
  max_results: 100
  timeout_seconds: 60

limits:
  max_concurrent_searches: 8

exclude:
  patterns:
    - ".git/*"
    - "*.bak"
    - "temp/*"
```

### With Cloud Sync

```yaml
knowledge:
  root: "/data/knowledge"

sync:
  enabled: true
  remotes:
    gdrive:
      rclone_remote: "gdrive:SharedKnowledge"
      auto_sync: true
      interval_minutes: 15
```

### Multi-Format Support

```yaml
knowledge:
  root: "./docs"

formats:
  pdf:
    enabled: true
    filter: "pdftotext - -"
    extensions: [".pdf"]

  docx:
    enabled: true
    filter: "pandoc -f docx -t plain"
    extensions: [".docx", ".doc"]

  markdown:
    enabled: true
    filter: null
    extensions: [".md", ".mdx"]

  html:
    enabled: true
    filter: "pandoc -f html -t plain"
    extensions: [".html", ".htm"]
```

---

## Validation

Configuration is validated on load. Common errors:

| Error | Cause | Solution |
|-------|-------|----------|
| `Knowledge root does not exist` | Path doesn't exist | Create directory or fix path |
| `Knowledge root is not a directory` | Path is a file | Use directory path |
| `Invalid log_level` | Wrong log level | Use DEBUG/INFO/WARNING/ERROR |
| `context_lines must be 0-50` | Out of range | Use valid range |

---

## CLI Override

CLI arguments override config file:

```bash
# Override root
file-knowledge-mcp --root /other/path

# Override log level
file-knowledge-mcp --log-level DEBUG

# Both
file-knowledge-mcp --config prod.yaml --log-level DEBUG
```
