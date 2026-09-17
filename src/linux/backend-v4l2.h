// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2015-2024 RealSense, Inc. All Rights Reserved.

#pragma once

#include "backend.h"
#include "camera-identifier-v4l.h"
#include "v4l-uvc-device.h"
#include <src/platform/uvc-device.h>
#include <src/metadata.h>
#include "types.h"

#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>

#include <algorithm>
#include <array>
#include <functional>
#include <string>
#include <sstream>
#include <fstream>
#include <regex>
#include <thread>
#include <utility> // for pair
#include <chrono>
#include <thread>
#include <atomic>

#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <limits.h>
#include <cmath>
#include <errno.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/usb/video.h>
#include <linux/uvcvideo.h>
#include <linux/videodev2.h>
#include <regex>
#include <list>


namespace librealsense
{
    namespace platform
    {

        // Composition layer for uvc/metadata split nodes introduced with kernel 4.16
        class v4l_uvc_meta_device : public v4l_uvc_device
        {
        public:
            v4l_uvc_meta_device(const uvc_device_info& info, bool use_memory_map = false);

            virtual ~v4l_uvc_meta_device();

            bool is_platform_jetson() const override {return false;}

        protected:

            virtual void streamon() const override;
            virtual void streamoff() const override;
            virtual void negotiate_kernel_buffers(size_t num) const override;
            virtual void allocate_io_buffers(size_t num) override;
            virtual void map_device_descriptor() override;
            virtual void unmap_device_descriptor() override;
            virtual void set_format(stream_profile profile) override;
            virtual void prepare_capture_buffers() override;
            virtual void acquire_metadata(buffers_mgr & buf_mgr,fd_set &fds, bool compressed_format=false) override;
            void assign_device_capabilities();
            // checking if metadata is streamed
            virtual inline bool is_metadata_streamed() const override { return _md_fd > 0;}
            virtual inline std::shared_ptr<buffer> get_md_buffer(__u32 index) const override {return _md_buffers[index];}
            int _md_fd = -1;
            std::string _md_name = "";
            v4l2_buf_type _md_type = LOCAL_V4L2_BUF_TYPE_META_CAPTURE;

            std::vector<std::shared_ptr<buffer>> _md_buffers;

        private:
            bool _are_device_capabilities_assigned;
        };


        // D457 Development. To be merged into underlying class
        class v4l_mipi_device : public v4l_uvc_meta_device
        {
        public:
            v4l_mipi_device(const uvc_device_info& info, bool use_memory_map = true);
            v4l_mipi_device(const mipi_device_info& info, bool use_memory_map = true);

            static void foreach_mipi_device(
                    std::function<void(const mipi_device_info&,
                                       const std::string&)> action);

            static std::vector<std::string> get_video_paths();

            static mipi_device_info get_info_from_mipi_device_path(
                    const std::string& video_path, const std::string& name);

            static void get_mipi_device_info(const std::string& dev_name,
                                             std::string& bus_info, std::string& card);

            virtual ~v4l_mipi_device();

            bool get_pu(rs2_option opt, int32_t& value) const override;
            bool set_pu(rs2_option opt, int32_t value) override;
            bool set_xu(const extension_unit& xu, uint8_t control, const uint8_t* data, int size) override;
            bool get_xu(const extension_unit& xu, uint8_t control, uint8_t* data, int size) const override;
            control_range get_xu_range(const extension_unit& xu, uint8_t control, int len) const override;
            control_range get_pu_range(rs2_option option) const override;
            void set_metadata_attributes(buffers_mgr& buf_mgr, __u32 bytesused, uint8_t* md_start) override;
            bool is_platform_jetson() const override;
        };

        class v4l_backend : public backend
        {
        public:
            std::shared_ptr<uvc_device> create_uvc_device(uvc_device_info info) const override;
            std::vector<uvc_device_info> query_uvc_devices() const override;

            std::shared_ptr<command_transfer> create_usb_device(usb_device_info info) const override;
            std::vector<usb_device_info> query_usb_devices() const override;

            std::shared_ptr<hid_device> create_hid_device(hid_device_info info) const override;
            std::vector<hid_device_info> query_hid_devices() const override;

            std::vector<mipi_device_info> query_mipi_devices() const override;

            std::shared_ptr<device_watcher> create_device_watcher() const override;
        };
    }
}
