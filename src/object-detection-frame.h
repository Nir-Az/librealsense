// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.
#pragma once

#include "frame.h"
#include "perception-frame.h"
#include "core/extension.h"
#include <librealsense2/h/rs_types.h>
#include <rsutils/string/from.h>
#include <atomic>
#include <cstddef>

namespace librealsense {

class object_detection_frame : public perception_frame
{
public:
    // Frames received over the object detection stream are binary blobs with object_detection_payload layout.

    static constexpr uint32_t MAGIC_NUMBER = 0x5445444F;  // ASCII "ODET" as a little-endian uint32
    static constexpr uint32_t MAX_DETECTIONS = 64;

    enum class source : uint8_t
    {
        RGB = 0,
        DEPTH = 1
    };

#pragma pack( push, 1 )
    struct object_detection_frame_header
    {
        uint32_t magic_number;  // Must equal MAGIC_NUMBER
        uint16_t version;       // major.minor SDK/HKR API version
        uint8_t data_type;      // 0 = object detection
        uint8_t flags;
        uint32_t size;          // Expected frame size, header excluded
        uint32_t spare;
        uint32_t crc32;         // CRC of the data, header excluded
    };

    struct object_detection_entry
    {
        uint16_t detection_id;    // For detection/tracking traceability
        uint8_t detection_type;   // 0 = person
        uint8_t confidence;       // 0-100
        uint16_t top_left_x;      // Bounding box top-left X [pixels]
        uint16_t top_left_y;      // Bounding box top-left Y [pixels]
        uint16_t bottom_right_x;  // Bounding box bottom-right X [pixels]
        uint16_t bottom_right_y;  // Bounding box bottom-right Y [pixels]
        float distance;           // Object distance from camera [meters]
    };

    struct object_detection_payload
    {
        object_detection_frame_header header;
        double timestamp_ms;       // Frame timestamp [milliseconds]
        uint64_t frame_id;         // Frame counter
        uint16_t number_of_detections;
        uint8_t source;            // 0 = RGB, 1 = depth
        uint32_t source_frame_id;  // ID of the frame detection was calculated on
        object_detection_entry detections[1]; // `number_of_detections` entries of type `object_detection_entry`
    };
#pragma pack( pop )

    static constexpr size_t FRAME_HEADER_SIZE = sizeof( object_detection_frame_header );
    static constexpr size_t PAYLOAD_HEADER_SIZE
        = offsetof( object_detection_payload, detections ) - FRAME_HEADER_SIZE;
    static constexpr size_t ENTRY_SIZE = sizeof( object_detection_entry );
    static constexpr size_t MIN_FRAME_SIZE = FRAME_HEADER_SIZE + PAYLOAD_HEADER_SIZE;

    static_assert( FRAME_HEADER_SIZE == 20, "Object Detection frame header ABI must be 20 bytes" );
    static_assert( PAYLOAD_HEADER_SIZE == 23, "Object Detection payload header ABI must be 23 bytes" );
    static_assert( ENTRY_SIZE == 16, "Object Detection entry ABI must be 16 bytes" );
    static_assert( MIN_FRAME_SIZE == 43, "Object Detection minimum frame ABI must be 43 bytes" );

    object_detection_frame() = default;
    object_detection_frame( object_detection_frame && other );
    object_detection_frame & operator=( object_detection_frame && other );

    size_t get_detection_count() const;
    object_detection_entry get_detection( size_t index ) const;

private:
    bool validate() const;
    bool validate_payload() const;

    mutable std::atomic_bool _validated{ false };
};

MAP_EXTENSION(RS2_EXTENSION_OBJECT_DETECTION_FRAME, librealsense::object_detection_frame);

}  // namespace librealsense
