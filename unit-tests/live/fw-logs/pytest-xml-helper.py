# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Firmware Logger XML Helper Test

Tests XML parsing helper functionality for firmware logger.
Validates XML structure, source/module configuration, version verification,
and verbosity levels. D585S-specific because it supports module verbosity and version verification.
"""

import pytest
import pyrealsense2 as rs
import os

# Module-level markers
pytestmark = [
    pytest.mark.device("D585S"),
    pytest.mark.live
]


@pytest.fixture
def fw_logger(test_device):
    """Create firmware logger from device."""
    dev, _ = test_device
    return rs.firmware_logger(dev)


@pytest.fixture
def device_versions(test_device):
    """Get device firmware versions."""
    dev, _ = test_device
    fw_version = dev.get_info(rs.camera_info.firmware_version)
    smcu_version = dev.get_info(rs.camera_info.smcu_fw_version)
    return fw_version, smcu_version


@pytest.fixture
def temp_xml_files():
    """Create and cleanup temporary XML files."""
    files_created = []
    
    def create_file(filename, content):
        with open(filename, "w") as f:
            f.write(content)
        files_created.append(filename)
        return filename
    
    yield create_file
    
    # Cleanup
    for filepath in files_created:
        if os.path.exists(filepath):
            os.remove(filepath)


def test_empty_xml(fw_logger):
    """Test parsing empty XML string."""
    with pytest.raises(RuntimeError, match="Cannot find XML root"):
        fw_logger.init_parser("")


def test_root_not_format(fw_logger):
    """Test XML with incorrect root element."""
    xml = """<Source id="0" Name="test" />"""
    with pytest.raises(RuntimeError, match="XML root should be 'Format'"):
        fw_logger.init_parser(xml)


def test_source_validation(fw_logger, temp_xml_files):
    """Test source element validation."""
    # Create empty events file
    temp_xml_files("events.xml", "<Format/>")
    
    # Missing id attribute
    xml = """<Format>
               <Source/>
             </Format>"""
    with pytest.raises(RuntimeError, match="Can't find attribute 'id' in node Source"):
        fw_logger.init_parser(xml)
    
    # Missing Name attribute
    xml = """<Format>
               <Source id="0"/>
             </Format>"""
    with pytest.raises(RuntimeError, match="Can't find attribute 'Name' in node Source"):
        fw_logger.init_parser(xml)
    
    # Invalid source id (too high)
    xml = """<Format>
               <Source id="3" Name="invalid" />
             </Format>"""
    with pytest.raises(RuntimeError, match=r"Supporting source id 0 to 2\. Found source \(3, invalid\)"):
        fw_logger.init_parser(xml)
    
    # Invalid source id (negative)
    xml = """<Format>
               <Source id="-1" Name="invalid" />
             </Format>"""
    with pytest.raises(RuntimeError, match=r"Supporting source id 0 to 2\. Found source \(-1, invalid\)"):
        fw_logger.init_parser(xml)


def test_module_validation(fw_logger, temp_xml_files):
    """Test module element validation."""
    temp_xml_files("events.xml", "<Format/>")
    
    # Missing verbosity attribute
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="32" />
               </Source>
             </Format>"""
    with pytest.raises(RuntimeError, match="Can't find attribute 'verbosity' in node Module"):
        fw_logger.init_parser(xml)
    
    # Invalid module id (too high)
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="32" verbosity="0" />
               </Source>
             </Format>"""
    with pytest.raises(RuntimeError, match=r"Supporting module id 0 to 31\. Found module 32 in source \(0, test\)"):
        fw_logger.init_parser(xml)
    
    # Invalid module id (negative)
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="-1" verbosity="0" />
               </Source>
             </Format>"""
    with pytest.raises(RuntimeError, match=r"Supporting module id 0 to 31\. Found module -1 in source \(0, test\)"):
        fw_logger.init_parser(xml)


