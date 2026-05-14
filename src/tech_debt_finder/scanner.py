"""
scanner.py — Find code rot markers in files

This module walks through files and finds:
- TODO, FIXME, HACK, TEMP, XXX comments
- Commented-out code blocks (3+ consecutive lines)

CONCEPTS EXPLAINED:

1. PATHLIB
   Python's modern way to handle file paths.
   Dart equivalent: Working with File() and Directory()
   
   path = Path("src/auth.dart")
   path.suffix          → ".dart"
   path.name            → "auth.dart"  
   path.parent          → Path("src")
   path.exists()        → True/False
   path.is_file()       → True/False
   path.read_text()     → file contents as string

2. GENERATORS (yield)
   A way to return items one-at-a-time instead of building a huge list.
   
   # Without generator (loads ALL files into memory):
   def get_files():
       result = []
       for f in folder:
           result.append(f)
       return result
   
   # With generator (one at a time, memory efficient):
   def get_files():
       for f in folder:
           yield f

3. DATACLASS
   Python's equivalent of a simple Dart class with fields.
   Like a Freezed/Equatable class but built-in.
   
   @dataclass
   class Marker:
       file: str
       line: int
   
   # Equivalent Dart:
   class Marker {
     final String file;
     final int line;
     Marker({required this.file, required this.line});
   }
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Marker:
    """
    Represents a single TODO/FIXME/etc. marker found in code.
    
    This is like a simple Dart class with named parameters.
    The @dataclass decorator auto-generates __init__, __repr__, __eq__.
    """
    file: str           # Path to the file
    line: int           # Line number (1-indexed, like editors show)
    marker_type: str    # "TODO", "FIXME", "HACK", "TEMP", "XXX"
    text: str           # The message after the marker
    full_line: str      # The entire line of code (for context)
    
    # These will be filled in later by git_utils.py:
    author: str = "unknown"
    date: str = "unknown"
    age_days: int = 0
    file_modifications: int = 0
    
    # Calculated later by prioritizer.py:
    priority_score: float = 0.0
    priority_bucket: str = "low"  # "high", "medium", "low"


@dataclass
class CommentedCodeBlock:
    """
    Represents a block of commented-out code (dead code).
    
    These are 3+ consecutive comment lines that look like actual code,
    not just explanatory comments.
    """
    file: str
    start_line: int
    end_line: int
    line_count: int
    preview: str  # First line of the block for context
    
    # Filled in by git_utils:
    author: str = "unknown"
    date: str = "unknown"
    age_days: int = 0


# =============================================================================
# PATTERNS — What we're looking for
# =============================================================================

# We want to find TODOs that are inside COMMENTS, not in regular code.
# Different languages have different comment styles:
#
#   Python/Ruby/Shell:  # comment
#   Dart/JS/Java/C:     // comment   or   /* comment */
#   HTML:               <!-- comment -->
#   SQL:                -- comment
#
# Our strategy: Look for common comment prefixes IMMEDIATELY FOLLOWED by the marker.
# This avoids false positives like "# was a TODO, now fixed" where TODO is mentioned
# but not the actual marker.

# Pattern for the TODO/FIXME/etc. part
MARKER_WORDS = r'(TODO|FIXME|HACK|TEMP|XXX)'

# Patterns that indicate we're inside a comment
# These go BEFORE the marker word
COMMENT_PREFIXES = [
    r'^\s*#',           # Python, Ruby, Shell: # comment
    r'^\s*//',          # Dart, JS, Java, C++: // comment
    r'^\s*/\*',         # C-style block comment start: /* comment
    r'^\s*\*',          # C-style block comment continuation: * comment
    r'^\s*<!--',        # HTML comment: <!-- comment
    r'^\s*--',          # SQL comment: -- comment
    r'^\s*;',           # Assembly, INI: ; comment
    r'^\s*%',           # LaTeX, Matlab: % comment
    r'^\s*\'\'\'',      # Python docstring (triple quote)
    r'^\s*"""',         # Python docstring (triple quote)
]

# Build the complete patterns
# STRICT: marker must come IMMEDIATELY after comment prefix (only whitespace allowed)
# This prevents "# was a TODO" from matching
#
# Pattern: COMMENT_PREFIX + whitespace + MARKER + optional (author) + optional colon + rest
# Examples that match:
#   # TODO: fix this
#   // FIXME: broken
#   # TODO(alice): assigned task
#   /* HACK - workaround */
#
# Examples that DON'T match:
#   # was a TODO, now fixed
#   # This has TODO in the middle
MARKER_PATTERNS = [
    re.compile(
        prefix + r'\s*' + MARKER_WORDS + r'(?:\([^)]*\))?[\s:\-]*(.*)$',
        re.IGNORECASE
    )
    for prefix in COMMENT_PREFIXES
]

