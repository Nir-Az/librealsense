# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 Intel Corporation. All Rights Reserved.

#test:device L500*
#test:device D400*

import pyrealsense2 as rs, os, time, tempfile, sys
from rspy import devices, log, test

cp = dp = None
color_format = depth_format = None
color_fps = depth_fps = None
color_width = depth_width = None
color_height = depth_height = None
previous_depth_frame_number = -1
previous_color_frame_number = -1
got_frames = False

dev = test.find_first_device_or_exit()
depth_sensor = dev.first_depth_sensor()
color_sensor = dev.first_color_sensor()

# finding the wanted profile settings. We want to use default settings except for color fps where we want
# the lowest value available
for p in color_sensor.profiles:
    if p.is_default() and p.stream_type() == rs.stream.color:
        color_format = p.format()
        color_fps = p.fps()
        color_width = p.as_video_stream_profile().width()
        color_height = p.as_video_stream_profile().height()
        break
for p in color_sensor.profiles:
    if p.stream_type() == rs.stream.color and p.format() == color_format and \
       p.fps() < color_fps and\
       p.as_video_stream_profile().width() == color_width and \
       p.as_video_stream_profile().height() == color_height:
        color_fps = p.fps()
for p in depth_sensor.profiles:
    if p.is_default() and p.stream_type() == rs.stream.depth:
        depth_format = p.format()
        depth_fps = p.fps()
        depth_width = p.as_video_stream_profile().width()
        depth_height = p.as_video_stream_profile().height()
        break

def got_frame():
    global got_frames
    got_frames = True

def color_frame_call_back( frame ):
    global previous_color_frame_number
    got_frame()
    test.check_frame_drops( frame, previous_color_frame_number )
    previous_color_frame_number = frame.get_frame_number()

def depth_frame_call_back( frame ):
    global previous_depth_frame_number
    got_frame()
    test.check_frame_drops( frame, previous_depth_frame_number )
    previous_depth_frame_number = frame.get_frame_number()

def restart_profiles( force_fps = None , force_low_res = False):
    """
    You can't use the same profile twice, but we need the same profile several times. So this function resets the
    profiles with the given parameters to allow quick profile creation
    """
    global cp, dp, color_sensor, depth_sensor
    global color_format, color_fps, color_width, color_height
    global depth_format, depth_fps, depth_width, depth_height

    if force_fps:
        color_fps = depth_fps = force_fps

    cp = next( p for p in color_sensor.profiles if p.fps() == color_fps
               and p.stream_type() == rs.stream.color
               and p.format() == color_format
               and ((force_low_res and p.as_video_stream_profile().width() < color_width) or
                    (not force_low_res and p.as_video_stream_profile().width() == color_width))
               and ((force_low_res and p.as_video_stream_profile().height() < color_height) or
                    (not force_low_res and p.as_video_stream_profile().height() == color_height)))

    dp = next( p for p in depth_sensor.profiles if p.fps() == depth_fps
               and p.stream_type() == rs.stream.depth
               and p.format() == p.format() == depth_format
               and p.as_video_stream_profile().width() == depth_width
               and p.as_video_stream_profile().height() == depth_height )

def stop_pipeline( pipeline ):
    if pipeline:
        try:
            pipeline.stop()
        except RuntimeError as rte:
            # if the error Occurred because the pipeline wasn't started we ignore it
            if str( rte ) != "stop() cannot be called before start()":
                test.unexpected_exception()
        except Exception:
            test.unexpected_exception()

def stop_sensor( sensor ):
    if sensor:
        # if the sensor is already closed get_active_streams returns an empty list
        if sensor.get_active_streams():
            try:
                sensor.stop()
            except RuntimeError as rte:
                if str( rte ) != "stop_streaming() failed. UVC device is not streaming!":
                    test.unexpected_exception()
            except Exception:
                test.unexpected_exception()
            sensor.close()

# create temporary folder to record to that will be deleted automatically at the end of the script
# (requires that no files are being held open inside this directory. Important to not keep any handle open to a file
# in this directory, any handle as such must be set to None)
temp_dir = tempfile.TemporaryDirectory( prefix='recordings_' )
file_name = temp_dir.name + os.sep + 'rec.bag'

################################################################################################
test.start("Trying to record and playback using pipeline interface")

