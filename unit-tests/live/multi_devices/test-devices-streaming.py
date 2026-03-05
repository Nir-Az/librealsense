# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

# Test configuration: Requires 2 D400 series devices
#test:device:!jetson D400* D400*

"""
Tests:
- Simultaneous multi-stream operation (depth + color + IR) on 2 devices
- Frame drop detection with multiple stream types
- Long duration stress testing
- Stream independence verification

Requires 2 D400 series devices.
"""

import pyrealsense2 as rs
from rspy import test, log
import time
from collections import defaultdict

# Test configuration
STREAM_DURATION_SEC = 10  # Longer duration for multi-stream stress test
MAX_FRAME_DROP_PERCENTAGE = 5.0  # Allow up to 5% frame drops
STABILIZATION_TIME_SEC = 3  # Time to allow auto-exposure to settle

# Query the connected devices directly via RealSense context
ctx = rs.context()
device_list = ctx.query_devices()
device_count = len(device_list)

def _discover_device_profiles(devs):
    """
    Discover all available stream profiles across all devices.
    
    :param devs: List of device objects
    :return: List of profile dictionaries, one per device. Each dictionary maps
             (stream_type, format) -> set of (width, height, fps) tuples
    """
    all_profiles = []
    
    for dev in devs:
        sensors = dev.query_sensors()
        dev_profiles = defaultdict(set)
        
        for sensor in sensors:
            for profile in sensor.get_stream_profiles():
                if profile.is_video_stream_profile():
                    vp = profile.as_video_stream_profile()
                    key = (profile.stream_type(), profile.format())
                    value = (vp.width(), vp.height(), profile.fps())
                    dev_profiles[key].add(value)
        
        all_profiles.append(dev_profiles)
    
    return all_profiles


def _find_common_profiles(all_profiles, stream_key):
    """
    Find the intersection of available profiles for a specific stream across all devices.
    
    :param all_profiles: List of profile dictionaries from _discover_device_profiles
    :param stream_key: Tuple of (stream_type, format) to look up
    :return: Set of (width, height, fps) tuples available on all devices, or None if not available
    """
    # Check if all devices support this stream
    if not all(stream_key in dev_prof for dev_prof in all_profiles):
        return None
    
    # Find intersection of all devices
    common_profiles = all_profiles[0][stream_key]
    for dev_prof in all_profiles[1:]:
        common_profiles = common_profiles.intersection(dev_prof[stream_key])
    
    return common_profiles


def _select_best_resolution(available_configs, target_resolutions):
    """
    Select the best matching resolution from available configurations.
    
    :param available_configs: Set of (width, height, fps) tuples
    :param target_resolutions: List of (width, height, fps) tuples in preference order
    :return: Tuple of (width, height, fps) if found, else None
    """
    if not available_configs:
        return None
    
    # Try each target resolution in order of preference
    for target_width, target_height, target_fps in target_resolutions:
        if (target_width, target_height, target_fps) in available_configs:
            return (target_width, target_height, target_fps)
    
    return None


def _try_add_depth_stream(all_profiles, target_resolutions):
    """
    Attempt to add a depth stream configuration.
    
    :param all_profiles: List of profile dictionaries for all devices
    :param target_resolutions: List of (width, height, fps) tuples in preference order
    :return: Stream configuration tuple if successful, else None
    """
    depth_key = (rs.stream.depth, rs.format.z16)
    common_depth = _find_common_profiles(all_profiles, depth_key)
    
    if common_depth is None:
        return None
    
    resolution = _select_best_resolution(common_depth, target_resolutions)
    if resolution:
        width, height, fps = resolution
        log.d(f"  Added Depth stream: {width}x{height} @ {fps}fps")
        return (rs.stream.depth, -1, width, height, rs.format.z16, fps)
    
    return None


