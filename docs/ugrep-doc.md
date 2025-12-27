# ugrep - Ultra-fast Universal Grep

ugrep is a high-performance file pattern searcher designed as a drop-in replacement for GNU/BSD grep with extensive enhancements. Built on the RE/flex regex library, it provides ultra-fast Unicode regex matching with SIMD optimizations (SSE2, AVX2, AVX512BW, ARM NEON), multi-threaded search capabilities, and support for multiple regex engines (POSIX BRE/ERE, PCRE2, Boost.Regex). The tool maintains complete compatibility with traditional grep command-line interfaces while adding powerful new features.

Beyond basic pattern matching, ugrep offers advanced capabilities including fuzzy matching with configurable Levenshtein distance, Boolean query syntax with AND/OR/NOT operators, transparent decompression and archive searching (zip, 7z, tar, gz, bz2, xz, lz4, zstd, brotli), document filtering for PDFs and Office files, an interactive query TUI, and customizable output formats (JSON, XML, CSV, hexdump). It includes a work-stealing multi-threaded job scheduler for optimal performance on large codebases and supports optional file indexing for accelerated searches on slow file systems.

---

## Command-Line Usage

### Basic pattern search

```bash
# Search for pattern in files
ugrep 'error' *.log

# Case-insensitive search
ugrep -i 'warning' file.txt

# Recursive search with line numbers
ugrep -rn 'TODO' src/

# Expected output:
# src/main.cpp:42:    // TODO: implement this feature
# src/utils.cpp:15:   // TODO: optimize performance
```

### Interactive query TUI with real-time search

```bash
# Start interactive terminal UI
ug -Q

# Start TUI with initial pattern
ug -Q -e 'function'

# TUI controls:
# F1 or CTRL-Z: Show help
# F2 or CTRL-Y: View/edit selected file
# TAB: Navigate to files
# SHIFT-TAB: Navigate to directories
# ALT-n: Toggle line numbers
# ALT-i: Toggle case sensitivity
# ALT-l: Toggle file list mode
# ALT-w: Toggle word matching
# ALT-z: Toggle fuzzy matching

# Example session:
# 1. Run: ug -Q
# 2. Type: main
# 3. Press ALT-n to show line numbers
# 4. Press TAB to highlight first file
# 5. Press F2 to view file contents
```

### Recursive search with file type filtering

```bash
# Search C++ files only
ugrep -t cpp 'class.*public' -r src/

# Search by file extension
ugrep -O cpp,hpp 'namespace' .

# Search Python files excluding tests
ugrep -t python -g '^test_*.py' 'def ' .

# Expected output with -n:
# src/engine.cpp:23:class Engine : public Base {
# src/renderer.cpp:45:class Renderer : public Component {
```

### Archive and compressed file search

```bash
# Search in compressed files
ugrep -z 'pattern' archive.zip

# Search nested archives up to 2 levels deep
ugrep -z --zmax=2 'error' backup.tar.gz

# Search all archives in directory
ugrep -z 'keyword' *.7z *.zip *.tar.gz

# Supported formats: .gz, .Z, .bz, .bz2, .lzma, .xz, .lz4, .zst, .br
# Supported archives: .zip, .7z, .tar, .pax, .cpio, .jar
```

### Boolean query search with AND/OR/NOT operators

```bash
# Match lines with A AND B
ug -% 'error warning' *.log

# Match A OR B, both must be in file
ug -% 'error|warning critical' *.log

# Match A but NOT B or C
ug -% 'exception -timeout -cancelled' *.log

# Exact string matching with quotes
ug -% '"null pointer" -test' src/

# Alternative syntax with options
ugrep -e 'error' --and 'critical' *.log
ugrep -e 'malloc' --andnot 'free' src/*.c

# File-wide Boolean matching (not line-based)
ug -%%  'init cleanup' --stats *.cpp
# Output: Lists files containing both "init" AND "cleanup" anywhere
```

### Fuzzy matching with edit distance