# Also match markers at the very start of a line (for plain text files like .md)
# But only if it looks like a marker (starts with the word, not embedded in text)
STANDALONE_PATTERN = re.compile(
    r'^\s*' + MARKER_WORDS + r'[\s:]+(.+)$',  # Note: requires space/colon + text after
    re.IGNORECASE
)

# File extensions we should scan
# We skip binary files, images, etc.
CODE_EXTENSIONS = {
    # Languages you probably use
    '.dart', '.py', '.js', '.ts', '.jsx', '.tsx',
    '.java', '.kt', '.swift', '.go', '.rs', '.rb',
    '.c', '.cpp', '.h', '.hpp', '.cs',
    # Config/data files that might have TODOs
    '.yaml', '.yml', '.json', '.toml', '.xml',
    '.md', '.txt', '.sh', '.bash', '.zsh',
    '.html', '.css', '.scss', '.sass', '.less',
    '.sql', '.graphql',
}

# Folders to skip (common patterns)
SKIP_FOLDERS = {
    '.git', '.svn', '.hg',           # Version control
    'node_modules', '.npm',           # JavaScript
    '.venv', 'venv', '__pycache__',   # Python
    'build', 'dist', '.dart_tool',    # Build outputs
    '.idea', '.vscode',               # IDE folders
    'Pods', '.gradle',                # Mobile dev
    'coverage', '.nyc_output',        # Test coverage
}


# =============================================================================
# FILE WALKING — Find all code files
# =============================================================================

def iter_code_files(root: Path) -> Iterator[Path]:
    """
    Walk through a directory and yield all code files.
    
    This is a GENERATOR function (uses 'yield' instead of 'return').
    It returns files one-at-a-time, which is memory-efficient for large repos.
    
    Args:
        root: Starting directory (or single file)
        
    Yields:
        Path objects for each code file found
        
    Example:
        for file in iter_code_files(Path("./src")):
            print(file)  # src/auth.dart, src/utils.dart, ...
    """
    # If root is a single file, just yield it
    if root.is_file():
        if root.suffix.lower() in CODE_EXTENSIONS:
            yield root
        return
    
    # Walk the directory tree
    # root.rglob("*") recursively finds all files/folders
    for path in root.rglob("*"):
        # Skip if it's a directory
        if path.is_dir():
            continue
            
        # Skip if it's in a folder we want to ignore
        # any() returns True if ANY part matches
        if any(skip in path.parts for skip in SKIP_FOLDERS):
            continue
            
        # Skip if it's not a code file extension
        if path.suffix.lower() not in CODE_EXTENSIONS:
            continue
            
        yield path


# =============================================================================
# SCANNER — Find markers in a file
# =============================================================================

def scan_file(file_path: Path) -> list[Marker]:
    """
    Scan a single file for TODO/FIXME/etc. markers.
    
    Args:
        file_path: Path to the file to scan
        
    Returns:
        List of Marker objects found in the file
        
    Example:
        markers = scan_file(Path("src/auth.dart"))
        for m in markers:
            print(f"{m.marker_type} at line {m.line}: {m.text}")
    """
    markers = []
    
    try:
        # Read the entire file
        # encoding="utf-8" handles most code files
        # errors="ignore" skips characters that can't be decoded (rare)
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, IOError) as e:
        # File can't be read (permissions, etc.) — skip silently
        # In production, you might want to log this
        return []
    
    # Split into lines and scan each one
    # enumerate() gives us both the index and the line
    # start=1 means line numbers start at 1 (like editors show)
    for line_number, line in enumerate(content.splitlines(), start=1):
        # Try each comment pattern
        match = None
        
        # First, try comment-style patterns (most reliable)
        for pattern in MARKER_PATTERNS:
            match = pattern.search(line)
            if match:
                break
        
        # If no comment pattern matched, try standalone pattern
        # (for markdown, plain text, etc.)
        if not match:
            match = STANDALONE_PATTERN.search(line)
        
        if match:
            # match.group(1) = the marker type (TODO, FIXME, etc.)
            # match.group(2) = the text after the marker
            marker_type = match.group(1).upper()
            text = match.group(2).strip()
            
            # Skip if the text is empty (probably a false positive)
            if not text:
                continue
            
            marker = Marker(
                file=str(file_path),
                line=line_number,
                marker_type=marker_type,
                text=text,
                full_line=line.strip(),
            )
            markers.append(marker)
    
    return markers