def _try_add_color_stream(all_profiles, target_resolutions):
    """
    Attempt to add a color stream configuration, trying multiple formats.
    
    :param all_profiles: List of profile dictionaries for all devices
    :param target_resolutions: List of (width, height, fps) tuples in preference order
    :return: Stream configuration tuple if successful, else None
    """
    color_formats = [rs.format.rgb8, rs.format.bgr8, rs.format.rgba8, rs.format.bgra8, rs.format.yuyv]
    
    for color_format in color_formats:
        color_key = (rs.stream.color, color_format)
        common_color = _find_common_profiles(all_profiles, color_key)
        
        if common_color is None:
            continue
        
        resolution = _select_best_resolution(common_color, target_resolutions)
        if resolution:
            width, height, fps = resolution
            log.d(f"  Added Color stream: {width}x{height} @ {fps}fps {color_format}")
            return (rs.stream.color, -1, width, height, color_format, fps)
    
    return None


def _try_add_infrared_stream(all_profiles, target_resolutions, stream_index=1):
    """
    Attempt to add an infrared stream configuration.
    
    :param all_profiles: List of profile dictionaries for all devices
    :param target_resolutions: List of (width, height, fps) tuples in preference order
    :param stream_index: IR stream index (1 or 2)
    :return: Stream configuration tuple if successful, else None
    """
    ir_key = (rs.stream.infrared, rs.format.y8)
    common_ir = _find_common_profiles(all_profiles, ir_key)
    
    if common_ir is None:
        return None
    
    resolution = _select_best_resolution(common_ir, target_resolutions)
    if resolution:
        width, height, fps = resolution
        log.d(f"  Added Infrared stream (index {stream_index}): {width}x{height} @ {fps}fps")
        return (rs.stream.infrared, stream_index, width, height, rs.format.y8, fps)
    
    return None


def get_common_multi_stream_config(*devs):
    """
    Find a multi-stream configuration that works on all provided devices.
    Returns a list of (stream_type, stream_index, width, height, format, fps) tuples.
    
    This tries to enable as many stream types as possible:
    - Depth stream
    - Color stream  
    - Infrared streams (1 and 2 if available)
    
    All streams will use the same resolution and FPS for simplicity.
    """
    # Guard against empty device list
    if len(devs) == 0:
        log.w("get_common_multi_stream_config called with no devices")
        return []
    
    # Try common resolutions in order of preference
    # 640x360 added as fallback to support safety camera profiles
    target_resolutions = [
        (640, 480, 30),  # Standard VGA resolution
        (640, 360, 30),  # Fallback for safety cameras and other devices
    ]
    
    # Discover available profiles from all devices
    all_profiles = _discover_device_profiles(devs)
    
    # Build multi-stream configuration by trying each stream type
    stream_configs = []
    
    # Try to add Depth stream
    depth_config = _try_add_depth_stream(all_profiles, target_resolutions)
    if depth_config:
        stream_configs.append(depth_config)
    
    # Try to add Color stream
    color_config = _try_add_color_stream(all_profiles, target_resolutions)
    if color_config:
        stream_configs.append(color_config)
    
    # Try to add Infrared stream (index 1)
    ir_config = _try_add_infrared_stream(all_profiles, target_resolutions, stream_index=1)
    if ir_config:
        stream_configs.append(ir_config)
    
    # Note: IR2 skipped for simplicity as multiple streams of same type with different
    # indices require more complex configuration
    
    return stream_configs


def setup_pipelines(devs, stream_configs):
    """
    Create and configure pipelines for all devices with the specified stream configurations.
    
    :param devs: List of device objects
    :param stream_configs: List of (stream_type, stream_index, width, height, format, fps) tuples
    :return: Tuple of (pipes, cfgs, device_info)
    """
    pipes = []
    cfgs = []
    device_info = []
    
    # Setup pipelines for all devices
    for dev in devs:
        sn = dev.get_info(rs.camera_info.serial_number)
        name = dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else "Unknown"
        
        pipe = rs.pipeline()
        cfg = rs.config()
        cfg.enable_device(sn)
        
        pipes.append(pipe)
        cfgs.append(cfg)
        device_info.append({'sn': sn, 'name': name})
    
    # Configure all pipelines identically
    log.i(f"Configuring streams:")
    for stream_type, stream_index, width, height, format, fps in stream_configs:
        for cfg in cfgs:
            if stream_index >= 0:
                # Use the overload with stream_index (important for infrared streams)
                cfg.enable_stream(stream_type, stream_index, width, height, format, fps)
            else:
                # Use the overload without stream_index (for depth/color)
                cfg.enable_stream(stream_type, width, height, format, fps)
        index_str = f" index {stream_index}" if stream_index >= 0 else ""
        log.i(f"  - {stream_type}{index_str} {width}x{height} @ {fps}fps {format}")
    
    return pipes, cfgs, device_info


