// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "viewer-test-helpers.h"

#include <librealsense2/rs_advanced_mode.hpp>


// IM_CHECK returns from the test on failure, so a restore at the very end may never run - put the
// group back on the way out regardless, or every later test inherits the probe value
struct depth_control_restore
{
    rs400::advanced_mode advanced;
    STDepthControlGroup saved;
    ~depth_control_restore() { try { advanced.set_depth_control( saved ); } catch( ... ) {} }
};

// Both tests below drive "DS Median Threshold" under Advanced Controls > Depth Control. The slider
// and the text box that replaces it share the "##<name>" label; the pencil beside them is
// "<edit icon>##<name>". Returns false when the device has no advanced mode to drive.
static bool open_ds_median_threshold( viewer_test & test, rs2::device_model & model,
                                      std::shared_ptr< rs2::subdevice_model > & sub,
                                      ImGuiID & widget, ImGuiID & edit_button )
{
    if( ! model.dev.is< rs400::advanced_mode >()
        || ! model.dev.as< rs400::advanced_mode >().is_enabled() )
        return false;

    for( auto && s : model.subdevices )
        if( s->s->is< rs2::depth_sensor >() )
        {
            sub = s;
            break;
        }
    IM_CHECK_RETV( sub != nullptr, false );

    test.expand_sensor_panel( model, sub );
    IM_CHECK_RETV( test.wait_until( 10, 0.3f, [&] {
        return test.node_shown( model, sub, { "Advanced Controls" } ); } ), false );

    test.imgui->ItemOpen( test.node_id( model, sub, { "Advanced Controls" } ) );
    test.imgui->ItemOpen( test.node_id( model, sub, { "Advanced Controls", "Depth Control" } ) );

    widget = test.node_id( model, sub, { "Advanced Controls", "Depth Control", "##DS Median Threshold" } );
    std::string const edit_label = rsutils::string::from()
        << rs2::textual_icons::edit << "##DS Median Threshold";
    edit_button = test.node_id( model, sub, { "Advanced Controls", "Depth Control", edit_label } );
    IM_CHECK_RETV( test.wait_until( 10, 0.3f, [&] { return test.imgui->ItemExists( widget ); } ), false );
    IM_CHECK_RETV( test.imgui->ItemExists( edit_button ), false );
    return true;
}

// A probe value the camera does not already hold
static int probe_value( rs400::advanced_mode & advanced )
{
    auto const original = advanced.get_depth_control( 0 ).deepSeaMedianThreshold;
    auto const minimum = advanced.get_depth_control( 1 ).deepSeaMedianThreshold;
    return (int)( ( original == minimum ) ? original + 100 : minimum );
}


// An advanced-mode section writes its whole group to the camera once, after the controls inside it
// have drawn: what the user dragged has to reach the camera, and only that section has to write.
VIEWER_TEST( "controls", "advanced_write_back" )
{
    auto & model = test.find_first_device_or_exit();
    std::shared_ptr< rs2::subdevice_model > sub;
    ImGuiID slider, edit_button;
    if( ! open_ds_median_threshold( test, model, sub, slider, edit_button ) )
        return;

    auto advanced = model.dev.as< rs400::advanced_mode >();
    depth_control_restore restore{ advanced, advanced.get_depth_control( 0 ) };
    auto const original = advanced.get_depth_control( 0 ).deepSeaMedianThreshold;
    auto const target = probe_value( advanced );

    test.imgui->ItemInputValue( slider, target );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == target; } ) );

    // and back, so the next test starts where this one found the camera
    test.imgui->ItemInputValue( slider, (int)original );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == original; } ) );
}


// The pencil swaps the slider for a text box that stays until a value is entered. That state has
// to survive from one frame to the next: a plain click and typed digits, no ctrl-click and no
// drag, must reach the camera.
VIEWER_TEST( "controls", "advanced_text_edit" )
{
    auto & model = test.find_first_device_or_exit();
    std::shared_ptr< rs2::subdevice_model > sub;
    ImGuiID widget, edit_button;
    if( ! open_ds_median_threshold( test, model, sub, widget, edit_button ) )
        return;

    auto advanced = model.dev.as< rs400::advanced_mode >();
    depth_control_restore restore{ advanced, advanced.get_depth_control( 0 ) };
    auto const original = advanced.get_depth_control( 0 ).deepSeaMedianThreshold;
    auto const target = probe_value( advanced );

    auto type_value = [&]( int value )
    {
        test.imgui->ItemClick( edit_button );
        test.imgui->ItemClick( widget );
        // a text box takes the focus; a slider left in place would not, and would ignore the keys
        IM_CHECK_RETV( test.imgui->UiContext->InputTextState.ID == widget, false );
        test.imgui->KeyCharsReplaceEnter( std::to_string( value ).c_str() );
        return true;
    };

    IM_CHECK( type_value( target ) );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == target; } ) );

    IM_CHECK( type_value( (int)original ) );
    IM_CHECK( test.wait_until( 20, 0.25f, [&] {
        return advanced.get_depth_control( 0 ).deepSeaMedianThreshold == original; } ) );
}
