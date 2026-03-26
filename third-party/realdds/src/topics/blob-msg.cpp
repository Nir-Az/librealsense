// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2023-4 RealSense, Inc. All Rights Reserved.

#include <realdds/topics/blob-msg.h>
#include <realdds/topics/blob/blobPubSubTypes.h>

#include <realdds/dds-topic.h>
#include <realdds/dds-topic-reader.h>
#include <realdds/dds-topic-writer.h>
#include <realdds/dds-utilities.h>

#include <fastdds/dds/subscriber/DataReader.hpp>
#include <fastdds/dds/publisher/DataWriter.hpp>
#include <fastdds/dds/topic/Topic.hpp>


namespace realdds {
namespace topics {


/*static*/ std::shared_ptr< dds_topic >
blob_msg::create_topic( std::shared_ptr< dds_participant > const & participant, char const * topic_name )
{
    return std::make_shared< dds_topic >( participant,
                                          eprosima::fastdds::dds::TypeSupport( new blob_msg::type ),
                                          topic_name );
}


/*static*/ bool
blob_msg::take_next( dds_topic_reader & reader, blob_msg * output, dds_sample * info )
{
    eprosima::fastdds::dds::SampleInfo info_;
    if( ! info )
        info = &info_;  // use the local copy if the user hasn't provided their own
    auto status = reader->take_next_sample( static_cast< udds::blob * >( output ), info );
    if( status == ReturnCode_t::RETCODE_OK )
    {
        // We have data
        if( output )
        {
            // Only samples for which valid_data is true should be accessed
            // valid_data indicates that the instance is still ALIVE and the `take` return an
            // updated sample
            if( ! info->valid_data )
                output->invalidate();
        }
        return true;
    }
    if( status == ReturnCode_t::RETCODE_NO_DATA )
    {
        // This is an expected return code and is not an error
        return false;
    }
    DDS_API_CALL_THROW( "blob_msg::take_next", status );
}


dds_sequence_number blob_msg::write_to( dds_topic_writer & writer ) const
{
    return write_to( writer, []() { return false; } );
}


dds_sequence_number blob_msg::write_to( dds_topic_writer & writer, std::function< bool() > should_stop ) const
{
    eprosima::fastrtps::rtps::WriteParams params;
    bool success = DDS_API_CALL(
        writer.get()->write( const_cast< udds::blob * >( static_cast< udds::blob const * >( this ) ), params ) );
    if( ! success )
    {
        LOG_ERROR( "Error writing message" );
        return 0;
    }
    
    // We assume ASYNCHRONOUS mode, so write() returned quickly.
    // Now wait for ACKs with periodic check.
    dds_time wait_time;
    wait_time.seconds = 0;
    wait_time.nanosec = 100000000; // 0.1s
    
    while( DDS_API_CALL( writer.get()->wait_for_acknowledgments( wait_time ) != ReturnCode_t::RETCODE_OK ) )
    {
        if( should_stop() )
        {
            LOG_DEBUG( "Aborting write of blob message" );
            size_t removed = 0;
            DDS_API_CALL( writer.get()->clear_history( &removed ) );
            return 0;
        }
    }

    // The params will contain, after the write, the sequence number (incremented automatically) for the sample that was
    // sent. The source_timestamp is always INVALID for some reason.
    return params.sample_identity().sequence_number().to64long();
}


}  // namespace topics
}  // namespace realdds
