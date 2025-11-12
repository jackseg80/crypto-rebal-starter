#!/usr/bin/env python3
"""
Extract all unique emojis from frontend files (HTML and JS)
"""
import re
import glob
from pathlib import Path
from collections import Counter

def is_emoji(char):
    """Check if a character is an emoji"""
    code = ord(char)
    # Common emoji ranges
    return (
        0x1F300 <= code <= 0x1F9FF or  # Misc Symbols and Pictographs, Emoticons, etc.
        0x2600 <= code <= 0x26FF or    # Misc symbols
        0x2700 <= code <= 0x27BF or    # Dingbats
        0xFE00 <= code <= 0xFE0F or    # Variation Selectors
        0x1F000 <= code <= 0x1F02F or  # Mahjong Tiles
        0x1F0A0 <= code <= 0x1F0FF or  # Playing Cards
        0x1F100 <= code <= 0x1F64F or  # Enclosed characters
        0x1F680 <= code <= 0x1F6FF or  # Transport and Map
        0x1F900 <= code <= 0x1F9FF or  # Supplemental Symbols
        0x1FA00 <= code <= 0x1FA6F or  # Extended pictographs
        0x1FA70 <= code <= 0x1FAFF or  # Symbols and Pictographs Extended-A
        0x2300 <= code <= 0x23FF or    # Misc Technical
        0x2B50 == code or              # Star
        0x2705 == code or              # Check mark
        0x274C == code or              # Cross mark
        0x2753 <= code <= 0x2755 or    # Question marks
        0x2795 <= code <= 0x2797 or    # Plus/minus
        0x203C == code or              # Double exclamation
        0x2049 == code                 # Exclamation question
    )

def extract_emojis_from_file(filepath):
    """Extract all emojis from a file"""
    emojis = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            for char in content:
                if is_emoji(char):
                    emojis.append(char)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return emojis

def main():
    # Get all HTML and JS files in static/
    html_files = list(Path('static').rglob('*.html'))
    js_files = list(Path('static').rglob('*.js'))

    all_files = html_files + js_files
    print(f"Scanning {len(all_files)} files...")

    # Extract all emojis
    all_emojis = []
    file_emoji_map = {}

    for filepath in all_files:
        emojis = extract_emojis_from_file(filepath)
        if emojis:
            all_emojis.extend(emojis)
            file_emoji_map[str(filepath)] = emojis

    # Count and deduplicate
    emoji_counter = Counter(all_emojis)
    unique_emojis = sorted(emoji_counter.keys(), key=lambda x: -emoji_counter[x])

    print(f"\nFound {len(all_emojis)} total emojis")
    print(f"Found {len(unique_emojis)} unique emojis")

    # Write results
    with open('emoji_list.txt', 'w', encoding='utf-8') as f:
        # List separated by spaces
        f.write(' '.join(unique_emojis))

    # Write detailed report
    with open('emoji_report.txt', 'w', encoding='utf-8') as f:
        f.write("EMOJI REPORT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total emojis found: {len(all_emojis)}\n")
        f.write(f"Unique emojis: {len(unique_emojis)}\n\n")
        f.write("Emojis by frequency:\n")
        f.write("-" * 80 + "\n")
        for emoji in unique_emojis:
            count = emoji_counter[emoji]
            f.write(f"{emoji}  -  {count} occurrences\n")

        f.write("\n\n")
        f.write("Files containing emojis:\n")
        f.write("-" * 80 + "\n")
        for filepath, emojis in sorted(file_emoji_map.items()):
            f.write(f"\n{filepath}: {len(emojis)} emojis\n")
            unique_in_file = sorted(set(emojis), key=lambda x: -emojis.count(x))
            f.write(f"  {' '.join(unique_in_file)}\n")

    print("\nFiles created:")
    print("  - emoji_list.txt (space-separated list for AI)")
    print("  - emoji_report.txt (detailed report)")
    print("\nUnique emojis found:")
    print(' '.join(unique_emojis))

if __name__ == '__main__':
    main()
