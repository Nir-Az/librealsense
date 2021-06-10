// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2018 Intel Corporation. All Rights Reserved.

/////////////////////////////////////////////////////////////////////////////////////////////////////////////
// This set of tests is valid for any number and combination of RealSense cameras, including R200 and F200 //
/////////////////////////////////////////////////////////////////////////////////////////////////////////////
#include <cmath>
#include "unit-tests-common.h"
#include "../include/librealsense2/rs_advanced_mode.hpp"
#include <librealsense2/hpp/rs_frame.hpp>
#include <iostream>
#include <chrono>
#include <ctime>
#include <algorithm>
#include <deque>
#include <librealsense2/rsutil.h>

# define SECTION_FROM_TEST_NAME space_to_underscore(Catch::getCurrentContext().getResultCapture()->getCurrentTestName()).c_str()

std::string frame_to_string(const rs2::frame& f)
{
    std::ostringstream s;

    if (!&f)
    {
        s << "[null]";
    }
    else
    {
        auto composite = f.as<rs2::frameset>();
        if (composite)
        {
            s << "[";
            composite.foreach_rs([&](const rs2::frame& f) {s << frame_to_string(f); });
            s << "]";
        }
        else
        {
            auto profile = f.get_profile();
            s << "[" << profile.stream_type();
            s << "/" << profile.unique_id();
            s << " #" << f.get_frame_number();
            s << " @" << std::fixed << (double)f.get_timestamp();
            s << " W: " << profile.as<rs2::video_stream_profile>().width() << " H: " << profile.as<rs2::video_stream_profile>().height();
            s << "]";
        }
    }
    return s.str();
}

typedef struct _sw_context
{

    rs2::software_device sdev;
    std::map<std::string, std::shared_ptr<rs2::software_sensor>> sw_sensors;
    std::map<std::string, rs2::syncer> sw_syncers;
    std::map<std::string, std::map<rs2_stream, rs2::stream_profile>> sw_stream_profiles;
} sw_context;

rs2_software_video_frame create_sw_frame(const rs2::video_frame& f, rs2::stream_profile profile)
{
    uint32_t data_size = f.get_width() * f.get_bytes_per_pixel() * f.get_height();
    uint8_t* data = new uint8_t[data_size];
    std::memcpy(data, f.get_data(), data_size);
    rs2_software_video_frame new_frame = {
        (void*)data,
        [](void* data) { delete[] (uint8_t*)data; },
        f.get_width() * f.get_bytes_per_pixel(),
        f.get_bytes_per_pixel(),
        f.get_timestamp(),
        f.get_frame_timestamp_domain(),
        static_cast<int>(f.get_frame_number()),
        profile
    };
    return new_frame;
}

class processing_recordable_block
{
public:
    virtual void record(std::string sensor_name, const rs2::frame& frame, sw_context sctx) = 0;
    virtual rs2::frame process(const rs2::frame& frame) = 0;
};

class align_record_block : public processing_recordable_block
{
public:
    align_record_block(rs2_stream align_to, rs2_stream align_from) : _align(align_to), _align_from(align_from) {}
    virtual void record(std::string sensor_name, const rs2::frame& frame, sw_context sctx) override
    {
        auto ss = sctx.sw_sensors[sensor_name];
        ss->on_video_frame(create_sw_frame(frame, sctx.sw_stream_profiles[sensor_name][_align_from]));
        ss->stop();
        ss->close();
    }
    virtual rs2::frame process(const rs2::frame& frame) override
    {
        auto fs = frame.as<rs2::frameset>();
        return (_align.process(fs)).first_or_default(_align_from);
    }

private:
    rs2::align _align;
    rs2_stream _align_from;

};

class pointcloud_record_block : public processing_recordable_block
{
public:
    pointcloud_record_block() {}
    virtual void record(std::string sensor_name, const rs2::frame& frame, sw_context sctx) override
    {
        auto profile = sctx.sw_stream_profiles[sensor_name][RS2_STREAM_DEPTH].as<rs2::video_stream_profile>();
        const int points_bpp = 20;
        uint32_t data_size = profile.width() * points_bpp * profile.height();
        uint8_t* data = new uint8_t[data_size];
        std::memcpy(data, frame.get_data(), data_size);
        rs2_software_video_frame points_frame = {
            (void*)data,
            [](void* data) { delete[] (uint8_t*)data; },
            profile.width() * points_bpp,
            points_bpp,
            frame.get_timestamp(),
            frame.get_frame_timestamp_domain(),
            static_cast<int>(frame.get_frame_number()),
            sctx.sw_stream_profiles[sensor_name][RS2_STREAM_DEPTH]
        };

        auto ss = sctx.sw_sensors[sensor_name];
        ss->on_video_frame(points_frame);
        ss->stop();
        ss->close();
    }
    virtual rs2::frame process(const rs2::frame& frame) override
    {
        auto fs = frame.as<rs2::frameset>();
        return _pc.calculate(fs.get_depth_frame());
    }

private:
    rs2::pointcloud _pc;
};

