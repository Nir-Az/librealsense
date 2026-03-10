// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "viewer-test-helpers.h"
#include "imgui_te_context.h"


// Start all sensors simultaneously and verify all streams are alive
VIEWER_TEST( "streaming", "stream_all_sensors" )
{
    IM_CHECK( !test.device_models.empty() );
    auto & model = *test.device_models[0];

    for( auto && sub : model.subdevices )
        test.click_stream_toggle_on( sub, model );

    test.imgui->SleepNoSkip( 1.0f, 0.5f );
    IM_CHECK( test.all_streams_alive() );

    test.imgui->SleepNoSkip( 2.0f, 1.0f );

    for( auto && sub : model.subdevices )
        test.click_stream_toggle_off( sub, model );

    IM_CHECK( !model.is_streaming() );
}
