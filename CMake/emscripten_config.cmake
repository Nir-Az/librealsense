message(STATUS "Setting Emscripten configurations")

# compiling with MinGW
macro(os_set_flags)
    set(CMAKE_POSITION_INDEPENDENT_CODE OFF)
    set(CMAKE_C_FLAGS   "${CMAKE_C_FLAGS}   -pedantic -g -D_DEFAULT_SOURCE")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pedantic -g -Wno-missing-field-initializers")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-switch -Wno-multichar -Wsequence-point -Wformat -Wformat-security")
    set(BACKEND RS2_USE_WMF_BACKEND)
    set(BUILD_EXAMPLES OFF)
    set(BUILD_GRAPHICAL_EXAMPLES OFF )
    set(IMPORT_DEPTH_CAM_FW OFF)
    set(CHECK_FOR_UPDATES OFF)
    set(BUILD_WITH_TM2 OFF)
endmacro()

# compiling with Windows
#set(CMAKE_C_COMPILER emcc)
#set(CMAKE_CXX_COMPILER "C:/Work/Tools/emscripten/emsdk/upstream/emscripten/em++.bat")
#include(CMake/windows_config.cmake)
#set(BACKEND RS2_USE_WMF_BACKEND)
#set(BUILD_EXAMPLES OFF)
#set(BUILD_GRAPHICAL_EXAMPLES OFF )
#set(IMPORT_DEPTH_CAM_FW OFF)
#set(CHECK_FOR_UPDATES OFF)
#set(BUILD_WITH_TM2 OFF)

macro(os_target_config)
endmacro()