```bash
# Fuzzy search with default 1 edit distance
ugrep -Z 'hello' file.txt
# Matches: hello, helo, hallo, hell, helllo

# Allow up to 3 edits (insertions, deletions, substitutions)
ugrep -Z3 'function' src/*.cpp

# Allow only insertions (up to 2 extra characters)
ugrep -Z+2 'test' *.py

# Allow only deletions (up to 2 missing characters)
ugrep -Z-2 'testing' *.py

# Allow only substitutions (up to 2 replaced characters)
ugrep -Z~2 'color' *.txt
# Matches: color, colour, colar, etc.

# Show only best matches per file
ugrep -Zbest 'search' docs/

# Sort files by best match quality
ugrep -Z --sort=best 'algorithm' papers/*.pdf
```

### Document and binary file search

```bash
# Search PDF files using pdftotext filter
ug --filter='pdf:pdftotext % -' 'contract' *.pdf

# Search Microsoft Word documents
ug --filter='doc:antiword %' 'budget' reports/*.doc

# Search modern Office formats with pandoc
ug --filter='docx,odt,epub:pandoc --wrap=preserve -t plain % -o -' 'policy' *.docx

# Search all document types with ug+ command
ug+ 'quarterly report' documents/

# Binary file search with hexdump output
ugrep --hexdump -U '\x4D\x5A' /bin/*
# Searches for MZ header (DOS/Windows executables)

# Binary search with text pattern
ugrep -X 'password' memory.dump
```

### Output formatting and export

```bash
# JSON output
ugrep --json 'error' *.log
# Output:
# [
#   {"file":"app.log","line":42,"column":10,"match":"error: failed"},
#   {"file":"sys.log","line":15,"column":5,"match":"error: timeout"}
# ]

# XML output
ugrep --xml 'warning' *.log
# Output:
# <grep>
#   <file name="app.log">
#     <match line="23" column="8">warning: deprecated</match>
#   </file>
# </grep>

# CSV output
ugrep --csv 'TODO' src/*.cpp
# Output:
# "file","line","column","match"
# "main.cpp","42","5","TODO: refactor"
# "utils.cpp","18","12","TODO: add tests"

# Custom format string
ugrep --format='%f:%n:%k - %O%~' 'function' src/*.js
# Output:
# app.js:15:3 - function init() {
# utils.js:42:1 - function parse(data) {

# Format with match highlighting
ugrep --format='File: %f%~Line %n: %O%~%~' 'class' *.cpp
```

### Pattern replacement and text transformation

```bash
# Replace pattern in output with -P (PCRE) and --replace
ugrep -P --replace='REDACTED' '\b\d{3}-\d{2}-\d{4}\b' data.txt
# Replaces SSN patterns: 123-45-6789 → REDACTED

# Extract and reformat with capture groups
ugrep -P --replace='Name: %1, Email: %2' '(\w+)@(\w+\.\w+)' contacts.txt
# Input: john@example.com
# Output: Name: john, Email: example.com

# Pass through entire file with replacements (-y flag)
ugrep -y -P --replace='[FILTERED]' 'password\s*=\s*\S+' config.ini

# Replace with formatted output
ugrep -P --replace='Match at line %n, col %k: %m' 'TODO' src/*.cpp
```

### Multi-threaded search with job control

```bash
# Use 8 parallel threads
ugrep -r -J8 'pattern' large_codebase/

# Single-threaded mode
ugrep -J1 'pattern' files/

# Optimal thread count (automatic)
ugrep -r 'pattern' project/

# Set work-stealing threshold
ugrep -r --min-steal=4096 'pattern' /big/filesystem/
```

---

## RE/flex Pattern Class

### Create and compile regex patterns

```cpp
#include <reflex/pattern.h>

// Compile a pattern from string
reflex::Pattern pattern("\\w+");

// Pattern with options (case-insensitive)
reflex::Pattern pattern("hello", "i");

// Pattern from std::string
std::string regex = "[a-z]+";
reflex::Pattern pattern(regex);

// Assign new pattern
pattern.assign("new.*pattern", "im");
pattern = "different.*regex";

// Pattern options:
// "i" - case insensitive
// "m" - multiline (^ and $ match line boundaries)
// "s" - single-line (. matches newline)
// "x" - free-spacing (ignore whitespace in pattern)

// Example with error handling:
try {
  reflex::Pattern pattern("(invalid[");
} catch (reflex::regex_error& e) {
  std::cerr << "Regex error: " << e.what() << std::endl;
}
```