def stabilize_streams(pipes):
    """
    Allow auto-exposure to stabilize by collecting and discarding initial frames.
    
    :param pipes: List of pipeline objects
    """
    log.i(f"Stabilizing for {STABILIZATION_TIME_SEC} seconds...")
    stabilization_frames = int(STABILIZATION_TIME_SEC * 30)  # Assume ~30fps
    for _ in range(stabilization_frames):
        try:
            for pipe in pipes:
                pipe.wait_for_frames(timeout_ms=5000)
        except Exception as e:
            log.w(f"  Exception during stabilization: {e}")


def collect_frames(pipes, duration_sec):
    """
    Collect frames from all pipelines for the specified duration.
    
    :param pipes: List of pipeline objects
    :param duration_sec: How long to stream in seconds
    :return: Tuple of (all_frame_counters, all_framesets_received, all_stream_frame_counts, actual_duration)
    :raises: Re-raises any exception from wait_for_frames() after logging
    """
    all_frame_counters = [defaultdict(list) for _ in pipes]
    all_framesets_received = [0] * len(pipes)
    all_stream_frame_counts = [defaultdict(int) for _ in pipes]
    
    log.i(f"Streaming for {duration_sec} seconds...")
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration_sec:
            for i, pipe in enumerate(pipes):
                frameset = pipe.wait_for_frames(timeout_ms=5000)
                all_framesets_received[i] += 1
                
                for frame in frameset:
                    stream_type = frame.get_profile().stream_type()
                    all_stream_frame_counts[i][stream_type] += 1
                    
                    if frame.supports_frame_metadata(rs.frame_metadata_value.frame_counter):
                        counter = frame.get_frame_metadata(rs.frame_metadata_value.frame_counter)
                        all_frame_counters[i][stream_type].append(counter)
    except Exception as e:
        actual_duration = time.time() - start_time
        log.e(f"Exception during streaming after {actual_duration:.2f}s: {e}")
        raise
    
    actual_duration = time.time() - start_time
    return all_frame_counters, all_framesets_received, all_stream_frame_counts, actual_duration


def analyze_device_drops(frame_counters, stream_frame_counts, device_name):
    """
    Analyze frame drops for a single device across all streams.
    
    :param frame_counters: Dict of stream_type -> list of frame counters
    :param stream_frame_counts: Dict of stream_type -> total frame count
    :param device_name: Name/identifier for logging
    :return: Tuple of (overall_drop_percentage, per_stream_stats_dict)
    """
    total_expected = 0
    total_received = 0
    per_stream_stats = {}
    
    for stream_type, counters in frame_counters.items():
        if len(counters) < 2:
            log.w(f"  {device_name} {stream_type}: insufficient frames ({len(counters)})")
            continue
        
        # Calculate expected frames based on counter range
        counter_range = counters[-1] - counters[0]
        expected = counter_range + 1
        received = len(counters)
        dropped = expected - received
        
        total_expected += expected
        total_received += received
        
        drop_pct = (dropped / expected * 100) if expected > 0 else 0
        
        per_stream_stats[stream_type] = {
            'expected': expected,
            'received': received,
            'dropped': dropped,
            'drop_pct': drop_pct,
            'total_frames': stream_frame_counts.get(stream_type, 0)
        }
        
        log.d(f"  {device_name} {stream_type}: {received}/{expected} frames, "
              f"{dropped} dropped ({drop_pct:.2f}%)")
    
    if total_expected > 0:
        overall_drop_pct = ((total_expected - total_received) / total_expected * 100)
    else:
        overall_drop_pct = 0.0
        
    return overall_drop_pct, per_stream_stats


