cmake_minimum_required(VERSION 3.16.3)  # same as in FastDDS (U20)
include(FetchContent)

# Option to use system FastDDS instead of building from source
option(USE_SYSTEM_FASTDDS "Use system-installed FastDDS instead of building from source" OFF)
# Option to install FastDDS headers when building from source (useful for packaging)
option(INSTALL_FASTDDS_HEADERS "Install FastDDS headers when building from source" ON)

# We use a function to enforce a scoped variables creation only for FastDDS build (i.e turn off BUILD_SHARED_LIBS which is used on LRS build as well)
function(get_fastdds)

    if(USE_SYSTEM_FASTDDS)
        # Try to find system FastDDS packages
        find_package(fastrtps QUIET)
        find_package(fastcdr QUIET)
        
        if(fastrtps_FOUND AND fastcdr_FOUND)
            message(STATUS "Using system FastDDS libraries")
            
            # Create interface library that links to system packages
            add_library(dds INTERFACE)
            target_link_libraries(dds INTERFACE fastrtps fastcdr)
            
            add_definitions(-DBUILD_WITH_DDS)
            
            # Install only the interface library
            install(TARGETS dds EXPORT realsense2Targets)
            
            message(CHECK_PASS "Using system FastDDS")
            return()
        else()
            message(WARNING "System FastDDS not found, falling back to building from source")
        endif()
    endif()

    # Original FetchContent approach for building from source
    # Mark new options from FetchContent as advanced options
    mark_as_advanced(FETCHCONTENT_QUIET)
    mark_as_advanced(FETCHCONTENT_BASE_DIR)
    mark_as_advanced(FETCHCONTENT_FULLY_DISCONNECTED)
    mark_as_advanced(FETCHCONTENT_UPDATES_DISCONNECTED)

    message(CHECK_START  "Fetching fastdds...")
    list(APPEND CMAKE_MESSAGE_INDENT "  ")  # Indent outputs

    FetchContent_Declare(
      fastdds
      GIT_REPOSITORY https://github.com/eProsima/Fast-DDS.git
      # 2.10.x is eProsima's last LTS version that still supports U20
      # 2.10.4 has specific modifications based on support provided, but it has some incompatibility
      # with the way we clone (which works with v2.11+), so they made a fix and tagged it for us:
      # Once they have 2.10.5 we should move to it
      GIT_TAG        v2.10.4-realsense
      GIT_SUBMODULES ""     # Submodules will be cloned as part of the FastDDS cmake configure stage
      GIT_SHALLOW ON        # No history needed
      SOURCE_DIR ${CMAKE_BINARY_DIR}/third-party/fastdds
    )

    # Set FastDDS internal variables
    # We use cached variables so the default parameter inside the sub directory will not override the required values
    # We add "FORCE" so that is a previous cached value is set our assignment will override it.
    set(THIRDPARTY_Asio FORCE CACHE INTERNAL "" FORCE)
    set(THIRDPARTY_fastcdr FORCE CACHE INTERNAL "" FORCE)
    set(THIRDPARTY_TinyXML2 FORCE CACHE INTERNAL "" FORCE)
    set(COMPILE_TOOLS OFF CACHE INTERNAL "" FORCE)
    set(BUILD_TESTING OFF CACHE INTERNAL "" FORCE)
    set(SQLITE3_SUPPORT OFF CACHE INTERNAL "" FORCE)
    #set(ENABLE_OLD_LOG_MACROS OFF CACHE INTERNAL "" FORCE)  doesn't work
    set(FASTDDS_STATISTICS OFF CACHE INTERNAL "" FORCE)
    # Enforce NO_TLS to disable SSL: if OpenSSL is found, it will be linked to, and we don't want it!
    set(NO_TLS ON CACHE INTERNAL "" FORCE)

    # Set special values for FastDDS sub directory
    set(BUILD_SHARED_LIBS OFF)
    # CHANGED: Don't set a local install prefix - use the main project's install prefix
    # set(CMAKE_INSTALL_PREFIX ${CMAKE_BINARY_DIR}/fastdds/fastdds_install) 
    # set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR}/fastdds/fastdds_install)  

    # Get fastdds
    FetchContent_MakeAvailable(fastdds)
    
    # Mark new options from FetchContent as advanced options
    mark_as_advanced(FETCHCONTENT_SOURCE_DIR_FASTDDS)
    mark_as_advanced(FETCHCONTENT_UPDATES_DISCONNECTED_FASTDDS)

    # place FastDDS project with other 3rd-party projects
    set_target_properties(fastcdr fastrtps foonathan_memory PROPERTIES
                          FOLDER "3rd Party/fastdds")

    list(POP_BACK CMAKE_MESSAGE_INDENT) # Unindent outputs

    # CHANGED: Create an interface library that uses hardcoded library names for installation
    # This approach avoids target dependency issues by referencing static library files directly
    add_library(dds INTERFACE)
    
    # During build time, link to the actual targets
    target_link_libraries(dds INTERFACE fastcdr fastrtps foonathan_memory)
    
    # Set include directories for build and install
    target_include_directories(dds INTERFACE
        $<BUILD_INTERFACE:${CMAKE_BINARY_DIR}/third-party/fastdds/include>
        $<BUILD_INTERFACE:${CMAKE_BINARY_DIR}/third-party/fastdds/thirdparty/fastcdr/include>
        $<INSTALL_INTERFACE:include>
    )
    
    # For installation, we'll use a different approach with custom properties
    # Store the library information for the install configuration
    set_target_properties(dds PROPERTIES
        FASTDDS_FASTCDR_LIB "libfastcdr.a"
        FASTDDS_FASTRTPS_LIB "libfastrtps.a"
        FASTDDS_FOONATHAN_LIB "libfoonathan_memory.a"
    )
    
    disable_third_party_warnings(fastcdr)  
    disable_third_party_warnings(fastrtps)  

    add_definitions(-DBUILD_WITH_DDS)

    # CHANGED: Install our interface library only
    install(TARGETS dds 
            EXPORT realsense2Targets
            RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
            LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
            ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    )

    # Install FastDDS library files manually (not as targets to avoid export conflicts)
    install(FILES 
            $<TARGET_FILE:fastcdr>
            $<TARGET_FILE:fastrtps>
            $<TARGET_FILE:foonathan_memory>
            DESTINATION ${CMAKE_INSTALL_LIBDIR}
    )

    # CHANGED: Conditionally install FastDDS headers (useful for packaging)
    if(INSTALL_FASTDDS_HEADERS)
        # Install fastcdr headers
        install(DIRECTORY ${CMAKE_BINARY_DIR}/third-party/fastdds/thirdparty/fastcdr/include/
                DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
                FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
        )
        
        # Install fastdds/fastrtps headers  
        install(DIRECTORY ${CMAKE_BINARY_DIR}/third-party/fastdds/include/
                DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
                FILES_MATCHING PATTERN "*.h" PATTERN "*.hpp"
        )
    endif()

    message(CHECK_PASS "Done")
endfunction()


pop_security_flags()

# Trigger the FastDDS build
get_fastdds()

push_security_flags()