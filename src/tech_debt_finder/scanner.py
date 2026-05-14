"""
scanner.py — Find code rot markers in files

This module walks through files and finds:
- TODO, FIXME, HACK, TEMP, XXX comments
- (Later: commented-out code blocks)

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
# Our strategy: Look for common comment prefixes BEFORE the TODO marker.

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
# Each pattern: COMMENT_PREFIX + anything + MARKER + optional colon/space + rest of line
MARKER_PATTERNS = [
    re.compile(
        prefix + r'.*?' + MARKER_WORDS + r'[\s:]*(.*)$',
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
