// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2022 Intel Corporation. All Rights Reserved.

#include <realdds/dds-device-broadcaster.h>

#include <realdds/dds-participant.h>
#include <realdds/dds-publisher.h>
#include <realdds/dds-topic-writer.h>
#include <realdds/dds-topic.h>
#include <realdds/dds-utilities.h>
#include <realdds/topics/dds-topic-names.h>
#include <realdds/topics/flexible-msg.h>

#include <fastdds/dds/publisher/DataWriter.hpp>
#include <fastdds/dds/core/condition/WaitSet.hpp>
#include <fastdds/dds/core/condition/GuardCondition.hpp>

#include <rsutils/shared-ptr-singleton.h>
#include <rsutils/string/slice.h>
using rsutils::string::slice;


namespace realdds {


// Singleton, per participant
// Manages the thread from which broadcast messages are sent
//
class detail::broadcast_manager
{
    std::thread _th;
    std::shared_ptr< dds_topic_writer > _writer;
    eprosima::fastdds::dds::GuardCondition _stopped;
    eprosima::fastdds::dds::GuardCondition _ready_for_broadcast;

    std::mutex _broadcasters_mutex;
    std::set< dds_device_broadcaster * > _broadcasters;

public:
    broadcast_manager( std::shared_ptr< dds_publisher > const & publisher )
    {
        auto topic = topics::flexible_msg::create_topic( publisher->get_participant(), topics::DEVICE_INFO_TOPIC_NAME );

        // We keep our own writer just for the thread status notifications
        _writer = std::make_shared< dds_topic_writer >( topic, publisher );
        _writer->on_publication_matched(
            [this]( eprosima::fastdds::dds::PublicationMatchedStatus const & status )
            {
                LOG_DEBUG( _writer->topic()->get_participant()->name()
                           << ": " << status.current_count << " total watchers for broadcast ("
                           << ( status.current_count_change >= 0 ? "+" : "" ) << status.current_count_change << ")" );
                // We get called from the participant thread; trigger our own thread for actual broadcast
                if( status.current_count_change > 0 )
                    _ready_for_broadcast.set_trigger_value( true );
            } );
        _writer->run();

        _th = std::thread(
            [this]()
            {
                LOG_DEBUG( _writer->topic()->get_participant()->name() << ": broadcaster thread running" );
                eprosima::fastdds::dds::WaitSet wait_set;
                //auto & publication_matched = _writer->get()->get_statuscondition();
                //publication_matched.set_enabled_statuses( eprosima::fastdds::dds::StatusMask::publication_matched() );
                //wait_set.attach_condition( publication_matched );
                wait_set.attach_condition( _ready_for_broadcast );
                wait_set.attach_condition( _stopped );

                while( ! _stopped.get_trigger_value() )
                {
                    eprosima::fastdds::dds::ConditionSeq active_conditions;
                    wait_set.wait( active_conditions, eprosima::fastrtps::c_TimeInfinite );
                    if( _stopped.get_trigger_value() )
                        break;
                    // Let multiple broadcasts gather and do it only once
                    std::this_thread::sleep_for( std::chrono::milliseconds( 50 ) );
                    _ready_for_broadcast.set_trigger_value( false );

                    std::lock_guard< std::mutex > lock( _broadcasters_mutex );
                    LOG_DEBUG( _writer->topic()->get_participant()->name() << ": broadcasting" );
                    for( dds_device_broadcaster const * broadcaster : _broadcasters )
                        broadcaster->broadcast();
                }
                LOG_DEBUG( _writer->topic()->get_participant()->name() << ": broadcaster thread stopped" );
            } );
    }

    ~broadcast_manager()
    {
        if( _th.joinable() )
        {
            _stopped.set_trigger_value( true );
            _th.join();
        }
    }

    std::shared_ptr< dds_topic_writer > register_broadcaster( dds_device_broadcaster * broadcaster )
    {
        // Each broadcaster (for a single device) gets its own writer, with a GUID, from which its broadcasts will be
        // made. This lets the watcher associate the GUID with that specific device, and can tell when the GUID
        // disappears that the device is no longer online...
        auto writer = std::make_shared< dds_topic_writer >( _writer->topic(), _writer->publisher() );
        writer->run();
        {
            std::lock_guard< std::mutex > lock( _broadcasters_mutex );
            _broadcasters.insert( broadcaster );
        }
        return writer;
    }

    void unregister_broadcaster( dds_device_broadcaster * broadcaster )
    {
        std::lock_guard< std::mutex > lock( _broadcasters_mutex );
        _broadcasters.erase( broadcaster );
    }
};


static std::map< realdds::dds_guid, rsutils::shared_ptr_singleton< detail::broadcast_manager > >
    participant_broadcast_manager;


dds_device_broadcaster::dds_device_broadcaster( std::shared_ptr< dds_publisher > const & publisher,
                                                topics::device_info const & dev_info )
    : _device_info( dev_info )
{
    if( ! publisher )
        DDS_THROW( runtime_error, "null publisher" );

    auto participant_guid = publisher->get_participant()->guid();
    _manager = participant_broadcast_manager[participant_guid].instance( publisher );
    _writer = _manager->register_broadcaster( this );

    broadcast();  // possible we have no subscribers, but can't hurt
}


void dds_device_broadcaster::broadcast() const
{
    try
    {
        topics::flexible_msg msg( _device_info.to_json() );
        LOG_DEBUG( "sending device-info message " << slice( msg.custom_data< char const >(), msg._data.size() ) );
        msg.write_to( *_writer );
    }
    catch( std::exception const & e )
    {
        LOG_ERROR( "Error sending device-info message for S/N " << _device_info.serial << ": " << e.what() );
    }
}


dds_device_broadcaster::~dds_device_broadcaster()
{
    _manager->unregister_broadcaster( this );
    // _th ref count will be decreased and, if no others hold it, destroyed -- thereby stopping the thread
}


}  // namespace realdds
