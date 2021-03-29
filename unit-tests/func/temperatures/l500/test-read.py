# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 Intel Corporation. All Rights Reserved.

#test:device L500*

import pyrealsense2 as rs
#from rspy.timer import Timer
from rspy import test
#import time

# Test reading l500 device temperatures with/without streaming

# RS2_OPTION_LLD_TEMPERATURE:
# RS2_OPTION_MC_TEMPERATURE:
# RS2_OPTION_MA_TEMPERATURE:
# RS2_OPTION_APD_TEMPERATURE:
# RS2_OPTION_HUMIDITY_TEMPERATURE:

#MAX_TIME_TO_WAIT_FOR_FRAMES = 10 # [sec]
#NUMBER_OF_FRAMES_BEFORE_CHECK = 50

devices = test.find_devices_by_product_line_or_exit(rs.product_line.L500)
device = devices[0]

#wait_frames_timer = Timer(MAX_TIME_TO_WAIT_FOR_FRAMES)

test.start("Read temperatures while not streaming")
device.

device.
depth_sensor.open(dp)
depth_sensor.start(frames_counter)
wait_frames_timer.start()

# we wait for first NUMBER_OF_FRAMES_BEFORE_CHECK frames OR MAX_TIME_TO_WAIT_FOR_FRAMES seconds
while (not wait_frames_timer.has_expired() 
    and n_depth_frame + n_ir_frame < NUMBER_OF_FRAMES_BEFORE_CHECK):
    time.sleep(1)

if wait_frames_timer.has_expired():
    print(str(NUMBER_OF_FRAMES_BEFORE_CHECK) + " frames did not arrived at "+ str(MAX_TIME_TO_WAIT_FOR_FRAMES) + " seconds , abort...")
    test.fail()
else:
    test.check(n_depth_frame >= NUMBER_OF_FRAMES_BEFORE_CHECK)
    test.check_equal(n_ir_frame, 0)

depth_sensor.stop()
depth_sensor.close()

time.sleep(1) # Allow time to ensure no more frame callbacks after stopping sensor

test.finish()

test.print_results_and_exit()