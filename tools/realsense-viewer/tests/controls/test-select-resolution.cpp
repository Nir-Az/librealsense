// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "viewer-test-helpers.h"
#include "imgui_te_context.h"


// Change resolution via the combo box for each sensor (if applicable), start streaming, and verify frames arrive
VIEWER_TEST( "controls", "select_resolution_and_stream" )
{
    IM_CHECK( !test.device_models.empty() );
    auto & model = *test.device_models[0];

    for( auto && sub : model.subdevices )
    {
        if( sub->resolutions.empty() || sub->get_selected_profiles().empty() )
            continue;

        // Pick target resolution: prefer HD, fall back to first available.
        std::string target_res;
        for( auto & r : sub->resolutions )
            if( r == "1280 x 720" ) { target_res = r; break; }
        if( target_res.empty() )
            target_res = sub->resolutions[0];

        test.expand_sensor_panel( sub, model );

        // Build the ImGui label that matches the resolution combo box in the viewer's control panel,
        // then select the target resolution from its dropdown
        std::string res_combo = rsutils::string::from()
            << "##" << sub->dev.get_info( RS2_CAMERA_INFO_NAME )
            << sub->s->get_info( RS2_CAMERA_INFO_NAME ) << " resolution";
        test.select_combo_item( sub, model, res_combo.c_str(), target_res.c_str() );

        test.collapse_sensor_panel( sub, model );

        test.click_stream_toggle_on( sub, model );
        IM_CHECK( test.all_streams_alive() );

        test.imgui->SleepNoSkip( 3.0f, 1.0f );

        test.click_stream_toggle_off( sub, model );
        // Give the camera real time to stop before the next sensor starts.
        test.imgui->SleepNoSkip( 2.0f, 0.5f );
    }

    IM_CHECK( !model.is_streaming() );
}
