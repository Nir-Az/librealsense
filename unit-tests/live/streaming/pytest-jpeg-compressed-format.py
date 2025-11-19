# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
JPEG Compressed Format Test

Tests JPEG (MJPEG) format support on D555 devices.
Verifies that JPEG streams can be captured and converted to RGB8.

Note: Requires DDS mode.
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device("D555"),
    pytest.mark.dds,  # Only run when -m dds is specified
    pytest.mark.live
]


@pytest.fixture
def jpeg_profile(test_device):
    """Find JPEG profile if supported."""
    dev, ctx = test_device
    
    # Need raw format conversion context for JPEG
    raw_ctx = rs.context({"format-conversion": "raw"})
    devices = raw_ctx.query_devices()
    
    if len(devices) == 0:
        pytest.skip("No devices found in raw format context")
    
    color_sensor = devices[0].first_color_sensor()
    
    # Find JPEG profile
    jpeg_profile = None
    for p in color_sensor.profiles:
        if p.stream_type() == rs.stream.color and p.format() == rs.format.mjpeg:
            jpeg_profile = p
            break
    
    if not jpeg_profile:
        pytest.skip("Device does not support JPEG streaming")
    
    yield jpeg_profile


def test_jpeg_format_support(jpeg_profile):
    """Verify device supports JPEG streaming format."""
    assert jpeg_profile is not None
    assert jpeg_profile.format() == rs.format.mjpeg
    assert jpeg_profile.stream_type() == rs.stream.color


def test_jpeg_streaming_and_conversion(jpeg_profile):
    """Test streaming JPEG and converting to RGB8."""
    pipeline = rs.pipeline()
    config = rs.config()
    
    vp = jpeg_profile.as_video_stream_profile()
    
    # Enable JPEG stream but request RGB8 conversion
    config.enable_stream(
        rs.stream.color,
        vp.stream_index(),
        vp.width(),
        vp.height(),
        rs.format.rgb8,  # JPEG is converted to RGB8
        vp.fps()
    )
    
    try:
        pipeline.start(config)
        
        # Capture 10 frames to verify streaming works
        for i in range(10):
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            
            assert color_frame, f"Failed to get color frame {i}"
            assert color_frame.get_profile().format() == rs.format.rgb8, \
                "Frame should be converted to RGB8"
    
    finally:
        pipeline.stop()
