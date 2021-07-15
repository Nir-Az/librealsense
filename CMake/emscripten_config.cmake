message(STATUS "Setting Emscripten configurations")

macro(os_set_flags)
    set(CMAKE_POSITION_INDEPENDENT_CODE OFF)
    set(CMAKE_C_FLAGS   "${CMAKE_C_FLAGS}   -pedantic -g -D_DEFAULT_SOURCE")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pedantic -g -Wno-missing-field-initializers")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-switch -Wno-multichar -Wsequence-point -Wformat -Wformat-security")
endmacro()

macro(os_target_config)
endmacro()