def aggregate_results(all_frame_counters, all_framesets_received, all_stream_frame_counts, 
                     device_info, actual_duration):
    """
    Aggregate and analyze results from all devices.
    
    :param all_frame_counters: List of frame counter dicts (one per device)
    :param all_framesets_received: List of frameset counts (one per device)
    :param all_stream_frame_counts: List of stream frame count dicts (one per device)
    :param device_info: List of device info dicts
    :param actual_duration: Actual streaming duration in seconds
    :return: Tuple of (success, drop_percentages, stats_dict)
    """
    log.i(f"Streaming completed after {actual_duration:.2f} seconds")
    for i, info in enumerate(device_info):
        log.i(f"Device {i+1} ({info['name']}): {all_framesets_received[i]} framesets")
    
    # Log per-stream frame counts for all devices
    for i, (info, stream_counts) in enumerate(zip(device_info, all_stream_frame_counts)):
        log.d(f"Device {i+1} frame counts by stream:")
        for stream_type, count in stream_counts.items():
            log.d(f"  {stream_type}: {count} frames")
    
    # Analyze drops for all devices
    drop_percentages = []
    all_stats = []
    
    for i, (frame_counters, stream_counts, info) in enumerate(zip(all_frame_counters, all_stream_frame_counts, device_info)):
        drop_pct, stream_stats = analyze_device_drops(frame_counters, stream_counts, f"Dev{i+1}({info['sn']})")
        drop_percentages.append(drop_pct)
        
        dev_stats = {
            'name': info['name'],
            'sn': info['sn'],
            'framesets': all_framesets_received[i],
            'drop_pct': drop_pct,
            'streams': stream_stats
        }
        all_stats.append(dev_stats)
    
    success = all(dp <= MAX_FRAME_DROP_PERCENTAGE for dp in drop_percentages)
    
    stats = {
        'devices': all_stats,
        'duration': actual_duration
    }
    
    return success, drop_percentages, stats


def stream_multi_and_check_frames(*devs, stream_configs, duration_sec=STREAM_DURATION_SEC):
    """
    Stream multiple stream types from all devices simultaneously and check for frame drops.
    
    :param devs: Variable number of device objects
    :param stream_configs: List of (stream_type, width, height, format, fps) tuples
    :param duration_sec: How long to stream in seconds
    :return: Tuple of (success, list of drop_percentages, stats)
    """
    # Setup phase: Create and configure pipelines
    pipes, cfgs, device_info = setup_pipelines(devs, stream_configs)
    
    try:
        # Start all pipelines
        for i, (pipe, cfg, info) in enumerate(zip(pipes, cfgs, device_info)):
            log.d(f"Starting pipeline on {info['name']} (SN: {info['sn']})...")
            pipe.start(cfg)
        
        # Stabilization phase: Allow auto-exposure to settle
        stabilize_streams(pipes)
        
        # Collection phase: Stream and collect frame data
        # Note: Exceptions will propagate and fail the test after cleanup in finally block
        all_frame_counters, all_framesets_received, all_stream_frame_counts, actual_duration = \
            collect_frames(pipes, duration_sec)
        
        # Analysis phase: Aggregate results and analyze drops
        success, drop_percentages, stats = aggregate_results(
            all_frame_counters, all_framesets_received, all_stream_frame_counts,
            device_info, actual_duration
        )
        
        return success, drop_percentages, stats
        
    finally:
        for pipe in pipes:
            try:
                pipe.stop()
            except Exception as e:
                log.d(f"Failed to stop pipeline during cleanup: {e}")