cfg = pipeline = None
try:
    # creating a pipeline and recording to a file
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_record_to_file( file_name )
    pipeline.start( cfg )
    time.sleep(5)
    pipeline.stop()
    # we create a new pipeline and use it to playback from the file we just recoded to
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_device_from_file(file_name)
    pipeline.start(cfg)
    # if the record-playback worked we will get frames, otherwise the next line will timeout and throw
    pipeline.wait_for_frames()
except Exception:
    test.unexpected_exception()
finally: # we must remove all references to the file so we can use it again in the next test
    cfg = None
    stop_pipeline( pipeline )

test.finish()

################################################################################################
test.start("Trying to record and playback using sensor interface")

recorder = depth_sensor = color_sensor = playback = None
try:
    dev = test.find_first_device_or_exit()
    recorder = rs.recorder( file_name, dev )
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()

    restart_profiles()

    depth_sensor.open( dp )
    depth_sensor.start( lambda f: None )
    color_sensor.open( cp )
    color_sensor.start( lambda f: None )

    time.sleep(5)

    recorder.pause()
    recorder = None
    color_sensor.stop()
    color_sensor.close()
    depth_sensor.stop()
    depth_sensor.close()

    ctx = rs.context()
    playback = ctx.load_device( file_name )

    depth_sensor = playback.first_depth_sensor()
    color_sensor = playback.first_color_sensor()

    restart_profiles()

    depth_sensor.open( dp )
    depth_sensor.start( depth_frame_call_back )
    color_sensor.open( cp )
    color_sensor.start( color_frame_call_back )
    time.sleep(5)

    # if record and playback worked we will receive frames, the callback functions will be called and got-frames
    # will be True. If the record and playback failed it will be false
    test.check( got_frames )
except Exception:
    test.unexpected_exception()
finally: # we must remove all references to the file so we can use it again in the next test
    if recorder:
        recorder.pause()
        recorder = None
    if playback:
        playback.pause()
        playback = None
    stop_sensor( depth_sensor )
    depth_sensor = None
    stop_sensor( color_sensor )
    color_sensor = None

test.finish()

#####################################################################################################
test.start("Trying to record and playback using sensor interface with syncer")

try:
    sync = rs.syncer()
    dev = test.find_first_device_or_exit()
    recorder = rs.recorder( file_name, dev )
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()

    # When using a frames syncer we want to use same FPS on synced streams,
    # we also want low resolution in order for the recorder to succeed recording all frames with no drops
    restart_profiles( force_fps = 30 , force_low_res = True)

    depth_sensor.open( dp )
    depth_sensor.start( sync )
    color_sensor.open( cp )
    color_sensor.start( sync )

    time.sleep(5)

    recorder.pause()
    recorder = None
    color_sensor.stop()
    color_sensor.close()
    depth_sensor.stop()
    depth_sensor.close()

    ctx = rs.context()
    playback = ctx.load_device( file_name )

    depth_sensor = playback.first_depth_sensor()
    color_sensor = playback.first_color_sensor()

    restart_profiles( force_fps = 30 , force_low_res = True)

    depth_sensor.open( dp )
    depth_sensor.start( sync )
    color_sensor.open( cp )
    color_sensor.start( sync )

    # if record-playback used a syncer we should get 2 frames in most framesets
    sync_frames_cnt = 0
    for count in range( depth_fps ):
        frames = sync.wait_for_frames()
        log.d("frames.size():",frames.size())
        for frame in frames:
            log.d(frame.profile.stream_type, frame.get_frame_number() ,frame.get_timestamp())
        if frames.size() > 1:
            sync_frames_cnt += 1
    log.d(sync_frames_cnt, "synced framesets out of", depth_fps)
    test.check( sync_frames_cnt > depth_fps / 2 ) # more than 50% of the frames are synced
except Exception:
    test.unexpected_exception()
finally: # we must remove all references to the file so the temporary folder can be deleted
    if recorder:
        recorder.pause()
        recorder = None
    if playback:
        playback.pause()
        playback = None
    stop_sensor( depth_sensor )
    depth_sensor = None
    stop_sensor( color_sensor )
    color_sensor = None

test.finish()

#############################################################################################
test.print_results_and_exit()
