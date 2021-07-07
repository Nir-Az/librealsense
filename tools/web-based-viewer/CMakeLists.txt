# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 Intel Corporation. All Rights Reserved.
#  minimum required cmake version: 3.1.0
cmake_minimum_required(VERSION 3.1.0)

project(RealsenseToolsRealSenseWebViewer)

add_executable(rs-web-based-viewer rs-dummy.cpp)
set_target_properties (rs-web-based-viewer PROPERTIES
    FOLDER Tools
)

install(
    TARGETS
    rs-web-based-viewer
    RUNTIME DESTINATION
    ${CMAKE_INSTALL_BINDIR}
)

