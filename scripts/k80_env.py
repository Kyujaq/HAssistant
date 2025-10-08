#!/usr/bin/env python3
"""
K80 GPU Auto-discovery Helper
Outputs shell commands to export GPU device variables
"""
import sys
import subprocess
import re


def detect_k80_gpus():
    """Detect Tesla K80 GPUs and return their indices"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True
        )
        
        k80_indices = []
        for line in result.stdout.strip().split('\n'):
            if 'K80' in line or 'Tesla' in line:
                match = re.match(r'^\s*(\d+)', line)
                if match:
                    k80_indices.append(int(match.group(1)))
        
        return k80_indices
    
    except subprocess.CalledProcessError:
        print("Error: nvidia-smi not found or failed", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error detecting GPUs: {e}", file=sys.stderr)
        return []


def main():
    k80_gpus = detect_k80_gpus()
    
    if not k80_gpus:
        print("# No Tesla K80 GPUs detected", file=sys.stderr)
        print("# Available GPUs:", file=sys.stderr)
        try:
            subprocess.run(["nvidia-smi", "--query-gpu=index,name", "--format=csv"])
        except:
            pass
        sys.exit(1)
    
    # Assign GPUs
    if len(k80_gpus) >= 2:
        screen_gpu = k80_gpus[0]
        room_gpu = k80_gpus[1]
    else:
        screen_gpu = k80_gpus[0]
        room_gpu = k80_gpus[0]
        print(f"# Warning: Only one K80 found. Both workers will share GPU {screen_gpu}", file=sys.stderr)
    
    # Output shell commands
    print(f"export VISION_SCREEN_CUDA_DEVICE={screen_gpu}")
    print(f"export VISION_ROOM_CUDA_DEVICE={room_gpu}")
    
    print(f"# Screen worker -> GPU {screen_gpu}", file=sys.stderr)
    print(f"# Room worker   -> GPU {room_gpu}", file=sys.stderr)


if __name__ == "__main__":
    main()
