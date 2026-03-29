# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 Intel Corporation. All Rights Reserved.

#test:device D400*
#test:donotrun:!nightly
#test:donotrun:!gui

import os, platform, re, shutil, subprocess, sys, threading, time
from rspy import log, repo, test

ansi_escape = re.compile( rb'\x1b\[[0-9;]*m' )
frame_prefix = re.compile( rb'\[\d{4}\] ' )

#############################################################################################
#

# the tests in the realsense-viewer-tests executable are defined along the tester file itself at
# tools/realsense-viewer/tests/. Using the --auto flag allows us to run all tests one by one.
# If we want to run a specific test / test group, we can use the -r flag

test.start( "Run realsense-viewer GUI tests" )
viewer_tests = repo.find_built_exe( 'tools/realsense-viewer', 'realsense-viewer-tests' )
test.check( viewer_tests )

cmd = []
env = None

# On headless Linux (no $DISPLAY), wraps the executable with xvfb-run for a virtual display.
if platform.system() == 'Linux' and not os.environ.get( 'DISPLAY' ):
    xvfb = shutil.which( 'xvfb-run' )
    if not xvfb:
        log.f( 'No DISPLAY and xvfb-run not found; install xvfb (apt install xvfb)' )
        test.print_results_and_exit()
    log.d( 'no DISPLAY set; using xvfb-run with software rendering' )
    cmd += [xvfb, '-a']
    env = dict( os.environ, LIBGL_ALWAYS_SOFTWARE='1' )

# On some Windows machines OpenGL is not available, so we use Mesa's software renderer to provide it
# On those machines we expect Mesa's OpenGL implementation dll files under C:\mesa
# URL: https://github.com/pal1000/mesa-dist-win/releases
if viewer_tests and platform.system() == 'Windows':
    mesa_dir = r'C:\mesa'
    exe_dir = os.path.dirname( viewer_tests )
    for dll in ['opengl32.dll', 'libgallium_wgl.dll']:
        src = os.path.join( mesa_dir, dll )
        dst = os.path.join( exe_dir, dll )
        if os.path.isfile( src ) and not os.path.isfile( dst ):
            log.d( 'copying Mesa', dll, 'to', exe_dir )
            shutil.copy2( src, dst )

if viewer_tests:
    cmd += [viewer_tests, '--auto']
    log.d( 'running:', *cmd )
    # Strip ANSI color codes and replace frame counts with elapsed time
    def print_stdout( pipe ):
        test_start = time.monotonic()
        for line in pipe:
            line = ansi_escape.sub( b'', line )
            m = frame_prefix.search( line )
            if m:
                elapsed = time.monotonic() - test_start
                line = line[:m.start()] + f'[{elapsed:5.1f}s] '.encode() + line[m.end():]
            sys.stdout.buffer.write( line )

    # Filter Mesa glCopyTexImage2D warnings that are irrelevant with software rendering
    def print_stderr( pipe ):
        for line in pipe:
            if b'glCopyTexImage2D' not in line:
                sys.stderr.buffer.write( line )

    p = subprocess.Popen( cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          env=env )
    stdout_thread = threading.Thread( target=print_stdout, args=( p.stdout, ) )
    stderr_thread = threading.Thread( target=print_stderr, args=( p.stderr, ) )
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()
    p.wait()
    if p.returncode != 0:
        log.e( 'realsense-viewer-tests exited with code', p.returncode )
    test.check( p.returncode == 0 )
else:
    log.e( 'realsense-viewer-tests was not found!' )
    import sys
    log.d( 'sys.path=\n    ' + '\n    '.join( sys.path ) )

test.finish()
#
#############################################################################################
test.print_results_and_exit()