### Access pattern metadata and opcodes

```cpp
#include <reflex/pattern.h>

reflex::Pattern pattern("\\d+");

// Get pattern string
const char* regex_str = pattern.rex();
std::cout << "Pattern: " << regex_str << std::endl;

// Get options
const char* opts = pattern.opt();

// Check if pattern is compiled
bool compiled = (pattern.opc() != nullptr);

// Get FSM function pointer (if compiled to native code)
reflex::Pattern::FSM fsm = pattern.fsm();

// Pattern properties
size_t length = pattern.size();  // Approximate pattern complexity

// Create pattern from pre-compiled opcodes
const reflex::Pattern::Opcode* opcodes = pattern.opc();
reflex::Pattern reused_pattern(opcodes);
```

---

## RE/flex Matcher Class

### Basic pattern matching with find() and scan()

```cpp
#include <reflex/matcher.h>
#include <reflex/pattern.h>
#include <reflex/input.h>

// Create pattern and matcher
reflex::Pattern pattern("\\b\\w+\\b");
reflex::Matcher matcher(pattern, "Hello World from RE/flex");

// Find all matches
while (matcher.find()) {
  std::cout << "Match: " << matcher.text()
            << " at position " << matcher.first()
            << std::endl;
}
// Output:
// Match: Hello at position 0
// Match: World at position 6
// Match: from at position 12
// Match: RE at position 17
// Match: flex at position 20

// Scan tokenizer-style (alternative to find)
reflex::Matcher scanner(pattern, "token1 token2");
while (scanner.scan()) {
  std::cout << "Token: " << scanner.str() << std::endl;
}

// Split at pattern matches
reflex::Pattern delimiter("\\s+");
reflex::Matcher splitter(delimiter, "one two three");
while (splitter.split()) {
  std::cout << "Part: " << splitter.str() << std::endl;
}
// Output:
// Part: one
// Part: two
// Part: three
```

### Extract match position and context information

```cpp
#include <reflex/matcher.h>

reflex::Pattern pattern("error");
reflex::Matcher matcher(pattern,
  "line 1\n"
  "an error occurred\n"
  "line 3\n");

while (matcher.find()) {
  // Match boundaries
  const char* start = matcher.begin();
  const char* end = matcher.end();
  size_t len = matcher.size();

  // Position information
  size_t byte_offset = matcher.first();
  size_t line_num = matcher.lineno();      // 1-based
  size_t col_num = matcher.columno();      // 1-based

  // Line context
  const char* line_start = matcher.bol();  // beginning of line
  const char* line_end = matcher.eol();    // end of line
  std::string full_line = matcher.line();

  // Match text
  std::string match_str = matcher.str();
  std::pair<const char*, size_t> match_pair = matcher.operator[](0);

  std::cout << "Found '" << match_str << "' at "
            << "line " << line_num
            << ", column " << col_num << "\n"
            << "Full line: " << full_line << std::endl;
}
// Output:
// Found 'error' at line 2, column 4
// Full line: an error occurred
```

### Capture groups with Perl-compatible regex

```cpp
#include <reflex/pcre2matcher.h>  // For PCRE2 support

// Pattern with capture groups
reflex::Pattern pattern("(\\w+)@(\\w+\\.\\w+)");
reflex::PCRE2Matcher matcher(pattern, "Contact: john@example.com");

while (matcher.find()) {
  // Full match
  std::cout << "Full match: " << matcher[0].first << std::endl;

  // Capture group 1 (username)
  auto group1 = matcher[1];
  std::string username(group1.first, group1.second);
  std::cout << "Username: " << username << std::endl;

  // Capture group 2 (domain)
  auto group2 = matcher[2];
  std::string domain(group2.first, group2.second);
  std::cout << "Domain: " << domain << std::endl;
}
// Output:
// Full match: john@example.com
// Username: john
// Domain: example.com

// Using named capture groups
reflex::Pattern named_pattern("(?<user>\\w+)@(?<domain>\\w+\\.\\w+)");
reflex::PCRE2Matcher named_matcher(named_pattern, "admin@site.org");
// Access named groups via indices
```