def test_version_verification(fw_logger, device_versions, temp_xml_files):
    """Test firmware version verification for D585S."""
    fw_version, smcu_version = device_versions
    
    # Create files with bad versions
    temp_xml_files("events.xml", "<Format version='1.2'/>")
    temp_xml_files("events2.xml", "<Format version='3.4'/>")
    
    xml = """<Format>
               <Source id="0" Name="HKR" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
               <Source id="1" Name="SMCU" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    
    expected_error = f"Source HKR expected version {fw_version} but xml file version is 1.2"
    with pytest.raises(RuntimeError, match=expected_error.replace(".", r"\.")):
        fw_logger.init_parser(xml)
    
    # Fix HKR version, fail on SMCU
    temp_xml_files("events.xml", f"<Format version='{fw_version}'/>")
    
    expected_error = f"Source SMCU expected version {smcu_version} but xml file version is 3.4"
    with pytest.raises(RuntimeError, match=expected_error.replace(".", r"\.")):
        fw_logger.init_parser(xml)
    
    # Both versions correct
    temp_xml_files("events2.xml", f"<Format version='{smcu_version}'/>")
    
    assert fw_logger.init_parser(xml), "Expected successful init with correct versions"


def test_verbosity_level(fw_logger, device_versions, temp_xml_files):
    """Test verbosity level parsing and validation."""
    fw_version, smcu_version = device_versions
    
    # Create files with correct versions
    temp_xml_files("events.xml", f"<Format version='{fw_version}'/>")
    temp_xml_files("events2.xml", f"<Format version='{smcu_version}'/>")
    
    # Numeric verbosity (range not checked, any number OK)
    xml = """<Format>
               <Source id="0" Name="HKR" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="55" />
               </Source>
               <Source id="1" Name="SMCU" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    assert fw_logger.init_parser(xml), "Expected valid numeric verbosity"
    
    # Invalid verbosity (starts with digit but not a number)
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="0A" />
               </Source>
               <Source id="1" Name="test" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    with pytest.raises(RuntimeError, match="Bad verbosity level 0A"):
        fw_logger.init_parser(xml)
    
    # Valid verbosity keywords combined
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="DEBUG|INFO|ERROR" />
               </Source>
               <Source id="1" Name="test" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="VERBOSE|FATAL" />
               </Source>
             </Format>"""
    assert fw_logger.init_parser(xml), "Expected valid keyword verbosity"
    
    # Invalid verbosity keyword
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="TEST" />
               </Source>
               <Source id="1" Name="test" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    with pytest.raises(RuntimeError, match="Illegal verbosity TEST. Expecting NONE, VERBOSE, DEBUG, INFO, WARNING, ERROR or FATAL"):
        fw_logger.init_parser(xml)


def test_module_events_file(fw_logger, device_versions, temp_xml_files):
    """Test module-specific events file path."""
    fw_version, smcu_version = device_versions
    
    temp_xml_files("events.xml", f"<Format version='{fw_version}'/>")
    temp_xml_files("events2.xml", f"<Format version='{smcu_version}'/>")
    
    xml = """<Format>
               <Source id="0" Name="test" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="0" Path="events.xml" />
               </Source>
               <Source id="1" Name="test" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    assert fw_logger.init_parser(xml), "Expected valid module events file path"


def test_live_log_messages(fw_logger, device_versions, temp_xml_files):
    """Test receiving live log messages from device."""
    fw_version, smcu_version = device_versions
    
    temp_xml_files("events.xml", f"<Format version='{fw_version}'/>")
    temp_xml_files("events2.xml", f"<Format version='{smcu_version}'/>")
    
    # Enable all modules with high verbosity
    xml = """<Format>
               <Source id="0" Name="HKR" >
                 <File Path="events.xml" />
                 <Module id="0" verbosity="63" />
                 <Module id="1" verbosity="63" />
                 <Module id="2" verbosity="63" />
                 <Module id="3" verbosity="63" />
                 <Module id="4" verbosity="63" />
                 <Module id="5" verbosity="63" />
                 <Module id="6" verbosity="63" />
                 <Module id="7" verbosity="63" />
                 <Module id="8" verbosity="63" />
                 <Module id="9" verbosity="63" />
               </Source>
               <Source id="1" Name="SMCU" >
                 <File Path="events2.xml" />
                 <Module id="0" verbosity="0" />
               </Source>
             </Format>"""
    
    assert fw_logger.init_parser(xml), "Expected successful parser init"
    
    fw_logger.start_collecting()
    message = fw_logger.create_message()
    
    # Get 10 firmware log messages
    for i in range(10):
        assert fw_logger.get_firmware_log(message), f"Expected firmware log message {i+1}"
    
    fw_logger.stop_collecting()