# =============================================================================
# COMMENTED-OUT CODE DETECTION
# =============================================================================

# Patterns that suggest a comment line is actually code, not prose
# Must be STRONG indicators that this is real code
CODE_INDICATORS = [
    r'\w+\s*=\s*\w',     # Assignments: x = 1, name = "foo" (not just bare =)
    r'\w+\(',            # Function calls: foo(, bar(
    r'def\s+\w+',        # Python function def
    r'class\s+\w+',      # Class definition
    r'return\s+\w',      # Return with value
    r'if\s+\w',          # Conditionals with condition
    r'for\s+\w',         # Loops with variable
    r'while\s+\w',       # While loops
    r'import\s+\w',      # Imports
    r'from\s+\w',        # From imports
    r'const\s+\w',       # Variable declarations
    r'var\s+\w',         #
    r'let\s+\w',         #
    r'function\s+\w',    # JS function
    r'=>',               # Arrow functions
    r'\w+\.\w+\(',       # Method calls: obj.method(
    r'\[\w+\]',          # Array access: arr[i]
    r'raise\s+',         # Exceptions
    r'throw\s+',         #
    r'try:',             # Try blocks
    r'except',           # Except blocks
    r'catch\s*\(',       # Catch blocks
]

# Lines that look like separators/headers (NOT code)
SEPARATOR_PATTERNS = [
    r'^[#/\-=\*\s]+$',   # Lines with only comment chars and separators
    r'^#+\s*$',          # Empty comment lines
    r'^\s*\*+\s*$',      # Star separators
]

# Compiled pattern to check if a line looks like code
CODE_LINE_PATTERN = re.compile('|'.join(CODE_INDICATORS))
SEPARATOR_PATTERN = re.compile('|'.join(SEPARATOR_PATTERNS))

# Comment prefix patterns (to strip the comment marker)
COMMENT_PREFIX_STRIP = re.compile(r'^\s*(#|//|/\*|\*|<!--|--)\s*')


def _looks_like_code(line: str) -> bool:
    """Check if a comment line looks like actual code (not prose)."""
    # Strip the comment prefix
    stripped = COMMENT_PREFIX_STRIP.sub('', line).strip()
    
    # Empty line doesn't count
    if not stripped:
        return False
    
    # Check if it's just a separator/header line (not code)
    if SEPARATOR_PATTERN.match(stripped):
        return False
    
    # If line is mostly words (prose), it's probably not code
    # Code has lots of symbols, prose has mostly letters and spaces
    words = stripped.split()
    if len(words) >= 4:
        # Prose typically has 4+ words per line
        # Check ratio of alphanumeric words to total
        alpha_words = sum(1 for w in words if w.isalpha())
        if alpha_words / len(words) > 0.7:
            return False  # Too much English prose
    
    # Check if it has STRONG code-like patterns
    return bool(CODE_LINE_PATTERN.search(stripped))


def _is_comment_line(line: str) -> bool:
    """Check if a line is a comment."""
    stripped = line.strip()
    return (
        stripped.startswith('#') or
        stripped.startswith('//') or
        stripped.startswith('/*') or
        stripped.startswith('*') or
        stripped.startswith('<!--') or
        stripped.startswith('--')
    )