### Work with different input sources

```cpp
#include <reflex/matcher.h>
#include <reflex/input.h>
#include <fstream>

reflex::Pattern pattern("\\d+");

// From C++ string
reflex::Input string_input("Numbers: 123, 456");
reflex::Matcher m1(pattern, string_input);

// From FILE pointer
FILE* fp = fopen("data.txt", "r");
reflex::Input file_input(fp);
reflex::Matcher m2(pattern, file_input);
fclose(fp);

// From std::istream
std::ifstream ifs("input.txt");
reflex::Input stream_input(ifs);
reflex::Matcher m3(pattern, stream_input);

// From memory buffer
const char* buffer = "Buffer: 789";
size_t length = strlen(buffer);
reflex::Input buffer_input(buffer, length);
reflex::Matcher m4(pattern, buffer_input);

// From C-string
reflex::Input cstr_input("C-string: 999");
reflex::Matcher m5(pattern, cstr_input);

// Switch input source dynamically
reflex::Matcher matcher(pattern);
matcher.input(string_input);
while (matcher.find()) {
  std::cout << matcher.text() << " ";
}
matcher.input(buffer_input);
while (matcher.find()) {
  std::cout << matcher.text() << " ";
}
// Output: 123 456 789
```

### Configure matcher behavior with options

```cpp
#include <reflex/matcher.h>

reflex::Pattern pattern("\\w+");

// Matcher with options string
// A = accept negative patterns as REDO
// N = nullable (allow empty matches)
// W = match whole words
// T=n = tab size (T=4 for 4-space tabs)
reflex::Matcher matcher(pattern, "input text", "N");

// Match whole words option
reflex::Matcher word_matcher(pattern, "word-boundary test", "W");
while (word_matcher.find()) {
  std::cout << word_matcher.text() << std::endl;
}

// Reset matcher with new options
matcher.reset("NT=8");

// Set new input
matcher.input(reflex::Input("new input"));

// Set new pattern
reflex::Pattern new_pattern("\\d+");
matcher.pattern(new_pattern);

// Check buffer state
if (!matcher.at_end()) {
  const char* current_buffer = matcher.buffer();
  size_t available = matcher.avail();
  std::cout << "Available bytes: " << available << std::endl;
}

// Check position
bool at_start = matcher.at_bob();  // beginning of buffer
bool at_finish = matcher.at_end();
```

---

## RE/flex FuzzyMatcher Class

### Fuzzy search with configurable edit distance

```cpp
#include <reflex/fuzzymatcher.h>
#include <reflex/pattern.h>

// Pattern to match approximately
reflex::Pattern pattern("hello");

// Create fuzzy matcher with max 1 edit
reflex::FuzzyMatcher fuzzy(pattern, 1, "helo world");

while (fuzzy.find()) {
  uint8_t edit_count = fuzzy.edits();
  std::string match = fuzzy.text();

  std::cout << "Match: " << match
            << " (edits: " << (int)edit_count << ")"
            << std::endl;
}
// Output: Match: helo (edits: 1)

// Max 2 edits (any combination)
reflex::FuzzyMatcher fuzzy2(pattern, 2, "halo wrld");
// Matches: halo (1 substitution from hello)

// Max 3 edits
reflex::FuzzyMatcher fuzzy3(pattern, 3, "hllo helo heelo");
while (fuzzy3.find()) {
  std::cout << "Match: " << fuzzy3.text()
            << " (" << (int)fuzzy3.edits() << " edits)"
            << std::endl;
}
// Output:
// Match: hllo (edits: 1)
// Match: helo (edits: 1)
// Match: heelo (edits: 1)
```

### Control edit operation types (insertions, deletions, substitutions)

