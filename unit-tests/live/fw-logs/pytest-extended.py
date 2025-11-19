# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Firmware Logger Extended Test

Tests extended firmware logger functionality with real event files and multiple sources.
Tests XML parsing, message collection, and D585S-specific version handling.
"""

import pytest
import pyrealsense2 as rs
import xml.etree.ElementTree as ET
import os.path
import tempfile

# Module-level markers
pytestmark = [
    pytest.mark.device("D500*"),
    pytest.mark.device_exclude("D555"),
    pytest.mark.live
]


@pytest.fixture
def fw_logger(test_device):
    """Create firmware logger from device."""
    dev, _ = test_device
    logger = dev.as_firmware_logger()
    assert logger, "Failed to create firmware logger"
    return logger


@pytest.fixture
def messages(fw_logger):
    """Create raw and parsed message objects."""
    raw_message = fw_logger.create_message()
    parsed_message = fw_logger.create_parsed_message()
    return raw_message, parsed_message


@pytest.fixture
def xml_files(test_device):
    """Create XML files for testing."""
    dev, _ = test_device
    # Get working directory
    path = os.path.dirname(os.path.realpath(__file__))
    
    # Events based on real events file
    events_real = ET.fromstring(
        """<Format>
             <Event id="50" numberOfArguments="0" format="Event50" />
             <Event id="52" numberOfArguments="3" format="Event52 Arg1:{0}, Arg2:{1}, Arg3:{2}" />
             <Event id="59" numberOfArguments="1" format="Event59 Arg1:{0}" />
             <Event id="2549" numberOfArguments="0" format="Event2549" />
             <File id="5" Name="File5" />
             <Module id="2" Name="Module2" />
           </Format>""")
    events_real_path = os.path.join(path, 'events_real.xml')
    ET.ElementTree(events_real).write(events_real_path)
    
    events_dummy = ET.fromstring(
        """<Format>
             <Event id="1" numberOfArguments="0" format="Event1" />
             <Event id="2" numberOfArguments="0" format="Event2" />
             <File id="1" Name="File1" />
             <File id="2" Name="File2" />
             <Module id="1" Name="Module1" />
             <Module id="2" Name="Module2" />
           </Format>""")
    events_dummy_path = os.path.join(path, 'events_dummy.xml')
    ET.ElementTree(events_dummy).write(events_dummy_path)
    
    # Expected events are from source1 module2, set verbosity to "enable all"
    definitions = ET.fromstring(
        """<Format>
             <Source id="0" Name="source1">
             <File Path="" />
               <Module id="1" verbosity="0" Name="source1module1" Path=""/>
               <Module id="2" verbosity="63" Name="source1module2" />
             </Source>
             <Source id="1" Name="source2">
             <File Path="" />
               <Module id="1" verbosity="0" Name="source2module1" />
               <Module id="2" verbosity="0" Name="source2module2" />
             </Source>
             <Source id="2" Name="source3">
             <File Path="" />
               <Module id="1" verbosity="0" Name="source3module1" />
               <Module id="2" verbosity="0" Name="source3module2" />
             </Source>
           </Format>""")
    definitions[0][0].set("Path", events_real_path)
    definitions[1][0].set("Path", events_dummy_path)
    definitions[2][0].set("Path", events_dummy_path)
    definitions_path = os.path.join(path, 'definitions.xml')
    ET.ElementTree(definitions).write(definitions_path)
    
    # Handle D585S file versions
    device_name = dev.get_info(rs.camera_info.name)
    if "D585S" in device_name:
        fw_version = dev.get_info(rs.camera_info.firmware_version)
        tree = ET.parse(events_real_path)
        root = tree.getroot()
        assert root.tag == 'Format', f"Expected root tag 'Format', got '{root.tag}'"
        root.set('version', fw_version)
        tree.write(events_real_path)
        
        smcu_version = dev.get_info(rs.camera_info.smcu_fw_version)
        tree = ET.parse(events_dummy_path)
        root = tree.getroot()
        assert root.tag == 'Format', f"Expected root tag 'Format', got '{root.tag}'"
        root.set('version', smcu_version)
        tree.write(events_dummy_path)
    
    yield events_real_path, events_dummy_path, definitions_path
    
    # Cleanup
    for path in [events_real_path, events_dummy_path, definitions_path]:
        if os.path.exists(path):
            os.remove(path)


def test_firmware_logger_extended(fw_logger, messages, xml_files):
    """Test extended firmware logger with real event files."""
    raw_message, parsed_message = messages
    events_real_path, events_dummy_path, definitions_path = xml_files
    
    # Test loading unsupported definitions file (events file instead of definitions)
    with open(events_real_path, 'r') as f:
        events_xml = f.read()
    
    with pytest.raises(RuntimeError, match="Did not find 'Source' node with id 0"):
        fw_logger.init_parser(events_xml)
    
    # Load supported definitions file
    with open(definitions_path, 'r') as f:
        definitions = f.read()
    
    fw_logger.init_parser(definitions)
    fw_logger.start_collecting()
    
    # Get and parse a log entry
    fw_logger.get_firmware_log(raw_message)
    fw_logger.parse_log(raw_message, parsed_message)
    
    # Verify we got a message
    message_text = parsed_message.get_message()
    assert message_text, "Expected parsed message content"
    
    fw_logger.stop_collecting()
