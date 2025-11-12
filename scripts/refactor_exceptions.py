#!/usr/bin/env python3
"""
Script to automatically refactor broad Exception handlers to use decorators

Usage:
    python refactor_exceptions.py <input_file> <output_file>
"""

import re
import sys
from pathlib import Path


def find_function_with_try_except(lines, start_idx):
    """
    Find a function definition with try/except and extract:
    - Function definition (with decorators)
    - Try block content
    - Except block content
    - Fallback data (if any)
    """
    # Find function definition
    func_match = None
    func_start = start_idx

    for i in range(start_idx, -1, -1):
        line = lines[i]
        if re.match(r'^(async )?def \w+', line):
            func_start = i
            func_match = line
            break
        if not line.strip() or line.strip().startswith(('#', '"""', "'''")):
            continue
        if line.strip().startswith('@'):
            continue
        if re.match(r'^class ', line):
            break

    if not func_match:
        return None

    # Find decorators above function
    decorators = []
    for i in range(func_start - 1, -1, -1):
        line = lines[i].rstrip()
        if line.strip().startswith('@'):
            decorators.insert(0, line)
        elif line.strip() and not line.strip().startswith('#'):
            break

    # Find except block
    except_idx = start_idx
    except_content = []
    indent_level = len(lines[except_idx]) - len(lines[except_idx].lstrip())

    # Check if it's a graceful fallback or HTTPException raise
    is_http_exception = False
    has_fallback = False
    fallback_dict = None

    i = except_idx + 1
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            except_content.append(line)
            i += 1
            continue

        line_indent = len(line) - len(line.lstrip())
        if line_indent <= indent_level and line.strip():
            break

        except_content.append(line)

        # Check for HTTPException
        if 'HTTPException' in line or 'raise ' in line:
            is_http_exception = True

        # Check for return with dict (fallback)
        if 'return {' in line:
            has_fallback = True

        i += 1

    return {
        'decorators': decorators,
        'func_start': func_start,
        'func_line': func_match,
        'except_idx': except_idx,
        'except_end': i,
        'is_http_exception': is_http_exception,
        'has_fallback': has_fallback,
        'except_content': except_content
    }


def analyze_fallback(except_content):
    """Extract fallback data from except block"""
    # Look for patterns like: return {"success": False, ...}
    fallback_keys = []
    for line in except_content:
        if 'return {' in line or '"' in line or "'" in line:
            # Try to extract keys
            keys = re.findall(r'["\'](\w+)["\']:\s*', line)
            fallback_keys.extend(keys)

    return fallback_keys


def refactor_file(input_file, output_file):
    """Refactor a Python file to use error handling decorators"""

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find all "except Exception" occurrences
    exception_indices = []
    for i, line in enumerate(lines):
        if re.search(r'except\s+Exception\s+as\s+\w+:', line):
            exception_indices.append(i)

    print(f"Found {len(exception_indices)} 'except Exception' statements")

    # Process file
    new_lines = []
    skip_until = -1
    added_import = False

    for i, line in enumerate(lines):
        # Skip lines that are part of removed except blocks
        if i < skip_until:
            continue

        # Add import after existing imports
        if not added_import and (line.startswith('from ') or line.startswith('import ')):
            # Check if this is the last import
            if i + 1 < len(lines) and not (lines[i + 1].startswith('from ') or lines[i + 1].startswith('import ')):
                new_lines.append(line)
                new_lines.append('from shared.error_handlers import handle_api_errors\n')
                added_import = True
                continue

        # Check if this is an except Exception line
        if i in exception_indices:
            func_info = find_function_with_try_except(lines, i)

            if func_info:
                # Extract function without try/except
                func_start = func_info['func_start']
                except_idx = func_info['except_idx']
                except_end = func_info['except_end']

                # Find try statement
                try_idx = None
                for j in range(except_idx - 1, func_start, -1):
                    if lines[j].strip().startswith('try:'):
                        try_idx = j
                        break

                if try_idx:
                    # Analyze fallback
                    fallback_keys = analyze_fallback(func_info['except_content'])

                    # Build fallback dict string
                    if fallback_keys:
                        # Create a simple fallback with common keys
                        common_fallbacks = {
                            'data': '[]',
                            'items': '[]',
                            'results': '{}',
                            'status': '{}',
                            'pipeline_status': '{}',
                            'loaded_models': '0',
                            'count': '0',
                            'success': 'False'
                        }
                        fallback_parts = []
                        for key in fallback_keys:
                            if key in common_fallbacks:
                                fallback_parts.append(f'"{key}": {common_fallbacks[key]}')

                        if fallback_parts:
                            fallback_str = '{' + ', '.join(fallback_parts) + '}'
                        else:
                            fallback_str = None
                    else:
                        fallback_str = None

                    # Add decorator
                    indent = ' ' * (len(func_info['decorators'][0]) - len(func_info['decorators'][0].lstrip())) if func_info['decorators'] else ''
                    if fallback_str:
                        decorator = f'{indent}@handle_api_errors(fallback={fallback_str}, include_traceback=True)\n'
                    else:
                        decorator = f'{indent}@handle_api_errors(include_traceback=True)\n'

                    # Write decorators + new decorator + function
                    for dec in func_info['decorators']:
                        new_lines.append(dec + '\n' if not dec.endswith('\n') else dec)
                    new_lines.append(decorator)
                    new_lines.append(func_info['func_line'])

                    # Write function body (skip try: and except blocks)
                    func_body_indent = len(lines[try_idx + 1]) - len(lines[try_idx + 1].lstrip())
                    base_indent = len(lines[func_start]) - len(lines[func_start].lstrip())

                    for j in range(try_idx + 1, except_idx):
                        body_line = lines[j]
                        # Remove one level of indentation (from try block)
                        if body_line.strip():
                            current_indent = len(body_line) - len(body_line.lstrip())
                            if current_indent >= func_body_indent:
                                new_lines.append(' ' * (current_indent - (func_body_indent - base_indent - 4)) + body_line.lstrip())
                            else:
                                new_lines.append(body_line)
                        else:
                            new_lines.append(body_line)

                    # Skip until end of except block
                    skip_until = except_end
                    continue

        new_lines.append(line)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"Refactored file written to: {output_file}")
    print(f"Reduced from {len(exception_indices)} broad exceptions to decorator-based handling")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python refactor_exceptions.py <input_file> <output_file>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    refactor_file(input_file, output_file)
