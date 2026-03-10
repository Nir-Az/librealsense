# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 Intel Corporation. All Rights Reserved.

#test:device D400*
#test:donotrun:!nightly

import os, platform, shutil, subprocess, sys
from rspy import log, repo, test

#############################################################################################
#

# the tests in the realsense-viewer-tests executable are defined along the tester file itself at
# tools/realsense-viewer/tests/. Using the --auto flag allows us to run all tests one by one.
# If we want to run a specific test / test group, we can use the -r flag

# On headless Linux (no $DISPLAY), wraps the executable with xvfb-run for a virtual display.
# On some Windows machines OpenGL is not available, so we use Mesa's software renderer to provide it
# (install https://github.com/pal1000/mesa-dist-win/releases to C:\mesa\).
cmd = []
env = None
if platform.system() == 'Linux' and not os.environ.get( 'DISPLAY' ):
    xvfb = shutil.which( 'xvfb-run' )
    if not xvfb:
        log.f( 'No DISPLAY and xvfb-run not found; install xvfb (apt install xvfb)' )
        test.print_results_and_exit()
    log.d( 'no DISPLAY set; using xvfb-run with software rendering' )
    cmd += [xvfb, '-a']
    env = dict( os.environ, LIBGL_ALWAYS_SOFTWARE='1' )

test.start( "Run realsense-viewer GUI tests" )
viewer_tests = repo.find_built_exe( 'tools/realsense-viewer', 'realsense-viewer-tests' )
test.check( viewer_tests )
if viewer_tests:
    if platform.system() == 'Windows':
        mesa_dir = r'C:\mesa'
        exe_dir = os.path.dirname( viewer_tests )
        for dll in ['opengl32.dll', 'libgallium_wgl.dll']:
            src = os.path.join( mesa_dir, dll )
            dst = os.path.join( exe_dir, dll )
            if os.path.isfile( src ) and not os.path.isfile( dst ):
                log.d( 'copying Mesa', dll, 'to', exe_dir )
                shutil.copy2( src, dst )
    cmd += [viewer_tests, '--auto']
    log.d( 'running:', *cmd )
    p = subprocess.Popen( cmd,
                          stdout=None,
                          stderr=subprocess.PIPE,
                          env=env )
    # Mesa's software renderer emits a benign GL error for glCopyTexImage2D; filter it out
    for line in p.stderr:
        if b'glCopyTexImage2D' not in line:
            sys.stderr.buffer.write( line )
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
