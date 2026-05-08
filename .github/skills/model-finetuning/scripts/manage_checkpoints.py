#!/usr/bin/env python3
"""
Checkpoint management utilities for model finetuning.

Lists, inspects, and manages training checkpoints.
"""

import sys
from pathlib import Path
import torch


def list_checkpoints(checkpoint_dir: str = "checkpoints") -> list:
    """
    List all checkpoints sorted by training step.
    
    Args:
        checkpoint_dir: Directory containing checkpoints
        
    Returns:
        List of checkpoint paths sorted by step number
    """
    dir_path = Path(checkpoint_dir)
    
    if not dir_path.exists():
        print(f"Checkpoint directory not found: {checkpoint_dir}")
        return []
    
    checkpoints = sorted(dir_path.glob("ckpt_step_*.pt"))
    return checkpoints


def get_latest_checkpoint(checkpoint_dir: str = "checkpoints") -> tuple:
    """
    Get the latest checkpoint and its step number.
    
    Returns:
        Tuple of (checkpoint_path, step_number) or (None, 0) if no checkpoints
    """
    checkpoints = list_checkpoints(checkpoint_dir)
    
    if not checkpoints:
        return None, 0
    
    latest = checkpoints[-1]
    step = int(latest.stem.split("_")[-1])
    return latest, step


def checkpoint_info(checkpoint_path: str) -> dict:
    """
    Get information about a checkpoint.
    
    Args:
        checkpoint_path: Path to checkpoint file
        
    Returns:
        Dictionary with checkpoint metadata
    """
    path = Path(checkpoint_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    try:
        # Load checkpoint
        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        
        # Calculate total parameters
        total_params = sum(p.numel() for p in state_dict.values())
        
        # Get file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        
        # Extract step from filename
        step = int(path.stem.split("_")[-1])
        
        return {
            "path": str(path),
            "step": step,
            "file_size_mb": file_size_mb,
            "total_params": total_params,
            "layers": len([k for k in state_dict.keys() if 'transformer.h' in k])
        }
    
    except Exception as e:
        return {
            "path": str(path),
            "error": str(e)
        }


def main():
    """Command-line interface for checkpoint management."""
    if len(sys.argv) < 2:
        action = "list"
    else:
        action = sys.argv[1]
    
    if action == "list":
        print("Training Checkpoints")
        print("=" * 60)
        checkpoints = list_checkpoints()
        
        if not checkpoints:
            print("No checkpoints found.")
            return
        
        for ckpt in checkpoints:
            step = int(ckpt.stem.split("_")[-1])
            size_mb = ckpt.stat().st_size / (1024 * 1024)
            print(f"  Step {step:5d}: {ckpt.name:30s} ({size_mb:7.1f} MB)")
        
        latest, latest_step = get_latest_checkpoint()
        print("=" * 60)
        print(f"Latest checkpoint: Step {latest_step}")
        print(f"Training will resume from step {latest_step}")
    
    elif action == "latest":
        latest, step = get_latest_checkpoint()
        if latest:
            print(f"{latest}")
        else:
            print("No checkpoints found")
            sys.exit(1)
    
    elif action == "info":
        if len(sys.argv) < 3:
            print("Usage: manage_checkpoints.py info <checkpoint_path>")
            sys.exit(1)
        
        ckpt_path = sys.argv[2]
        info = checkpoint_info(ckpt_path)
        
        print(f"Checkpoint Information")
        print("=" * 60)
        for key, value in info.items():
            print(f"{key:20s}: {value}")
    
    else:
        print(f"Unknown action: {action}")
        print("Usage:")
        print("  manage_checkpoints.py list              - List all checkpoints")
        print("  manage_checkpoints.py latest            - Print latest checkpoint path")
        print("  manage_checkpoints.py info <path>       - Show checkpoint info")
        sys.exit(1)


if __name__ == "__main__":
    main()