std::string get_sensor_name(rs2::video_stream_profile c, rs2::video_stream_profile d)
{
    std::string dres = std::to_string(d.width()) + "x" + std::to_string(d.height());
    std::string cres = std::to_string(c.width()) + "x" + std::to_string(c.height());
    std::string name = "depth_" + dres + "_color_" + std::to_string(c.format()) + "_" + cres;
    return name;
}

rs2::stream_profile init_stream_profile(std::shared_ptr<rs2::software_sensor> ss, rs2::video_stream_profile stream_profile)
{
    rs2_video_stream new_stream = {
        stream_profile.stream_type(),
        stream_profile.stream_index(),
        stream_profile.unique_id(),
        stream_profile.width(),
        stream_profile.height(),
        stream_profile.fps(),
        stream_profile.height(),
        stream_profile.format(),
        stream_profile.get_intrinsics()
    };

    return ss->add_video_stream(new_stream);
}

std::vector<rs2::stream_profile> init_stream_profiles(sw_context& sctx, std::shared_ptr<rs2::software_sensor> ss, std::string sensor_name, rs2::video_stream_profile c, rs2::video_stream_profile d)
{
    sctx.sw_stream_profiles[sensor_name][RS2_STREAM_DEPTH] = init_stream_profile(ss, d);
    sctx.sw_stream_profiles[sensor_name][RS2_STREAM_COLOR] = init_stream_profile(ss, c);
    std::vector<rs2::stream_profile> profiles = {
        sctx.sw_stream_profiles[sensor_name][RS2_STREAM_DEPTH],
        sctx.sw_stream_profiles[sensor_name][RS2_STREAM_COLOR]
    };
    return profiles;
}

sw_context init_sw_device(std::vector<rs2::video_stream_profile> depth_profiles,
    std::vector<rs2::video_stream_profile> color_profiles, float depth_units)
{
    sw_context sctx;
    for (auto depth_profile : depth_profiles)
    {
        for (auto color_profile : color_profiles)
        {
            if (depth_profile.width() == color_profile.width() && depth_profile.height() == color_profile.height())
                continue;

            std::string name = get_sensor_name(color_profile, depth_profile);
            auto sensor = std::make_shared<rs2::software_sensor>(sctx.sdev.add_sensor(name));

            sensor->add_read_only_option(RS2_OPTION_DEPTH_UNITS, depth_units);

            sensor->open(init_stream_profiles(sctx, sensor, name, color_profile, depth_profile));
            rs2::syncer sync;
            sensor->start(sync);

            sctx.sw_sensors[name] = sensor;
            sctx.sw_syncers[name] = sync;
        }
    }
    return sctx;
}

void record_sw_frame(std::string sensor_name, rs2::frameset fs, sw_context sctx)
{
    auto ss = sctx.sw_sensors[sensor_name];
    ss->on_video_frame(create_sw_frame(fs.get_depth_frame(), fs.get_depth_frame().get_profile().as<rs2::video_stream_profile>()));
    ss->on_video_frame(create_sw_frame(fs.get_color_frame(), fs.get_color_frame().get_profile().as<rs2::video_stream_profile>()));
    ss->stop();
    ss->close();
}

