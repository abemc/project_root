#!/usr/bin/env python3
"""
Dataset validation script for model finetuning.

Validates JSONL dataset format, structure, and data integrity before training.
"""

import json
import sys
from pathlib import Path
from typing import Tuple, List
import tiktoken

def validate_dataset(dataset_path: str, verbose: bool = True) -> Tuple[int, int, List[str]]:
    """
    Validate JSONL dataset format and structure.
    
    Args:
        dataset_path: Path to dataset.jsonl
        verbose: Print detailed output
        
    Returns:
        Tuple of (valid_lines, invalid_lines, errors)
    """
    path = Path(dataset_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    
    if verbose:
        file_size_mb = path.stat().st_size / (1024 * 1024)
        print(f"Dataset file: {path}")
        print(f"File size: {file_size_mb:.2f} MB")
        print("-" * 60)
    
    valid_lines = 0
    invalid_lines = 0
    errors = []
    total_tokens = 0
    
    # Initialize tokenizer
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        if verbose:
            print(f"Warning: Could not initialize tokenizer: {e}")
        enc = None
    
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)
                
                # Validate required fields
                if "text" not in data:
                    invalid_lines += 1
                    errors.append(f"Line {line_num}: missing 'text' field")
                    continue
                
                text = data["text"]
                if not isinstance(text, str):
                    invalid_lines += 1
                    errors.append(f"Line {line_num}: 'text' is not a string (type: {type(text).__name__})")
                    continue
                
                if len(text) == 0:
                    invalid_lines += 1
                    errors.append(f"Line {line_num}: 'text' is empty")
                    continue
                
                valid_lines += 1
                
                # Count tokens if tokenizer is available
                if enc:
                    tokens = enc.encode(text)
                    total_tokens += len(tokens)
                    total_tokens += 1  # Add EOT token
                    
            except json.JSONDecodeError as e:
                invalid_lines += 1
                errors.append(f"Line {line_num}: JSON decode error: {str(e)[:50]}")
            except Exception as e:
                invalid_lines += 1
                errors.append(f"Line {line_num}: Unexpected error: {str(e)[:50]}")
    
    # Print results
    if verbose:
        print(f"✓ Valid lines: {valid_lines:,}")
        print(f"✗ Invalid lines: {invalid_lines:,}")
        
        if total_tokens > 0:
            print(f"✓ Estimated tokens: {total_tokens:,}")
        
        print("-" * 60)
        
        if errors:
            print(f"\n⚠ Found {len(errors)} errors. Showing first 5:\n")
            for err in errors[:5]:
                print(f"  • {err}")
            
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more errors")
        else:
            print("\n✓ Dataset validation passed! No errors found.")
        
        # Warnings
        if invalid_lines > 0:
            invalid_pct = (invalid_lines / (valid_lines + invalid_lines)) * 100
            print(f"\n⚠ Warning: {invalid_pct:.1f}% of lines are invalid")
            if invalid_pct > 5:
                print("  Consider regenerating the dataset if error rate is high")
        
        print("-" * 60)
    
    return valid_lines, invalid_lines, errors


def main():
    """Command-line interface for dataset validation."""
    if len(sys.argv) < 2:
        # Use default path
        dataset_path = "/mnt/d/rag_corpus/dataset.jsonl"
    else:
        dataset_path = sys.argv[1]
    
    try:
        valid, invalid, errors = validate_dataset(dataset_path, verbose=True)
        
        # Exit code: 0 if valid, 1 if any errors
        sys.exit(0 if invalid == 0 else 1)
        
    except FileNotFoundError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
