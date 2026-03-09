// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "viewer-test-helpers.h"
#include "imgui_te_context.h"


// Set exposure manually, verify auto-exposure disables, toggle it back on, and confirm frames keep arriving
VIEWER_TEST( "controls", "set_exposure" )
{
    IM_CHECK( !test.device_models.empty() );
    auto & model = *test.device_models[0];

    for( auto && sub : model.subdevices )
    {
        auto exp_it = sub->options_metadata.find( RS2_OPTION_EXPOSURE );
        if( exp_it == sub->options_metadata.end() || !exp_it->second.supported
            || exp_it->second.read_only )
            continue;

        test.click_toggle_on( sub, model );
        test.imgui->SleepNoSkip( 2.0f, 1.0f );

        test.expand_sensor_panel( sub, model, true );
        test.set_option_value( sub, model, RS2_OPTION_EXPOSURE, "100" );

        // Verify frames still arriving after exposure change
        IM_CHECK( test.all_streams_alive() );

        // setting exposure manually is expected to disable auto-exposure
        auto ae_it = sub->options_metadata.find( RS2_OPTION_ENABLE_AUTO_EXPOSURE );
        if( ae_it != sub->options_metadata.end() && ae_it->second.supported )
        {
            IM_CHECK( test.wait_until( 10, 0.5f, [&] {
                return !test.is_option_checked( sub, model, RS2_OPTION_ENABLE_AUTO_EXPOSURE );
            } ) );

            // toggle it back on
            test.toggle_option( sub, model, RS2_OPTION_ENABLE_AUTO_EXPOSURE );
        }

        test.collapse_sensor_panel( sub, model, true );
        test.click_toggle_off( sub, model );
        test.imgui->Sleep( 1.0f );
    }

    IM_CHECK( !model.is_streaming() );
}