std::vector<rs2::frameset> get_composite_frames(std::vector<rs2::sensor> sensors)
{
    std::vector<rs2::frameset> composite_frames;

    std::deque<rs2::frame> color_frames;
    std::deque<rs2::frame> depth_frames;
    std::vector<rs2::frame> frame_pairs;
    std::mutex frame_processor_lock;
    rs2::processing_block frame_processor([&](rs2::frame data, rs2::frame_source& source)
    {
            auto s = rs2::sensor_from_frame(data);
           // s->get_info();
        std::lock_guard<std::mutex> lock(frame_processor_lock);
        switch (data.get_profile().stream_type())
        {
        case RS2_STREAM_DEPTH:
            depth_frames.push_back(data);
            break;
        case RS2_STREAM_COLOR:
            color_frames.push_back(data);
            break;
        default:
            FAIL("bag file should contain only color and depth frames, got " << data.get_profile().stream_name());
            break;
        }

        // if we got a color and a depth frame, create a composite frame from it and dispatch it
        if (!depth_frames.empty() && !color_frames.empty())
        {
            frame_pairs.push_back(depth_frames.front());
            frame_pairs.push_back(color_frames.front());
            source.frame_ready(source.allocate_composite_frame(frame_pairs));
            frame_pairs.clear();
            depth_frames.pop_front();
            color_frames.pop_front();
        }
    });

    rs2::frame_queue postprocessed_frames;
    frame_processor >> postprocessed_frames;

    for (auto s : sensors)
    {
        s.open(s.get_stream_profiles());
    }

    std::cout << "test starting sensors" << std::endl;
    for (auto s : sensors)
    {
        s.start([&](rs2::frame f)
        {
            frame_processor.invoke(f);
        });
    }

    while (composite_frames.size() < sensors.size())
    {
        rs2::frameset composite_fs;
        if (postprocessed_frames.try_wait_for_frame(&composite_fs))
        {
            composite_fs.keep();
            composite_frames.push_back(composite_fs);
        }
    }

    std::cout << "test stopping sensors" << std::endl;
    for (auto s : sensors)
    {
        s.stop();
        s.close();
    }

    return composite_frames;
}

