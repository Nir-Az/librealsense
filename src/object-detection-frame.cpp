// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "object-detection-frame.h"
#include "librealsense-exception.h"
#include <rsutils/number/crc32.h>
#include <rsutils/string/from.h>
#include <rsutils/easylogging/easyloggingpp.h>
#include <utility>

namespace librealsense
{

object_detection_frame::object_detection_frame( object_detection_frame && other )
    : perception_frame( std::move( other ) )
{
}

object_detection_frame & object_detection_frame::operator=( object_detection_frame && other )
{
    perception_frame::operator=( std::move( other ) );
    _validated = false;
    return *this;
}

bool object_detection_frame::validate() const
{
    if( _validated )
        return true;
    if( ! validate_payload() )
        return false;
    _validated = true;
    return true;
}

bool object_detection_frame::validate_payload() const
{
    if( data.size() < MIN_FRAME_SIZE )
        return false;

    const object_detection_payload * payload = reinterpret_cast< const object_detection_payload * >( data.data() );

    // The firmware ABI excludes the fixed frame header from CRC coverage. Validate its fields
    // independently; header.size never determines a memory-access or CRC bound.
    if( payload->header.magic_number != MAGIC_NUMBER )
        return false;

    if( payload->header.data_type != static_cast< uint8_t >( perception_frame::type::OBJECT_DETECTION ) )
    {
        LOG_WARNING( "Unsupported Object Detection data_type: " << payload->header.data_type );
        return false;
    }

    uint16_t n = payload->number_of_detections;
    if( n > MAX_DETECTIONS )
    {
        LOG_WARNING( "Object Detection count exceeds ABI maximum: " << n << " > " << MAX_DETECTIONS );
        return false;
    }

    size_t detections_size = ENTRY_SIZE * n;
    size_t expected_size_field = PAYLOAD_HEADER_SIZE + detections_size;
    size_t expected_data_size_with_detections = FRAME_HEADER_SIZE + expected_size_field;

    // data.size() may exceed the logical payload if the transport adds trailing padding. The header
    // declares the valid length, and the bounded detection count keeps every read within the buffer.
    if( data.size() < expected_data_size_with_detections || payload->header.size != expected_size_field )
    {
        LOG_WARNING( "Object Detection frame size mismatch: got " << data.size() << ", expected at least " << expected_data_size_with_detections <<
                     ", header size field: " << payload->header.size << ", expected size field: " << expected_size_field );
        return false;
    }

    auto const payload_data = data.data() + FRAME_HEADER_SIZE;
    auto const computed_crc32 = rsutils::number::calc_crc32( payload_data, expected_size_field );
    if( payload->header.crc32 != computed_crc32 )
    {
        LOG_WARNING( "Object Detection CRC mismatch: got " << payload->header.crc32
                     << ", expected " << computed_crc32 );
        return false;
    }

    return true;
}

size_t object_detection_frame::get_detection_count() const
{
    if( validate() )
        return reinterpret_cast< const object_detection_payload * >( data.data() )->number_of_detections;

    return 0;
}

object_detection_frame::object_detection_entry object_detection_frame::get_detection( size_t index ) const
{
    size_t count = get_detection_count(); // Validates frame as well
    if( index >= count )
        throw std::out_of_range(
            rsutils::string::from() << "Detection index " << index << " is out of range (count=" << count << ")" );
    return reinterpret_cast< const object_detection_payload * >( data.data() )->detections[index];
}

}  // namespace librealsense
