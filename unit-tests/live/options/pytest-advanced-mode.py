# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Advanced Mode Test

Tests advanced mode functionality including:
- Visual presets
- Depth control settings
- RSM, RAU, color control
- Various advanced mode parameters
"""

import pytest
import pyrealsense2 as rs
from rspy import tests_wrapper as tw

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live
]


@pytest.fixture
def advanced_mode_device(test_device):
    """Setup device with advanced mode verified."""
    dev, ctx = test_device
    
    tw.start_wrapper(dev)
    
    # Verify advanced mode support
    am_dev = rs.rs400_advanced_mode(dev)
    assert am_dev is not None, "Advanced mode not supported"
    assert am_dev.is_enabled(), "Advanced mode should be enabled"
    
    yield dev, am_dev
    
    tw.stop_wrapper(dev)
    
    tw.stop_wrapper(dev)


def test_visual_preset_support(advanced_mode_device):
    """Test visual preset support and default preset."""
    dev, am_dev = advanced_mode_device
    depth_sensor = dev.first_depth_sensor()
    
    assert depth_sensor.supports(rs.option.visual_preset), \
        "Cameras with advanced mode should support visual preset"
    
    # Set and verify default preset
    depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.default))
    assert depth_sensor.get_option(rs.option.visual_preset) == rs.rs400_visual_preset.default


def test_depth_control(advanced_mode_device):
    """Test depth control settings."""
    dev, am_dev = advanced_mode_device
    
    dc = am_dev.get_depth_control()
    dc.plusIncrement = 11
    dc.minusDecrement = 12
    dc.deepSeaMedianThreshold = 13
    dc.scoreThreshA = 14
    dc.scoreThreshB = 22
    dc.textureDifferenceThreshold = 23
    dc.textureCountThreshold = 24
    dc.deepSeaSecondPeakThreshold = 25
    dc.deepSeaNeighborThreshold = 26
    dc.lrAgreeThreshold = 27
    
    am_dev.set_depth_control(dc)
    new_dc = am_dev.get_depth_control()
    
    assert new_dc.plusIncrement == 11
    assert new_dc.minusDecrement == 12
    assert new_dc.deepSeaMedianThreshold == 13
    assert new_dc.scoreThreshA == 14
    assert new_dc.scoreThreshB == 22
    assert new_dc.textureDifferenceThreshold == 23
    assert new_dc.textureCountThreshold == 24
    assert new_dc.deepSeaSecondPeakThreshold == 25
    assert new_dc.deepSeaNeighborThreshold == 26
    assert new_dc.lrAgreeThreshold == 27


def test_rsm(advanced_mode_device):
    """Test RSM (RealSense Mode) settings."""
    dev, am_dev = advanced_mode_device
    
    rsm = am_dev.get_rsm()
    rsm.diffThresh = 3.4
    rsm.sloRauDiffThresh = 1.1875  # 1.2 was out of step
    rsm.rsmBypass = 1
    rsm.removeThresh = 123
    
    am_dev.set_rsm(rsm)
    new_rsm = am_dev.get_rsm()
    
    assert abs(new_rsm.diffThresh - 3.4) < 0.01
    assert abs(new_rsm.sloRauDiffThresh - 1.1875) < 0.01
    assert new_rsm.removeThresh == 123


def test_rau(advanced_mode_device):
    """Test RAU support vector control."""
    dev, am_dev = advanced_mode_device
    
    rau = am_dev.get_rau_support_vector_control()
    rau.minWest = 1
    rau.minEast = 2
    rau.minWEsum = 3
    rau.minNorth = 0
    rau.minSouth = 1
    rau.minNSsum = 6
    rau.uShrink = 1
    rau.vShrink = 2
    
    am_dev.set_rau_support_vector_control(rau)
    new_rau = am_dev.get_rau_support_vector_control()
    
    assert new_rau.minWest == 1
    assert new_rau.minEast == 2
    assert new_rau.minWEsum == 3
    assert new_rau.minNorth == 0
    assert new_rau.minSouth == 1
    assert new_rau.minNSsum == 6
    assert new_rau.uShrink == 1
    assert new_rau.vShrink == 2


def test_color_control(advanced_mode_device):
    """Test color control settings."""
    dev, am_dev = advanced_mode_device
    
    color_control = am_dev.get_color_control()
    color_control.disableSADColor = 1
    color_control.disableRAUColor = 0
    color_control.disableSLORightColor = 1
    color_control.disableSLOLeftColor = 0
    color_control.disableSADNormalize = 1
    
    am_dev.set_color_control(color_control)
    new_color_control = am_dev.get_color_control()
    
    assert new_color_control.disableSADColor == 1
    assert new_color_control.disableRAUColor == 0
    assert new_color_control.disableSLORightColor == 1
    assert new_color_control.disableSLOLeftColor == 0
    assert new_color_control.disableSADNormalize == 1


def test_rau_thresholds_control(advanced_mode_device):
    """Test RAU thresholds control."""
    dev, am_dev = advanced_mode_device
    
    rau_tc = am_dev.get_rau_thresholds_control()
    rau_tc.rauDiffThresholdRed = 10
    rau_tc.rauDiffThresholdGreen = 20
    rau_tc.rauDiffThresholdBlue = 30
    
    am_dev.set_rau_thresholds_control(rau_tc)
    new_rau_tc = am_dev.get_rau_thresholds_control()
    
    assert new_rau_tc.rauDiffThresholdRed == 10
    assert new_rau_tc.rauDiffThresholdGreen == 20
    assert new_rau_tc.rauDiffThresholdBlue == 30


def test_slo_color_thresholds_control(advanced_mode_device):
    """Test SLO color thresholds control."""
    dev, am_dev = advanced_mode_device
    
    slo_ctc = am_dev.get_slo_color_thresholds_control()
    slo_ctc.diffThresholdRed = 1
    slo_ctc.diffThresholdGreen = 2
    slo_ctc.diffThresholdBlue = 3
    
    am_dev.set_slo_color_thresholds_control(slo_ctc)
    new_slo_ctc = am_dev.get_slo_color_thresholds_control()
    
    assert new_slo_ctc.diffThresholdRed == 1
    assert new_slo_ctc.diffThresholdGreen == 2
    assert new_slo_ctc.diffThresholdBlue == 3


def test_slo_penalty_control(advanced_mode_device):
    """Test SLO penalty control."""
    dev, am_dev = advanced_mode_device
    
    slo_pc = am_dev.get_slo_penalty_control()
    slo_pc.sloK1Penalty = 1
    slo_pc.sloK2Penalty = 2
    slo_pc.sloK1PenaltyMod1 = 3
    slo_pc.sloK2PenaltyMod1 = 4
    slo_pc.sloK1PenaltyMod2 = 5
    slo_pc.sloK2PenaltyMod2 = 6
    
    am_dev.set_slo_penalty_control(slo_pc)
    new_slo_pc = am_dev.get_slo_penalty_control()
    
    assert new_slo_pc.sloK1Penalty == 1
    assert new_slo_pc.sloK2Penalty == 2
    assert new_slo_pc.sloK1PenaltyMod1 == 3
    assert new_slo_pc.sloK2PenaltyMod1 == 4
    assert new_slo_pc.sloK1PenaltyMod2 == 5
    assert new_slo_pc.sloK2PenaltyMod2 == 6


def test_hdad(advanced_mode_device):
    """Test HDAD settings."""
    dev, am_dev = advanced_mode_device
    
    hdad = am_dev.get_hdad()
    hdad.lambdaCensus = 1.1
    hdad.lambdaAD = 2.2
    hdad.ignoreSAD = 1
    
    am_dev.set_hdad(hdad)
    new_hdad = am_dev.get_hdad()
    
    assert abs(new_hdad.lambdaCensus - 1.1) < 0.01
    assert abs(new_hdad.lambdaAD - 2.2) < 0.01
    assert new_hdad.ignoreSAD == 1


def test_color_correction(advanced_mode_device):
    """Test color correction matrix."""
    dev, am_dev = advanced_mode_device
    
    cc = am_dev.get_color_correction()
    cc.colorCorrection1 = -0.1
    cc.colorCorrection2 = -0.2
    cc.colorCorrection3 = -0.3
    cc.colorCorrection4 = -0.4
    cc.colorCorrection5 = -0.5
    cc.colorCorrection6 = -0.6
    cc.colorCorrection7 = -0.7
    cc.colorCorrection8 = -0.8
    cc.colorCorrection9 = -0.9
    cc.colorCorrection10 = 1.1
    cc.colorCorrection11 = 1.2
    cc.colorCorrection12 = 1.3
    
    am_dev.set_color_correction(cc)
    new_cc = am_dev.get_color_correction()
    
    assert abs(new_cc.colorCorrection1 - (-0.1)) < 0.01
    assert abs(new_cc.colorCorrection2 - (-0.2)) < 0.01
    assert abs(new_cc.colorCorrection3 - (-0.3)) < 0.01
    assert abs(new_cc.colorCorrection4 - (-0.4)) < 0.01
    assert abs(new_cc.colorCorrection5 - (-0.5)) < 0.01
    assert abs(new_cc.colorCorrection6 - (-0.6)) < 0.01
    assert abs(new_cc.colorCorrection7 - (-0.7)) < 0.01
    assert abs(new_cc.colorCorrection8 - (-0.8)) < 0.01
    assert abs(new_cc.colorCorrection9 - (-0.9)) < 0.01
    assert abs(new_cc.colorCorrection10 - 1.1) < 0.01
    assert abs(new_cc.colorCorrection11 - 1.2) < 0.01
    assert abs(new_cc.colorCorrection12 - 1.3) < 0.01


def test_ae_control(advanced_mode_device):
    """Test AE control settings."""
    dev, am_dev = advanced_mode_device
    
    aec = am_dev.get_ae_control()
    aec.meanIntensitySetPoint = 1234
    
    am_dev.set_ae_control(aec)
    new_aec = am_dev.get_ae_control()
    
    assert new_aec.meanIntensitySetPoint == 1234


def test_depth_table(advanced_mode_device):
    """Test depth table settings."""
    dev, am_dev = advanced_mode_device
    
    dt = am_dev.get_depth_table()
    dt.depthUnits = 100
    dt.depthClampMin = 10
    dt.depthClampMax = 200
    dt.disparityMode = 1
    dt.disparityShift = 2
    
    am_dev.set_depth_table(dt)
    new_dt = am_dev.get_depth_table()
    
    assert new_dt.depthUnits == 100
    assert new_dt.depthClampMin == 10
    assert new_dt.depthClampMax == 200
    assert new_dt.disparityMode == 1
    assert new_dt.disparityShift == 2


def test_census(advanced_mode_device):
    """Test census settings."""
    dev, am_dev = advanced_mode_device
    
    census = am_dev.get_census()
    census.uDiameter = 5
    census.vDiameter = 6
    
    am_dev.set_census(census)
    new_census = am_dev.get_census()
    
    assert new_census.uDiameter == 5
    assert new_census.vDiameter == 6


def test_amp_factor(advanced_mode_device):
    """Test amp factor settings."""
    dev, am_dev = advanced_mode_device
    
    af = am_dev.get_amp_factor()
    af.a_factor = 0.123
    
    am_dev.set_amp_factor(af)
    new_af = am_dev.get_amp_factor()
    
    assert abs(new_af.a_factor - 0.123) < 0.01


def test_return_to_default_preset(advanced_mode_device):
    """Test returning to default preset."""
    dev, am_dev = advanced_mode_device
    depth_sensor = dev.first_depth_sensor()
    
    depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.default))
    assert depth_sensor.get_option(rs.option.visual_preset) == rs.rs400_visual_preset.default