```cpp
#include <reflex/fuzzymatcher.h>

reflex::Pattern pattern("test");

// Distance flags
using FM = reflex::FuzzyMatcher;

// Allow only insertions (up to 2)
uint16_t ins_only = FM::INS | 2;
reflex::FuzzyMatcher m1(pattern, ins_only, "teest tesst");
// Matches: teest (1 insertion), tesst (1 insertion)

// Allow only deletions (up to 2)
uint16_t del_only = FM::DEL | 2;
reflex::FuzzyMatcher m2(pattern, del_only, "tst tet");
// Matches: tst (1 deletion), tet (1 deletion)

// Allow only substitutions (up to 2)
uint16_t sub_only = FM::SUB | 2;
reflex::FuzzyMatcher m3(pattern, sub_only, "best rest");
// Matches: best (1 substitution), rest (1 substitution)

// Allow insertions and deletions (no substitutions)
uint16_t ins_del = FM::INS | FM::DEL | 2;
reflex::FuzzyMatcher m4(pattern, ins_del, "tst teest");
// Matches both

// Allow insertions and substitutions
uint16_t ins_sub = FM::INS | FM::SUB | 2;
reflex::FuzzyMatcher m5(pattern, ins_sub, "best teest");

// Binary mode (no UTF-8 awareness)
uint16_t binary = FM::BIN | 3;
reflex::FuzzyMatcher m6(pattern, binary, "binary data");
```

### Dynamic distance adjustment and match quality

```cpp
#include <reflex/fuzzymatcher.h>

reflex::Pattern pattern("search");
reflex::FuzzyMatcher fuzzy(pattern, 3,
  "serch sarch seearch ssearch");

// Find all matches and report quality
while (fuzzy.find()) {
  uint8_t edits = fuzzy.edits();
  uint16_t current_distance = fuzzy.distance();
  std::string match = fuzzy.text();
  size_t line = fuzzy.lineno();

  std::cout << "Line " << line << ": '" << match << "' "
            << "edits=" << (int)edits
            << " quality=" << (3 - edits) << "/3"
            << std::endl;
}
// Output:
// Line 1: 'serch' edits=1 quality=2/3
// Line 1: 'sarch' edits=1 quality=2/3
// Line 1: 'seearch' edits=1 quality=2/3
// Line 1: 'ssearch' edits=1 quality=2/3

// Adjust distance mid-search
fuzzy.distance(1);  // Stricter matching
fuzzy.input(reflex::Input("new text"));

// Get current settings
uint16_t settings = fuzzy.distance();
bool allows_ins = settings & reflex::FuzzyMatcher::INS;
bool allows_del = settings & reflex::FuzzyMatcher::DEL;
bool allows_sub = settings & reflex::FuzzyMatcher::SUB;
uint8_t max_dist = settings & 0xFF;
```

---

## RE/flex Input Class

### Create input sources from various data types

```cpp
#include <reflex/input.h>
#include <fstream>

// Empty input
reflex::Input empty;

// From C++ string
std::string text = "Hello World";
reflex::Input str_input(text);

// From C-style string
const char* cstr = "C string data";
reflex::Input cstr_input(cstr);

// From character buffer with size
char buffer[256] = "Buffer data";
size_t buf_size = strlen(buffer);
reflex::Input buf_input(buffer, buf_size);

// From FILE pointer
FILE* fp = fopen("data.txt", "r");
if (fp) {
  reflex::Input file_input(fp);
  // Use input...
  fclose(fp);
}

// From std::istream
std::ifstream ifs("input.txt");
reflex::Input stream_input(ifs);

// From std::cin
reflex::Input stdin_input(std::cin);

// Copy constructor
reflex::Input copy_input(str_input);
```

### Handle different text encodings

