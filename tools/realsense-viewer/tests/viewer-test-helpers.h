// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#pragma once

#include "viewer.h"
#include "device-model.h"
#include "imgui_te_engine.h"
#include "imgui_te_context.h"

#include <vector>
#include <memory>
#include <string>


// ---------------------------------------------------------------------------
// viewer_test — wraps helpers as methods for cleaner test bodies
// ---------------------------------------------------------------------------
class viewer_test;
typedef void (*viewer_test_func)( viewer_test & );


// ---------------------------------------------------------------------------
// Auto-registration
// ---------------------------------------------------------------------------
struct viewer_test_entry
{
    const char *     category;
    const char *     name;
    viewer_test_func func;
    const char *     file;
    int              line;
};

inline std::vector< viewer_test_entry > & viewer_test_registry()
{
    static std::vector< viewer_test_entry > entries;
    return entries;
}

struct viewer_test_registrar
{
    viewer_test_registrar( const char * category, const char * name,
                           viewer_test_func fn, const char * file, int line )
    {
        viewer_test_registry().push_back( { category, name, fn, file, line } );
    }
};


// ---------------------------------------------------------------------------
// VIEWER_TEST macro — auto-registers the test at static-init time
// ---------------------------------------------------------------------------
#define _VT_CONCAT2( a, b ) a##b
#define _VT_CONCAT( a, b ) _VT_CONCAT2( a, b )

#define VIEWER_TEST( CATEGORY, NAME )                                          \
    static void _VT_CONCAT( _vt_fn_, __LINE__ )( viewer_test & );             \
    namespace {                                                                \
    static viewer_test_registrar _VT_CONCAT( _vt_reg_, __LINE__ )(            \
        CATEGORY, NAME, &_VT_CONCAT( _vt_fn_, __LINE__ ), __FILE__, __LINE__ );\
    }                                                                          \
    static void _VT_CONCAT( _vt_fn_, __LINE__ )( viewer_test & test )


// ---------------------------------------------------------------------------
// viewer_test
// ---------------------------------------------------------------------------
class viewer_test
{
public:
    ImGuiTestContext *         imgui;
    rs2::device_models_list & device_models;
    rs2::viewer_model &       viewer_model;

    // Open a sensor's collapsible panel, optionally expanding the controls section too
    void expand_sensor_panel( std::shared_ptr< rs2::subdevice_model > sub,
                              rs2::device_model & model,
                              bool open_controls = false );
    // Close a sensor's collapsible panel, optionally collapsing the controls section first
    void collapse_sensor_panel( std::shared_ptr< rs2::subdevice_model > sub,
                                rs2::device_model & model,
                                bool close_controls = false );

    // Start streaming on a sensor by clicking its toggle button; throws if already streaming
    void click_toggle_on( std::shared_ptr< rs2::subdevice_model > sub,
                          rs2::device_model & model );
    // Stop streaming on a sensor by clicking its toggle button; throws if already stopped
    void click_toggle_off( std::shared_ptr< rs2::subdevice_model > sub,
                           rs2::device_model & model );

    // Poll a condition up to max_attempts times, sleeping interval seconds between checks
    template< typename Pred >
    bool wait_until( int max_attempts, float interval, Pred cond )
    {
        for( int i = 0; i < max_attempts && !cond(); ++i )
            imgui->SleepNoSkip( interval, 0.05f );
        return cond();
    }

    // Open a device's hamburger menu and click the named item
    void click_device_menu_item( rs2::device_model & model, const char * item );

    // Type a numeric value into a slider option's edit field
    void set_option_value( std::shared_ptr< rs2::subdevice_model > sub,
                           rs2::device_model & model,
                           rs2_option option, const char * value );
    // Click a checkbox option to flip its state
    void toggle_option( std::shared_ptr< rs2::subdevice_model > sub,
                        rs2::device_model & model,
                        rs2_option option );
    // Query whether a checkbox option is currently checked
    bool is_option_checked( std::shared_ptr< rs2::subdevice_model > sub,
                            rs2::device_model & model,
                            rs2_option option );
    // Open a combo dropdown and select the named item
    void select_combo_item( std::shared_ptr< rs2::subdevice_model > sub,
                            rs2::device_model & model,
                            const char * combo_label, const char * item );

    // Wait until all active streams are receiving frames
    bool all_streams_alive( int max_attempts = 30, float interval = 0.5f );

    // -----------------------------------------------------------------------
    // Internal helpers — build ImGui labels and ID seeds for the control panel
    // -----------------------------------------------------------------------
private:
    std::string sensor_label( std::shared_ptr< rs2::subdevice_model > sub,
                               rs2::device_model & model );
    std::string controls_label( std::shared_ptr< rs2::subdevice_model > sub,
                                 rs2::device_model & model );
    ImGuiID sensor_id_seed( std::shared_ptr< rs2::subdevice_model > sub,
                             rs2::device_model & model );
    ImGuiID controls_id_seed( std::shared_ptr< rs2::subdevice_model > sub,
                               rs2::device_model & model );
};
