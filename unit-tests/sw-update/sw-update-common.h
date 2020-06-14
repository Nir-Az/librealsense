// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2020 Intel Corporation. All Rights Reserved.
#pragma once
// Let Catch define its own main() function
#define CATCH_CONFIG_MAIN
#include "../catch/catch.hpp"

#include <easylogging++.h>
#include "log.h"
#include <librealsense2/rs.hpp>   // Include RealSense Cross Platform API

#ifdef BUILD_SHARED_LIBS
// With static linkage, ELPP is initialized by librealsense, so doing it here will
// create errors. When we're using the shared .so/.dll, the two are separate and we have
// to initialize ours if we want to use the APIs!
INITIALIZE_EASYLOGGINGPP
#endif




