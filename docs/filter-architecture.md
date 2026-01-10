# Filter Architecture

## Overview

Fathom MCP uses document filters to enable searching in non-text formats like PDF, DOCX, EPUB, etc. The filter system constructs ugrep command-line arguments programmatically, providing transparency and cross-platform compatibility.

## Architecture

### Components

1. **FilterArgumentsBuilder** (`src/fathom_mcp/search/filter_builder.py`)
   - Constructs `--filter` arguments from format configurations
   - Validates filters against security policy
   - Provides human-readable filter summaries
   - No external file dependencies

2. **UgrepEngine** (`src/fathom_mcp/search/ugrep.py`)
   - Integrates FilterArgumentsBuilder
   - Builds complete ugrep commands with filters
   - Executes searches with proper security controls

3. **FilterSecurity** (`src/fathom_mcp/security.py`)
   - Validates filter commands (whitelist/blacklist/disabled modes)
   - Executes filters with timeouts and sandboxing
   - Prevents security violations

### Filter Syntax

Filters use ugrep's `--filter` option with the format:

```
--filter=extensions:command
```

Where:
- `extensions`: Comma-separated list without dots (e.g., `pdf,PDF`)
- `command`: Shell command with `%` placeholder for file path

**Example:**
```
--filter=pdf:pdftotext % -
--filter=docx:pandoc --wrap=preserve -f docx -t plain % -o -
```

### Key Design Principles

1. **Programmatic Construction**
   - Filters built at runtime from configuration
   - No intermediate configuration files
   - Complete transparency in command construction

2. **Security First**
   - All filters validated through FilterSecurity
   - Whitelist mode by default
   - Timeout enforcement
   - Sandboxed execution

3. **Cross-Platform**
   - Pure Python implementation
   - Platform-agnostic command building
   - Proper path handling on Windows/Unix

## Configuration

### Format Definition

```yaml
formats:
  pdf:
    enabled: true
    extensions: [".pdf"]
    filter: "pdftotext % -"

  docx:
    enabled: false
    extensions: [".docx"]
    filter: "pandoc --wrap=preserve -f docx -t plain % -o -"
```

### Security Settings

```yaml
security:
  enable_shell_filters: true
  filter_security_mode: "whitelist"  # whitelist, blacklist, or disabled
  allowed_filter_commands:
    - "pdftotext"
    - "pandoc"
    - "/usr/bin/pdftotext"
    - "/usr/local/bin/pandoc"
  filter_timeout_seconds: 30
```

## Usage

### Building Filter Arguments

```python
from fathom_mcp.config import Config
from fathom_mcp.search.filter_builder import FilterArgumentsBuilder

config = Config(knowledge={"root": "/path/to/documents"})
builder = FilterArgumentsBuilder(config)

# Get filter arguments for ugrep
filter_args = builder.build_filter_args()
# Returns: ['--filter=pdf:pdftotext % -', '--filter=docx:pandoc ...']

# Check if filters are configured
if builder.has_filters():
    print(builder.get_filter_summary())
```

### Search Integration

```python
from fathom_mcp.search.ugrep import UgrepEngine

engine = UgrepEngine(config)

# Filters are automatically included in search commands
result = await engine.search(
    query="test",
    path=knowledge_root,
    recursive=True
)
```

### Filter Validation

```python
# Validate all filters against security policy
results = builder.validate_filters()
# Returns: {'pdf': True, 'docx': True, 'word_doc': False}
```

## Command Line Flow

1. **Configuration Loading**
   - Formats loaded from config.yaml or defaults
   - Enabled formats identified

2. **Filter Construction** (FilterArgumentsBuilder)
   - For each enabled format with a filter:
     - Build extension list (e.g., "pdf")
     - Construct filter spec (e.g., "pdf:pdftotext % -")
     - Add as `--filter=` argument

3. **Command Building** (UgrepEngine)
   - Base ugrep command: `ugrep -% -i -C<n> --line-number --with-filename`
   - Add filter arguments from builder
   - Add extension includes: `--include *.pdf --include *.docx`
   - Add query and path

4. **Execution**
   - Validate through FilterSecurity
   - Execute with timeout
   - Parse results

## Example Command

Given configuration with PDF and DOCX filters enabled:

```bash
ugrep -% -i -C5 --line-number --with-filename \
  --filter=pdf:pdftotext % - \
  --filter=docx:pandoc --wrap=preserve -f docx -t plain % -o - \
  -r \
  --include *.pdf \
  --include *.docx \
  --include *.md \
  --include *.txt \
  "search query" \
  /path/to/documents
```

## Adding New Formats

1. **Define format in config.py:**

```python
"epub": FormatConfig(
    extensions=[".epub"],
    filter="pandoc --wrap=preserve -f epub -t plain % -o -",
    enabled=False,
)
```

2. **Add filter command to security whitelist:**

```python
allowed_filter_commands: list[str] = Field(
    default_factory=lambda: [
        # ... existing commands
        "pandoc",
        "/usr/bin/pandoc",
        "/usr/local/bin/pandoc",
    ]
)
```

3. **Enable in configuration:**

```yaml
formats:
  epub:
    enabled: true
```

The filter will automatically be included in search commands.

## Troubleshooting

### Filter Not Working

1. Check if format is enabled:
```python
config.formats["pdf"].enabled  # Should be True
```

2. Verify filter tool is available:
```bash
pdftotext --version
```

3. Check security validation:
```python
builder = FilterArgumentsBuilder(config)
results = builder.validate_filters()
print(results)  # Should show {'pdf': True}
```

4. Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Security Violations

If filters fail validation:

1. Check security mode:
```yaml
security:
  filter_security_mode: "whitelist"
```

2. Add command to whitelist:
```yaml
security:
  allowed_filter_commands:
    - "pdftotext"  # Base command
    - "pdftotext % -"  # Full command with args
    - "/usr/bin/pdftotext"  # Absolute path
```

3. Or temporarily disable for testing:
```yaml
security:
  filter_security_mode: "disabled"  # NOT recommended for production
```

## Performance Considerations

1. **Filter Execution**
   - Each filter runs as a subprocess
   - Timeout enforced (default: 30s)
   - Limited concurrency via semaphore

2. **Caching**
   - Search results cached by query
   - Smart cache tracks file modification times
   - Invalid cache entries automatically removed

3. **Large Files**
   - Configure timeout for large documents:
```yaml
security:
  filter_timeout_seconds: 60
```

## Testing

See test files for examples:
- `tests/test_filter_builder.py` - Unit tests for FilterArgumentsBuilder
- `tests/test_filter_integration.py` - Integration tests with UgrepEngine
- `tests/test_formats.py` - Format-specific tests

## References

- [ugrep documentation](https://github.com/Genivia/ugrep)
- [FilterArgumentsBuilder source](../src/fathom_mcp/search/filter_builder.py)
- [Security model](./security.md)
