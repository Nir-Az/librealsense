# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 Intel Corporation. All Rights Reserved.
#  minimum required cmake version: 3.1.0
cmake_minimum_required(VERSION 3.1.0)

#set(EmscriptenRoot "C:/Work/Tools/emscripten/emsdk/upstream/emscripten")
#message(STATUS "DEBUG - found emscripten at ${EmscriptenRoot} - temporary hard coded path")
#set(CMAKE_TOOLCHAIN_FILE "${EmscriptenRoot}/cmake/Modules/Platform/Emscripten.cmake")

project(RealsenseToolsRealSenseWebViewer)
message( STATUS "Adding emscripten_dummy" )

execute_process(COMMAND emcmake cmake -DEMSCRIPTEN_ROOT_PATH=C:/Work/Tools/emscripten/emsdk/upstream/emscripten .
    WORKING_DIRECTORY "${CMAKE_BINARY_DIR}/wrappers/wasm"
)

#SET(CMAKE_EXECUTABLE_SUFFIX ".js")
add_executable(rs-web-based-viewer rs-dummy.cpp)
set_target_properties (rs-web-based-viewer PROPERTIES
    FOLDER Wrappers
)

if(JS_ONLY)
	message(STATUS "Setting compilation target to native JavaScript")
    set(CMAKE_EXECUTABLE_SUFFIX ".js")
	set_target_properties(rs-web-based-viewer PROPERTIES LINK_FLAGS "-s ERROR_ON_UNDEFINED_SYMBOLS=0 WASM=0")
else(JS_ONLY)
	message(STATUS "Setting compilation target to WASM")
	#set_target_properties(rs-web-based-viewer PROPERTIES LINK_FLAGS "-s WASM=1 --bind --js-library jslinker.js")
    #set(DCMAKE_CXX_COMPILER emcc)
    #set(CMAKE_CXX_COMPILER "C:/Work/Tools/emscripten/emsdk/upstream/emscripten/em++.bat")
    set(CMAKE_CXX_FLAGS ${CMAKE_CXX_FLAGS} "-std=c++11 -s WASM=1")
    set(CMAKE_EXECUTABLE_SUFFIX ".wasm.js")
    #set_target_properties(rs-web-based-viewer PROPERTIES LINK_FLAGS "-s WASM=1 -s EXPORTED_FUNCTIONS='[_main]'")
endif(JS_ONLY)

install(
    TARGETS
    rs-web-based-viewer
    RUNTIME DESTINATION
    ${CMAKE_INSTALL_BINDIR}
)