```cpp
#include <reflex/input.h>

FILE* fp = fopen("encoded.txt", "r");

// UTF-8 (default)
reflex::Input utf8(fp, reflex::Input::file_encoding::utf8);

// UTF-16 big-endian
reflex::Input utf16be(fp, reflex::Input::file_encoding::utf16be);

// UTF-16 little-endian
reflex::Input utf16le(fp, reflex::Input::file_encoding::utf16le);

// UTF-32 big-endian
reflex::Input utf32be(fp, reflex::Input::file_encoding::utf32be);

// UTF-32 little-endian
reflex::Input utf32le(fp, reflex::Input::file_encoding::utf32le);

// ISO-8859-1 (Latin-1)
reflex::Input latin1(fp, reflex::Input::file_encoding::latin);

// Windows code pages
reflex::Input cp1252(fp, reflex::Input::file_encoding::cp1252);
reflex::Input cp1251(fp, reflex::Input::file_encoding::cp1251);

// DOS code pages
reflex::Input cp437(fp, reflex::Input::file_encoding::cp437);
reflex::Input cp850(fp, reflex::Input::file_encoding::cp850);

// EBCDIC
reflex::Input ebcdic(fp, reflex::Input::file_encoding::ebcdic);

// MacRoman
reflex::Input macroman(fp, reflex::Input::file_encoding::macroman);

// KOI8 variants
reflex::Input koi8r(fp, reflex::Input::file_encoding::koi8r);
reflex::Input koi8u(fp, reflex::Input::file_encoding::koi8u);

// Example: Search Latin-1 encoded file
reflex::Pattern pattern("café");
FILE* latin1_file = fopen("french.txt", "r");
reflex::Input latin1_input(latin1_file,
                          reflex::Input::file_encoding::latin);
reflex::Matcher matcher(pattern, latin1_input);
while (matcher.find()) {
  std::cout << "Found: " << matcher.text() << std::endl;
}
fclose(latin1_file);
```

---

## Integration with grep workflows

### Replace GNU grep in shell scripts

```bash
#!/bin/bash
# Traditional grep script converted to ugrep

# Old: grep -r "pattern" directory/
# New: ugrep -r "pattern" directory/
ugrep -r "function" src/

# Old: grep -i "error" *.log
# New: ugrep -i "error" *.log
ugrep -i "error" *.log

# Old: grep -n "TODO" file.cpp
# New: ugrep -n "TODO" file.cpp
ugrep -n "TODO" file.cpp

# Old: egrep -o "[0-9]+" data.txt
# New: ugrep -o "[0-9]+" data.txt
ugrep -o "[0-9]+" data.txt

# Old: fgrep -x "exact match" list.txt
# New: ugrep -F -x "exact match" list.txt
ugrep -F -x "exact match" list.txt

# Create symbolic links for compatibility
ln -s ugrep grep
ln -s ugrep egrep
ln -s ugrep fgrep
```

### Configure as git grep alternative

```bash
# ~/.gitconfig
[alias]
  # Use ugrep for git grep
  g = "!f() { \
    ugrep --color=always -n \"$@\" \
    $(git rev-parse --show-toplevel); \
  }; f"

# Usage:
git g "pattern"

# Configure git to use ugrep for paging
[core]
  pager = ugrep --color=always -n

# Use ugrep in git log search
git log -p --all -G "pattern" | \
  ugrep --color=always "pattern"
```

### Vim and editor integration

```vim
" ~/.vimrc - Configure Vim to use ugrep

" Set ugrep as grep program
set grepprg=ugrep\ -RInk\ -j\ -u\ --tabs=1\ --ignore-files
set grepformat=%f:%l:%c:%m,%f+%l+%c+%m,%-G%f\\\|%l\\\|%c\\\|%m

" Search with :grep command
:grep pattern

" Search in specific file types
:grep pattern -t cpp

" Open quickfix window with results
:copen

" Navigate results
:cnext     " Next result
:cprev     " Previous result
:cfirst    " First result
:clast     " Last result

" Fuzzy search function
function! UgrepFuzzy(pattern)
  execute 'grep -Z ' . a:pattern
  copen
endfunction
command! -nargs=1 Zgrep call UgrepFuzzy(<q-args>)

" Usage: :Zgrep pattern
```

### Build system integration with make

```makefile
# Makefile using ugrep for code analysis

# Find TODO comments
todos:
	@ugrep -tc++ -n --color=always "TODO|FIXME" src/ || true

# Check for debug statements
debug-check:
	@ugrep -tc++ "console\.log|debugger|print\(" src/ && \
	echo "Debug statements found!" || \
	echo "No debug statements found."

# Find unused variables (C++)
unused-vars:
	@ugrep -tc++ "\b_\w+" src/ -n --color=always

# Search for security issues
security-scan:
	@ugrep -r --color=always -n \
	  -e "strcpy" -e "strcat" -e "sprintf" -e "gets" \
	  src/ || echo "No security issues found"

# Find all function definitions
list-functions:
	@ugrep -tc++ -f cpp/functions src/ -n | \
	  ugrep "^\S+:\d+:" -o | sort | uniq

# Count lines of code
loc:
	@ugrep -tc++ "" -c src/ | \
	  awk '{sum+=$$1} END {print "Total lines:", sum}'
```