std::vector<rs2::frame> get_frames(std::vector<rs2::sensor> sensors)
{
    std::vector<rs2::frame> frames;
    std::mutex frames_lock;

    for (auto s : sensors)
    {
        s.open(s.get_stream_profiles());
    }

    for (auto s : sensors)
    {
        s.start([&](rs2::frame f)
        {
            std::lock_guard<std::mutex> lock(frames_lock);
            if (frames.size() < sensors.size())
            {
                f.keep();
                //std::cout << f.get_frame_number() << std::endl;
                frames.push_back( f );
            }
        });
    }

    while (true)
    {
        {
            std::lock_guard<std::mutex> lock(frames_lock);
            if ( frames.size() >= sensors.size() )
                break;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    } 


    for (auto s : sensors)
    {
        s.stop();
        s.close();
    }

    return frames;
}

sw_context init_sw_device(std::vector<std::string> sensor_names, std::vector<rs2::frame> processed_frames)
{
    sw_context sctx;
    for (int i = 0; i < processed_frames.size(); i++)
    {
        auto processed_frame = processed_frames[i];

        auto sensor = std::make_shared<rs2::software_sensor>(sctx.sdev.add_sensor(sensor_names[i]));

        auto profile = processed_frame.get_profile().as<rs2::video_stream_profile>();

        sctx.sw_stream_profiles[sensor_names[i]][profile.stream_type()] = init_stream_profile(sensor, profile);

        sensor->open(sctx.sw_stream_profiles[sensor_names[i]][profile.stream_type()]);
        rs2::syncer sync;
        sensor->start(sync);

        sctx.sw_sensors[sensor_names[i]] = sensor;
        sctx.sw_syncers[sensor_names[i]] = sync;
    }
    return sctx;
}

void record_frames_all_res(processing_recordable_block& record_block, std::string file)
{
    rs2::context ctx;
    if (!make_context(SECTION_FROM_TEST_NAME, &ctx))
        return;

    std::string folder_name = get_folder_path(special_folder::temp_folder);
    auto dev = ctx.load_device(folder_name + "all_combinations_depth_color.bag");
    dev.set_real_time(false);

    std::cout << "Recording was loaded" << std::endl;

    std::vector<rs2::sensor> sensors = dev.query_sensors();
    auto original_frames = get_composite_frames(sensors);

    std::cout << "Received all recorded composite frames" << std::endl;

    std::vector<rs2::frame> processed_frames;
    std::vector<std::string> sensor_names;

    for (auto f : original_frames)
    {
        auto processed_frame = record_block.process(f);
        processed_frame.get_data();
        processed_frame.keep();
        processed_frames.push_back(processed_frame);

        auto color_stream_profile = f.get_color_frame().get_profile().as<rs2::video_stream_profile>();
        auto depth_stream_profile = f.get_depth_frame().get_profile().as<rs2::video_stream_profile>();
        sensor_names.push_back(get_sensor_name(color_stream_profile, depth_stream_profile));
    }
    std::cout << "All frames were processed" << std::endl;

    auto sctx = init_sw_device(sensor_names, processed_frames);
    rs2::recorder recorder(folder_name + file, sctx.sdev);

    std::cout << "SW device initialized" << std::endl;

    for (int i = 0; i < processed_frames.size(); i++)
    {
        record_block.record(sensor_names[i], processed_frames[i], sctx);
    }
    std::cout << "All frames were recorded" << std::endl;

    std::cout << "Done" << std::endl;
}

void validate_ppf_results(const rs2::frame& result_frame, const rs2::frame& reference_frame)
{
    std::cout << "1" << std::endl;

    auto result_profile = result_frame.get_profile().as<rs2::video_stream_profile>();
    std::cout << "2" << std::endl;
    REQUIRE(result_profile);
    CAPTURE(result_profile.width());
    CAPTURE(result_profile.height());
    CAPTURE(result_profile.format());
    std::cout << "3" << std::endl;

    auto reference_profile = reference_frame.get_profile().as<rs2::video_stream_profile>();
    std::cout << "4" << std::endl;
    REQUIRE(reference_profile);
    CAPTURE(reference_profile.width());
    CAPTURE(reference_profile.height());
    CAPTURE(reference_profile.format());
    std::cout << "5" << std::endl;

    REQUIRE(result_profile.width() == reference_profile.width());
    REQUIRE(result_profile.height() == reference_profile.height());
    std::cout << "6" << std::endl;
    size_t pixels_as_bytes = reference_frame.as<rs2::video_frame>().get_bytes_per_pixel() * result_profile.width() * result_profile.height();
    std::cout << "7" << std::endl;
    // Pixel-by-pixel comparison of the resulted filtered depth vs data ercorded with external tool
    auto v1 = reinterpret_cast<const uint8_t*>(result_frame.get_data());
    auto v2 = reinterpret_cast<const uint8_t*>(reference_frame.get_data());
    std::cout << "8" << std::endl;
    REQUIRE(std::memcmp(v1, v2, pixels_as_bytes) == 0);
    std::cout << "9" << std::endl;
}

void compare_processed_frames_vs_recorded_frames(processing_recordable_block& record_block, std::string file)
{
    rs2::context ctx;
    if (!make_context(SECTION_FROM_TEST_NAME, &ctx))
        return;

    std::string folder_name = get_folder_path(special_folder::temp_folder);

    std::cout << "loading first device from file" << std::endl;
    auto dev = ctx.load_device(folder_name + "all_combinations_depth_color.bag");
    dev.set_real_time(false);

    std::vector<rs2::sensor> sensors = dev.query_sensors();
    std::cout << "calling get_composite_frames" << std::endl;

    auto frames = get_composite_frames(sensors);

    std::cout << "loading second device from file" << std::endl;

    auto ref_dev = ctx.load_device(folder_name + file);
    ref_dev.set_real_time(false);

    std::vector<rs2::sensor> ref_sensors = ref_dev.query_sensors();
    std::cout << "calling get_frames" << std::endl;

    auto ref_frames = get_frames(ref_sensors);
    std::cout << "after get_frames" << std::endl;

    CAPTURE(ref_frames.size());
    CAPTURE(frames.size());
    REQUIRE(ref_frames.size() == frames.size());
    std::cout << "---------------------------------------------------------------------------------------------" << std::endl;
    std::cout << "Calculated time interval to process frame" << std::endl;
    std::cout << "---------------------------------------------------------------------------------------------" << std::endl;
    for (int i = 0; i < frames.size(); i++)
    {
        CAPTURE(i);
        REQUIRE(frames[i]);
        std::cout << "org frame i = " << i << " " << frame_to_string(frames[i]) << std::endl;
        auto df = frames[i].get_depth_frame();
        REQUIRE(df);
        auto d = df.get_profile().as<rs2::video_stream_profile>();

        auto cf = frames[i].get_color_frame();
        REQUIRE(cf);
        auto c = cf.get_profile().as<rs2::video_stream_profile>();


        auto started = std::chrono::high_resolution_clock::now();
        auto fs_res = record_block.process(frames[i]);
        REQUIRE(fs_res);
        //std::cout << "processed i = " << i << " " << frame_to_string(fs_res) << std::endl;
        //std::cout << "reference i = " << i << " " << frame_to_string(ref_frames[i]) << std::endl;

        auto done = std::chrono::high_resolution_clock::now();

        std::cout << "DEPTH " << std::setw(4) << d.format() << " " << std::setw(10) << std::to_string(d.width()) + "x" + std::to_string(d.height()) << " | " <<
            "COLOR " << std::setw(6) << c.format() << " " << std::setw(10) << std::to_string(c.width()) + "x" + std::to_string(c.height()) << std::setw(4) << " [" <<
            std::setw(6) << std::chrono::duration_cast<std::chrono::microseconds>(done - started).count() << " us]" << std::endl;

        std::cout << "i = " << i << ", before validate_ppf_results" << std::endl;
        validate_ppf_results(fs_res, ref_frames[i]);
        std::cout << "i = " << i << ", after validate_ppf_results" << std::endl;
    }
    std::cout << "end of test" << std::endl;
}

TEST_CASE("Record software-device all resolutions", "[record-bag]")
{
    rs2::context ctx;
    if (!make_context(SECTION_FROM_TEST_NAME, &ctx))
        return;

    auto dev = ctx.query_devices()[0];
    auto sensors = dev.query_sensors();

    std::vector<rs2::video_stream_profile> depth_profiles;
    for (auto p : sensors[0].get_stream_profiles())
    {
        if (p.stream_type() == rs2_stream::RS2_STREAM_DEPTH)
        {
            auto pv = p.as<rs2::video_stream_profile>();
            if (!std::any_of(depth_profiles.begin(), depth_profiles.end(), [&](rs2::video_stream_profile i)
            {
                return i.height() == pv.height() && i.width() == pv.width() && i.format() == pv.format();
            }))
            {
                depth_profiles.push_back(pv);
            }
        }
    }

    std::vector<rs2::video_stream_profile> color_profiles;
    for (auto p : sensors[1].get_stream_profiles())
    {
        if (p.stream_type() == rs2_stream::RS2_STREAM_COLOR)
        {
            auto pv = p.as<rs2::video_stream_profile>();
            if (!std::any_of(color_profiles.begin(), color_profiles.end(), [&](rs2::video_stream_profile i)
            {
                return i.height() == pv.height() || i.width() == pv.width() || i.format() == pv.format();
            }))
            {
                color_profiles.push_back(pv);
            }
        }
    }

    auto sctx = init_sw_device(depth_profiles, color_profiles, sensors[0].get_option(RS2_OPTION_DEPTH_UNITS));
    std::string folder_name = get_folder_path(special_folder::temp_folder);
    rs2::recorder recorder(folder_name + "all_combinations_depth_color.bag", sctx.sdev);

    for (auto depth_profile : depth_profiles)
    {
        for (auto color_profile : color_profiles)
        {
            if (depth_profile.width() == color_profile.width() && depth_profile.height() == color_profile.height())
                continue;
            rs2::syncer sync;
            sensors[0].open(depth_profile);
            sensors[1].open(color_profile);

            sensors[0].start(sync);
            sensors[1].start(sync);

            while (true)
            {
                auto fs = sync.wait_for_frames();
                if (fs.size() == 2)
                {
                    std::cout << "Recording : " << "Depth : " << depth_profile.format() << " " << depth_profile.width() << "x" << depth_profile.height() <<
                        ", Color : " << color_profile.format() << " " << color_profile.width() << "x" << color_profile.height() << std::endl;
                    std::string sensor_name = get_sensor_name(color_profile, depth_profile);
                    record_sw_frame(sensor_name, fs, sctx);
                    break;
                }
            }
            sensors[0].stop();
            sensors[1].stop();
            sensors[0].close();
            sensors[1].close();
        }
    }
}

TEST_CASE("Record align color to depth software-device all resolutions", "[record-bag][align]")
{
    auto record_block = align_record_block(RS2_STREAM_DEPTH, RS2_STREAM_COLOR);
    record_frames_all_res(record_block, "[aligned_2d]_all_combinations_depth_color.bag");
}

TEST_CASE("Record align depth to color software-device all resolutions", "[record-bag][align]")
{
    auto record_block = align_record_block(RS2_STREAM_COLOR, RS2_STREAM_DEPTH);
    record_frames_all_res(record_block, "[aligned_2c]_all_combinations_depth_color.bag");
}

TEST_CASE("Record point cloud software-device all resolutions", "[record-bag][point-cloud]")
{
    auto record_block = pointcloud_record_block();
    record_frames_all_res(record_block, "[pointcloud]_all_combinations_depth_color.bag");
}

TEST_CASE("Test align color to depth from recording", "[software-device][align]")
{
    auto record_block = align_record_block(RS2_STREAM_DEPTH, RS2_STREAM_COLOR);
    compare_processed_frames_vs_recorded_frames(record_block, "[aligned_2d]_all_combinations_depth_color.bag");
}

TEST_CASE("Test align depth to color from recording", "[software-device][align]")
{
    auto record_block = align_record_block(RS2_STREAM_COLOR, RS2_STREAM_DEPTH);
    compare_processed_frames_vs_recorded_frames(record_block, "[aligned_2c]_all_combinations_depth_color.bag");
}

TEST_CASE("Test point cloud from recording", "[software-device][point-cloud]")
{
    auto record_block = pointcloud_record_block();
    compare_processed_frames_vs_recorded_frames(record_block, "[pointcloud]_all_combinations_depth_color.bag");
}
