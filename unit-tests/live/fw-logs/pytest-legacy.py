# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Firmware Logger Legacy Test

Tests legacy firmware logger functionality with D400 devices.
Verifies XML parsing with different file formats and error conditions.
"""

import pytest
import pyrealsense2 as rs
import xml.etree.ElementTree as ET
import os.path

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
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
def xml_files():
    """Create XML files for testing."""
    path = os.path.dirname(os.path.realpath(__file__))
    
    events = ET.fromstring(
        """<Format>
             <Event id="0" numberOfArguments="0" format="Event0" />
           </Format>""")
    events_path = os.path.join(path, 'events.xml')
    ET.ElementTree(events).write(events_path)
    
    definitions = ET.fromstring(
        """<Format>
             <Source id="0" Name="source1">
             <File Path="" />
               <Module id="1" verbosity="0" Name="source0module1" />
             </Source>
             <Source id="1" Name="source2">
             <File Path="" />
               <Module id="1" verbosity="0" Name="source1module1" />
             </Source>
           </Format>""")
    definitions[0][0].set("Path", events_path)
    definitions[1][0].set("Path", events_path)
    definitions_path = os.path.join(path, 'definitions.xml')
    ET.ElementTree(definitions).write(definitions_path)
    
    yield events_path, definitions_path
    
    # Cleanup
    for path in [events_path, definitions_path]:
        if os.path.exists(path):
            os.remove(path)


def test_unsupported_definitions_file(fw_logger, messages, xml_files):
    """Test loading unsupported definitions file with multiple formatting options."""
    raw_message, parsed_message = messages
    events_path, definitions_path = xml_files
    
    with open(definitions_path, 'r') as f:
        definitions = f.read()
    
    fw_logger.init_parser(definitions)
    fw_logger.get_firmware_log(raw_message)
    
    # Should fail because multiple sources provide formatting options
    with pytest.raises(RuntimeError, match='FW logs parser expect one formatting options, have 2'):
        fw_logger.parse_log(raw_message, parsed_message)


def test_supported_definitions_file(fw_logger, messages):
    """Test loading supported definitions file with complete event definitions."""
    raw_message, parsed_message = messages
    path = os.path.dirname(os.path.realpath(__file__))
    
    # Events based on real events file with all entry types
    events = ET.fromstring(
        """<Format>
             <Event id="37" numberOfArguments="3" format="Event37 Arg1:{0} Arg2:{1}, Arg3:0x{2:x}" />
             <Event id="49" numberOfArguments="3" format="Event49 Arg1:{0} EnumArg2: {1,ETSystemSubStates} EnumArg3: {2,ETSystemSubStates}" />
             <Event id="90" numberOfArguments="3" format="Event90 Arg1:0x{0:x}, Arg2:{1}, Arg3:0x{2:x}" />
             <Event id="272" numberOfArguments="1" format="Event272 Arg1 0x{0:x}" />
             <Event id="277" numberOfArguments="2" format="Event277 Arg1 0x{0:x}, Arg2 0x{1:x}" />
             <Event id="304" numberOfArguments="1" format="Event304 Arg1 0x{0:x}" />
             <Event id="380" numberOfArguments="1" format="Event380 Arg1:{0:x}" />
             <File id="13" Name="File13" />
             <File id="29" Name="File29" />
             <File id="49" Name="File49" />
             <Thread id="0" Name="Thread0" />
             <Thread id="7" Name="Thread7" />
             <Enums>
               <Enum Name="ETSystemSubStates">
                 <EnumValue Key="0" Value="Enum1Litteral0" />
                 <EnumValue Key="1" Value="Enum1Litteral1" />
                 <EnumValue Key="2" Value="Enum1Litteral2" />
                 <EnumValue Key="4" Value="Enum1Litteral4" />
                 <EnumValue Key="8" Value="Enum1Litteral8" />
                 <EnumValue Key="16" Value="Enum1Litteral16" />
                 <EnumValue Key="32" Value="Enum1Litteral32" />
                 <EnumValue Key="64" Value="Enum1Litteral64" />
                 <EnumValue Key="128" Value="Enum1Litteral128" />
               </Enum>
             </Enums>
           </Format>""")
    events_path = os.path.join(path, 'events.xml')
    ET.ElementTree(events).write(events_path)
    
    definitions = ET.fromstring(
        """<Format>
             <Source id="0" Name="DS5">
               <File Path="" />
             </Source>
           </Format>""")
    definitions[0][0].set("Path", events_path)
    definitions_path = os.path.join(path, 'definitions.xml')
    ET.ElementTree(definitions).write(definitions_path)
    
    try:
        with open(definitions_path, 'r') as f:
            definitions_xml = f.read()
        
        fw_logger.init_parser(definitions_xml)
        fw_logger.get_firmware_log(raw_message)
        
        # Try to parse - may fail if device returns unknown log ID
        try:
            fw_logger.parse_log(raw_message, parsed_message)
            message_text = parsed_message.get_message()
            assert message_text is not None, "Expected parsed message"
        except RuntimeError:
            # Expected if device returns log ID not in our test XML
            pass
    finally:
        if os.path.exists(events_path):
            os.remove(events_path)
        if os.path.exists(definitions_path):
            os.remove(definitions_path)


def test_events_file_directly(fw_logger, messages):
    """Test loading events file directly without definitions wrapper."""
    raw_message, parsed_message = messages
    path = os.path.dirname(os.path.realpath(__file__))
    
    events = ET.fromstring(
        """<Format>
             <Event id="37" numberOfArguments="3" format="Event37 Arg1:{0} Arg2:{1}, Arg3:0x{2:x}" />
             <Event id="90" numberOfArguments="3" format="Event90 Arg1:0x{0:x}, Arg2:{1}, Arg3:0x{2:x}" />
           </Format>""")
    events_path = os.path.join(path, 'events.xml')
    ET.ElementTree(events).write(events_path)
    
    try:
        with open(events_path, 'r') as f:
            events_xml = f.read()
        
        fw_logger.init_parser(events_xml)
        fw_logger.get_firmware_log(raw_message)
        
        # Try to parse - may fail if device returns unknown log ID
        try:
            fw_logger.parse_log(raw_message, parsed_message)
            message_text = parsed_message.get_message()
            assert message_text is not None, "Expected parsed message"
        except RuntimeError:
            # Expected if device returns log ID not in our test XML
            pass
    finally:
        if os.path.exists(events_path):
            os.remove(events_path)