### Pipeline processing with xargs and parallel

```bash
#!/bin/bash
# Advanced pipeline patterns with ugrep

# Find and process matching files
ugrep -l "pattern" -r src/ | \
  xargs -I {} sh -c 'process_file "$1"' _ {}

# Parallel processing with GNU parallel
ugrep -l "TODO" -r . | \
  parallel -j 8 'echo "Processing {}"; analyze_file {}'

# Count matches per file and sort
ugrep -c "error" *.log | \
  sort -t: -k2 -nr | \
  head -10

# Extract and transform matches
ugrep -o -P "email:\s*(\S+)" data.txt | \
  cut -d: -f2 | \
  sort | uniq > emails.txt

# Fuzzy deduplication
ugrep -Z --sort=best "duplicate" dataset.txt | \
  ugrep -o "^[^:]+:\d+" | \
  cut -d: -f1 | uniq

# Multi-stage filtering
ugrep -r "class" src/ -t cpp | \
  ugrep "public" | \
  ugrep -v "private" | \
  ugrep -o "class \w+"

# Generate file statistics
ugrep -r "" -c --sort=size -t cpp src/ | \
  awk -F: '{print $2, $1}' | \
  sort -nr | \
  head -20
```

### Custom output formats for data extraction

```bash
# Extract structured data with custom format
ugrep --format='{"file":"%f","line":%n,"text":"%O"}%~' \
  -tc++ "class.*public" src/ > classes.json

# Generate CSV report
ugrep --csv "error" *.log > error_report.csv

# Create XML documentation
ugrep --xml -f cpp/functions src/ > api_functions.xml

# Extract function signatures to specific format
ugrep -tc++ --format='%[1]#%~' \
  -P "(\w+\s+\w+\s*\([^)]*\))" src/*.cpp > signatures.txt

# Generate test coverage report
ugrep --format='%h:%n%~' "COVERAGE" tests/*.cpp | \
  sort | uniq -c | \
  awk '{printf "%3d %s\n", $1, $2}'

# Create markdown documentation
echo "# Code Analysis Report" > report.md
echo "" >> report.md
echo "## TODO Items" >> report.md
ugrep --format='- [ ] %f:%n - %O%~' "TODO" src/ >> report.md
echo "" >> report.md
echo "## FIXME Items" >> report.md
ugrep --format='- [ ] %f:%n - %O%~' "FIXME" src/ >> report.md
```

---

## Summary

ugrep excels as both a command-line utility and a library foundation through its RE/flex regex engine. As a CLI tool, it provides comprehensive pattern matching capabilities with performance optimizations including SIMD acceleration, multi-threaded search, and optional file indexing. The Boolean query syntax enables complex AND/OR/NOT searches, fuzzy matching handles approximate pattern matching with configurable edit distances, and transparent archive/compression support allows seamless searching through zip, 7z, tar, and compressed files. The interactive TUI provides real-time search feedback, while customizable output formats (JSON, XML, CSV) and document filters (PDF, DOC, Office) extend functionality beyond plain text.

The RE/flex C++ library underlying ugrep offers a powerful API for embedding pattern matching in applications. The Pattern class compiles regexes with various options and engines (POSIX, PCRE2, Boost.Regex). The Matcher class provides efficient find/scan/split operations with rich context information including line numbers, columns, capture groups, and surrounding text. The FuzzyMatcher extends this with Levenshtein distance matching and fine-grained control over edit operations. The Input abstraction handles diverse sources (files, streams, strings, buffers) and encodings (UTF-8/16/32, Latin-1, Windows/DOS code pages, EBCDIC). This architecture enables integration into editors (Vim, Emacs), build systems (make, CMake), version control workflows (git grep), and custom applications requiring high-performance Unicode-aware pattern matching.
