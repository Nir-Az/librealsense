import sys
import os

# Add py directory
sys.path.insert(0, 'py')

from rspy import repo

pyrs_dir = repo.find_pyrs_dir()
print(f'pyrs_dir: {pyrs_dir}')

if pyrs_dir:
    print(f'Files in pyrs_dir:')
    for f in os.listdir(pyrs_dir):
        if 'pyrealsense' in f.lower():
            print(f'  {f}')
    
    sys.path.insert(1, pyrs_dir)
    print(f'sys.path: {sys.path[:3]}')
    
    try:
        import pyrealsense2 as rs
        print(f'✓ Successfully imported pyrealsense2')
        ctx = rs.context()
        print(f'✓ Context created: {ctx}')
        print(f'✓ Devices: {len(ctx.devices)}')
    except Exception as e:
        print(f'✗ Failed to import: {e}')
        import traceback
        traceback.print_exc()
else:
    print('pyrs_dir not found')