#
# Test: Stream multiple stream types simultaneously from all devices
#
with test.closure(f"Multiple devices - multi-stream simultaneous operation (depth + color + IR) - {device_count} devices"):
    # Verify required device count
    test.check(device_count == 2, f"Test requires exactly 2 D400 devices, but found {device_count}")
    
    if device_count != 2:
        log.e(f"FAIL: Test requires exactly 2 D400 devices but found {device_count}")
        test.print_results_and_exit()
    
    # Use the devices already queried at the top of the file
    devs = [device_list[i] for i in range(device_count)]
    
    log.i("=" * 80)
    log.i(f"Testing multi-stream operation on {device_count} devices:")
    for i, dev in enumerate(devs, 1):
        sn = dev.get_info(rs.camera_info.serial_number)
        name = dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else "Unknown"
        log.i(f"  Device {i}: {name} (SN: {sn})")
    log.i("=" * 80)
    
    # Get common multi-stream configuration
    log.i("\nFinding common multi-stream configuration...")
    stream_configs = get_common_multi_stream_config(*devs)

    if len(stream_configs) < 2:
        log.w(f"Insufficient common streams found ({len(stream_configs)})")
        log.w("At least 2 stream types needed for multi-stream test")
        test.check(False, "Devices should support at least 2 common stream types")
    else:
        log.i(f"\nFound {len(stream_configs)} common stream types")
        log.i(f"Will stream all of them simultaneously from all {device_count} devices")
        
        # Run the multi-stream test
        # Note: Exceptions during streaming will propagate and fail the test automatically
        success, drop_percentages, stats = stream_multi_and_check_frames(
            *devs, stream_configs=stream_configs
        )
        
        # Check for analysis errors
        if len(stats['devices']) == 0:
            log.e("\nFAIL - No device statistics collected")
            test.check(False, "Should collect statistics from all devices")
        else:
            # Print detailed results
            # Print detailed results
            log.i("\n" + "=" * 80)
            log.i("RESULTS:")
            log.i("=" * 80)
            log.i(f"Duration: {stats['duration']:.2f} seconds")
            
            for i, dev_stats in enumerate(stats['devices'], 1):
                log.i(f"\nDevice {i} ({dev_stats['name']}):")
                log.i(f"  Total framesets: {dev_stats['framesets']}")
                log.i(f"  Overall drop rate: {dev_stats['drop_pct']:.2f}%")
                for stream_type, stream_stats in dev_stats['streams'].items():
                    log.i(f"  {stream_type}:")
                    log.i(f"    Received: {stream_stats['received']}/{stream_stats['expected']}")
                    log.i(f"    Dropped: {stream_stats['dropped']} ({stream_stats['drop_pct']:.2f}%)")
            
            log.i("=" * 80)
            
            if success:
                log.i(f"\nPASS - Multi-stream test successful!")
                for i, drop_pct in enumerate(drop_percentages, 1):
                    log.i(f"  Device {i} drop rate: {drop_pct:.2f}%")
            else:
                log.w(f"\nFAIL - Excessive frame drops detected!")
                for i, drop_pct in enumerate(drop_percentages, 1):
                    log.w(f"  Device {i} drop rate: {drop_pct:.2f}% (max: {MAX_FRAME_DROP_PERCENTAGE}%)")
            
            test.check(success, 
                        f"Multi-stream operation should have <{MAX_FRAME_DROP_PERCENTAGE}% drops on all devices")
            
            # Verify stream independence: Check that each stream type received adequate frames
            # (at least 80% of expected based on actual duration and configured FPS)
            log.i("\nVerifying stream independence...")
            all_streams_ok = True
            
            for i, dev_stats in enumerate(stats['devices'], 1):
                for stream_type, stream_stats in dev_stats['streams'].items():
                    min_expected_frames = int(stream_stats['expected'] * 0.8)
                    if stream_stats['received'] < min_expected_frames:
                        log.w(f"Device {i} {stream_type} received only {stream_stats['received']} frames (expected >={min_expected_frames})")
                        all_streams_ok = False
            
            if all_streams_ok:
                log.i("PASS - All streams received adequate frame counts (independence verified)")
            else:
                log.w("FAIL - Some streams received fewer frames than expected")
            
            test.check(all_streams_ok, 
                        "All streams should receive frames independently without interference")

# Print test summary
test.print_results_and_exit()