def find_commented_code_blocks(file_path: Path, min_lines: int = 3) -> list[CommentedCodeBlock]:
    """
    Find blocks of commented-out code in a file.
    
    Looks for 3+ consecutive comment lines that appear to contain
    actual code (assignments, function calls, etc.) rather than
    explanatory prose.
    
    Args:
        file_path: Path to the file to scan
        min_lines: Minimum consecutive lines to consider a block (default: 3)
        
    Returns:
        List of CommentedCodeBlock objects
    """
    blocks = []
    
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, IOError):
        return []
    
    lines = content.splitlines()
    
    # Track current block
    block_start = None
    code_like_count = 0
    consecutive_comments = 0
    
    for i, line in enumerate(lines):
        line_num = i + 1  # 1-indexed
        
        if _is_comment_line(line):
            if block_start is None:
                block_start = line_num
                consecutive_comments = 0
                code_like_count = 0
            
            consecutive_comments += 1
            if _looks_like_code(line):
                code_like_count += 1
        else:
            # End of comment block
            if block_start is not None:
                # Check if it qualifies as commented-out code
                # Require: at least min_lines AND at least 70% look like code
                code_ratio = code_like_count / consecutive_comments if consecutive_comments > 0 else 0
                if consecutive_comments >= min_lines and code_ratio >= 0.7:
                    preview_line = lines[block_start - 1].strip()
                    blocks.append(CommentedCodeBlock(
                        file=str(file_path),
                        start_line=block_start,
                        end_line=block_start + consecutive_comments - 1,
                        line_count=consecutive_comments,
                        preview=preview_line[:60] + "..." if len(preview_line) > 60 else preview_line,
                    ))
            
            # Reset
            block_start = None
            consecutive_comments = 0
            code_like_count = 0
    
    # Handle block at end of file
    if block_start is not None:
        code_ratio = code_like_count / consecutive_comments if consecutive_comments > 0 else 0
        if consecutive_comments >= min_lines and code_ratio >= 0.7:
            preview_line = lines[block_start - 1].strip()
            blocks.append(CommentedCodeBlock(
                file=str(file_path),
                start_line=block_start,
                end_line=block_start + consecutive_comments - 1,
                line_count=consecutive_comments,
                preview=preview_line[:60] + "..." if len(preview_line) > 60 else preview_line,
            ))
    
    return blocks


def scan_for_commented_code(root: Path, min_lines: int = 3) -> list[CommentedCodeBlock]:
    """
    Scan a directory for commented-out code blocks.
    
    Args:
        root: Directory to scan (or single file)
        min_lines: Minimum consecutive lines to consider a block
        
    Returns:
        List of all CommentedCodeBlock objects found
    """
    all_blocks = []
    
    for file_path in iter_code_files(root):
        blocks = find_commented_code_blocks(file_path, min_lines)
        all_blocks.extend(blocks)
    
    return all_blocks


def scan_directory(root: Path) -> list[Marker]:
    """
    Scan an entire directory for markers.
    
    This is the main function you'll call from the CLI.
    
    Args:
        root: Directory to scan (or single file)
        
    Returns:
        List of all Marker objects found
        
    Example:
        all_markers = scan_directory(Path("."))
        print(f"Found {len(all_markers)} markers")
    """
    all_markers = []
    
    for file_path in iter_code_files(root):
        markers = scan_file(file_path)
        all_markers.extend(markers)  # extend = add all items from list
    
    return all_markers


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def count_by_type(markers: list[Marker]) -> dict[str, int]:
    """
    Count markers by type (TODO, FIXME, etc.)
    
    Example:
        counts = count_by_type(markers)
        # {'TODO': 31, 'FIXME': 9, 'HACK': 5}
    """
    counts: dict[str, int] = {}
    for marker in markers:
        counts[marker.marker_type] = counts.get(marker.marker_type, 0) + 1
    return counts


def filter_by_age(markers: list[Marker], min_age_days: int) -> list[Marker]:
    """
    Filter markers to only include those older than min_age_days.
    
    Note: This requires git blame to have been run first (age_days populated).
    """
    return [m for m in markers if m.age_days >= min_age_days]


# =============================================================================
# TESTING — Run this file directly to test
# =============================================================================

if __name__ == "__main__":
    # This block runs only when you execute: python scanner.py
    # It won't run when you import this module elsewhere
    
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    # Test on current directory
    console.print("[bold]Testing scanner on current directory...[/]\n")
    
    markers = scan_directory(Path("."))
    
    if not markers:
        console.print("[yellow]No markers found![/]")
    else:
        # Show results in a table
        table = Table(title=f"Found {len(markers)} markers")
        table.add_column("Type", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Line", justify="right")
        table.add_column("Text", style="white")
        
        for m in markers[:20]:  # Show first 20 only
            table.add_row(
                m.marker_type,
                m.file,
                str(m.line),
                m.text[:50] + "..." if len(m.text) > 50 else m.text
            )
        
        console.print(table)
        
        if len(markers) > 20:
            console.print(f"\n[dim]... and {len(markers) - 20} more[/]")
        
        # Show counts by type
        console.print("\n[bold]By type:[/]")
        for marker_type, count in count_by_type(markers).items():
            console.print(f"  {marker_type}: {count}")
