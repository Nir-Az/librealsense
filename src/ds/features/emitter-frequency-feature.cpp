// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2023 Intel Corporation. All Rights Reserved.

#pragma once

#include <src/ds/features/emitter-frequency-feature.h>
#include <src/platform/uvc-option.h>
#include <src/ds/ds-private.h>
#include <src/sensor.h>

namespace librealsense {


emitter_frequency_feature::emitter_frequency_feature( synthetic_sensor & sensor )
    : feature_interface( ID )
    , _sensor( sensor )
{
    _emitter_freq_option = std::make_shared< uvc_xu_option< uint16_t > >(
        dynamic_cast< uvc_sensor & >( *_sensor.get_raw_sensor() ),
        ds::depth_xu,
        ds::DS5_EMITTER_FREQUENCY,
        "Controls the emitter frequency, 57 [KHZ] / 91 [KHZ]",
        std::map< float, std::string >{ { (float)RS2_EMITTER_FREQUENCY_57_KHZ, "57 KHZ" },
                                        { (float)RS2_EMITTER_FREQUENCY_91_KHZ, "91 KHZ" } },
        false );
}

void emitter_frequency_feature::activate()
{
    _sensor.register_option( RS2_OPTION_EMITTER_FREQUENCY, _emitter_freq_option );
}

void emitter_frequency_feature::deactivate()
{
    _sensor.unregister_option( RS2_OPTION_EMITTER_FREQUENCY );
}


}  // namespace librealsense
