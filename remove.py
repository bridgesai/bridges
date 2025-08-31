#!/usr/bin/env python3
"""
Python Comment Remover Utility
Removes all comments from Python source files while preserving code functionality.
"""

import ast
import sys
import argparse
from pathlib import Path


def remove_comments(source_code):
    """
    Remove comments from Python source code while preserving strings and functionality.
    
    Args:
        source_code (str): The Python source code as a string
        
    Returns:
        str: The source code with comments removed
    """
    lines = source_code.split('\n')
    result = []
    in_multiline_string = False
    multiline_delimiter = None
    
    for line in lines:
        processed_line = ""
        i = 0
        in_string = False
        string_char = None
        
        while i < len(line):
            # Check for string delimiters
            if not in_multiline_string:
                # Check for triple quotes (multiline strings)
                if i + 2 < len(line) and line[i:i+3] in ['"""', "'''"]:
                    if not in_string:
                        in_multiline_string = True
                        multiline_delimiter = line[i:i+3]
                        processed_line += line[i:i+3]
                        i += 3
                        continue
                    elif line[i:i+3] == multiline_delimiter:
                        in_multiline_string = False
                        multiline_delimiter = None
                        processed_line += line[i:i+3]
                        i += 3
                        continue
                
                # Check for single/double quotes
                if line[i] in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = line[i]
                    elif line[i] == string_char:
                        in_string = False
                        string_char = None
                    processed_line += line[i]
                    i += 1
                    continue
                
                # Check for comments (only if not in string)
                if line[i] == '#' and not in_string:
                    # Check if it's a shebang line
                    if i == 0 and line.startswith('#!'):
                        processed_line = line
                        break
                    # Otherwise, we've hit a comment - stop processing this line
                    processed_line = processed_line.rstrip()
                    break
                
                processed_line += line[i]
                i += 1
            else:
                # In multiline string - check for closing delimiter
                if i + 2 < len(line) and line[i:i+3] == multiline_delimiter:
                    in_multiline_string = False
                    multiline_delimiter = None
                    processed_line += line[i:i+3]
                    i += 3
                else:
                    processed_line += line[i]
                    i += 1
        
        # Only add non-empty lines or lines that had code
        if processed_line or (not processed_line and in_multiline_string):
            result.append(processed_line)
    
    # Remove trailing empty lines
    while result and not result[-1].strip():
        result.pop()
    
    return '\n'.join(result)


def remove_docstrings(source_code):
    """
    Remove docstrings from Python source code.
    
    Args:
        source_code (str): The Python source code as a string
        
    Returns:
        str: The source code with docstrings removed
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        # If parsing fails, return as is
        return source_code
    
    # Find all docstring positions
    docstring_nodes = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and 
                isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                docstring_nodes.append(node.body[0])
    
    # Sort by line number in reverse to maintain positions when removing
    docstring_nodes.sort(key=lambda x: x.lineno, reverse=True)
    
    lines = source_code.split('\n')
    
    for node in docstring_nodes:
        # Remove the docstring lines
        start_line = node.lineno - 1
        end_line = node.end_lineno - 1 if hasattr(node, 'end_lineno') else start_line
        
        # Remove the lines
        for i in range(end_line, start_line - 1, -1):
            if i < len(lines):
                lines[i] = ""
    
    # Clean up empty lines
    result = []
    for line in lines:
        if line or (result and not result[-1] and line == ""):
            continue
        result.append(line)
    
    return '\n'.join(result)


def process_file(input_file, output_file=None, remove_docstrings_flag=False):
    """
    Process a Python file to remove comments.
    
    Args:
        input_file (str): Path to the input Python file
        output_file (str): Path to the output file (optional)
        remove_docstrings_flag (bool): Whether to also remove docstrings
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: File '{input_file}' not found.")
        return False
    
    if not input_path.suffix == '.py':
        print(f"Warning: File '{input_file}' does not have .py extension.")
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return False
    
    # Remove comments
    processed_code = remove_comments(source_code)
    
    # Optionally remove docstrings
    if remove_docstrings_flag:
        processed_code = remove_docstrings(processed_code)
    
    # Determine output file
    if output_file is None:
        output_path = input_path.with_stem(input_path.stem)
    else:
        output_path = Path(output_file)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed_code)
        print(f"Successfully processed '{input_file}' -> '{output_path}'")
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Remove comments from Python source files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s script.py                    # Creates script_no_comments.py
  %(prog)s script.py -o clean.py        # Saves to clean.py
  %(prog)s script.py --remove-docstrings # Also removes docstrings
  %(prog)s -                            # Read from stdin, write to stdout
        """
    )
    
    parser.add_argument('input', 
                        help='Input Python file (use "-" for stdin)')
    parser.add_argument('-o', '--output', 
                        help='Output file (default: input_no_comments.py, use "-" for stdout)')
    parser.add_argument('-d', '--remove-docstrings', 
                        action='store_true',
                        help='Also remove docstrings')
    
    args = parser.parse_args()
    
    # Handle stdin/stdout
    if args.input == '-':
        source_code = sys.stdin.read()
        processed_code = remove_comments(source_code)
        if args.remove_docstrings:
            processed_code = remove_docstrings(processed_code)
        
        if args.output == '-' or args.output is None:
            sys.stdout.write(processed_code)
        else:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(processed_code)
    else:
        # Process file
        process_file(args.input, args.output, args.remove_docstrings)


if __name__ == "__main__":
    main()
