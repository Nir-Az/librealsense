// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "viewer-test-helpers.h"

#include <librealsense2/rs_advanced_mode.hpp>


// The pencil beside an advanced-mode slider swaps it for a text box that stays until a value is
// entered. That state has to survive from one frame to the next: a plain click and typed digits,
// no ctrl-click and no drag, must reach the camera.
VIEWER_TEST( "controls", "advanced_text_edit" )
{
    auto & model = test.find_first_device_or_exit();
    if( ! model.dev.is< rs400::advanced_mode >()
        || ! model.dev.as< rs400::advanced_mode >().is_enabled() )
        return;   // nothing to edit on a device that has no advanced mode

    auto advanced = model.dev.as< rs400::advanced_mode >();

    // IM_CHECK returns from the test on failure; put the group back on the way out regardless
    struct depth_control_restore
    {
        rs400::advanced_mode advanced;
        STDepthControlGroup saved;
        ~depth_control_restore() { try { advanced.set_depth_control( saved ); } catch( ... ) {} }
    } restore{ advanced, advanced.get_depth_control( 0 ) };

    std::shared_ptr< rs2::subdevice_model > sub;
    for( auto && s : model.subdevices )
        if( s->s->is< rs2::depth_sensor >() )
        {
            sub = s;
            break;
        }
    IM_CHECK( sub != nullptr );

    test.expand_sensor_panel( model, sub );
    IM_CHECK( test.wait_until( 10, 0.3f, [&] {
        return test.node_shown( model, sub, { "Advanced Controls" } ); } ) );

    test.imgui->ItemOpen( test.node_id( model, sub, { "Advanced Controls" } ) );
    test.imgui->ItemOpen( test.node_id( model, sub, { "Advanced Controls", "Depth Control" } ) );

    // the slider and the text box that replaces it share the "##<name>" label; the pencil is
    // "<edit icon>##<name>" beside it
    ImGuiID const widget = test.node_id( model, sub,
        { "Advanced Controls", "Depth Control", "##DS Median Threshold" } );
    std::string const edit_label = rsutils::string::from()
        << rs2::textual_icons::edit << "##DS Median Threshold";
    ImGuiID const edit_button = test.node_id( model, sub,
        { "Advanced Controls", "Depth Control", edit_label } );
    IM_CHECK( test.wait_until( 10, 0.3f, [&] { return test.imgui->ItemExists( widget ); } ) );
    IM_CHECK( test.imgui->ItemExists( edit_button ) );

    auto const original = advanced.get_depth_control( 0 ).deepSeaMedianThreshold;
    auto const minimum = advanced.get_depth_control( 1 ).deepSeaMedianThreshold;
    auto const target = ( original == minimum ) ? original + 100 : minimum;

    auto type_value = [&]( int value )
    {
        test.imgui->ItemClick( edit_button );
        test.imgui->ItemClick( widget );
        // a text box takes the focus; a slider left in place would not, and would ignore the keys
        IM_CHECK_RETV( test.imgui->UiContext->InputTextState.ID == widget, false );
        test.imgui->KeyCharsReplaceEnter( std::to_string( value ).c_str() );
        return true;
    };

    IM_CHECK( type_value( (int)target ) );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == target; } ) );

    // and back, so the next test starts where this one found the camera
    IM_CHECK( type_value( (int)original ) );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == original; } ) );
}
