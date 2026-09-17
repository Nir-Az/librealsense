// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#pragma once

#include "camera-identifier-v4l.h"
#include "v4l-node-info.h"

#include <src/platform/mipi-device-info.h>

#include <functional>
#include <string>
#include <utility>
#include <vector>

namespace librealsense
{
    namespace platform
    {
        namespace v4l_enum
        {
            // Walk every enumerable UVC node - USB and MIPI alike - and hand each resolved device to 'action'.
            void foreach_uvc_device( std::function<void(const uvc_device_info&, const std::string&)> action );

            // Walk MIPI devices sitting in DFU/recovery mode.
            void foreach_mipi_device( std::function<void(const mipi_device_info&, const std::string&)> action );

            std::vector<std::string> get_mipi_dfu_paths();

            std::vector<path_and_identifier> collect_v4l_video_path_and_identifier();
            bool get_identifier_from_v4l_video_path(const std::string& v4l_video_path, identifier& key);
            bool get_devname_from_v4l_video_path(const std::string& v4l_video_path, std::string& devname,
                                                    const std::vector<std::pair <std::string, std::string>>& v4l_to_dev_video_paths);
            bool get_devname_from_mipi_dfu_path(const path_and_identifier& dfu_path, std::string& dev_name);

            std::vector<std::pair <std::string, std::string>> generate_v4l_to_dev_video_paths(const std::vector<path_and_identifier>& v4l_videos,
                                                                                                     const std::vector<path_and_identifier>& dev_videos);
            std::vector<node_info> collect_uvc_nodes(const std::vector<path_and_identifier>& v4l_videos,
                                                            const std::vector<std::pair <std::string, std::string>>& v4l_to_dev_video_paths);
            std::vector<node_info> match_video_with_metadata_nodes(const std::vector<node_info>& uvc_nodes);
            void sort_nodes_by_streaming_interface(std::vector<node_info>& nodes);
            bool get_info_from_v4l_video_path(const std::string& v4l_video_path, const std::string& dev_name, uvc_device_info& info, bool is_mipi_rs_enum_nodes_empty,
                                                 camera_identifier_v4l_mipi& mipi_id);
            std::vector<node_info> get_mipi_rs_enum_nodes();
            uvc_device_info get_info_from_mipi_device_path(const std::string& video_path, const std::string& name,
                                                                  camera_identifier_v4l_mipi& mipi_id);
            uvc_device_info get_info_from_usb_device_path(const std::string& video_path, const std::string& dev_name, const std::string& name);
            std::vector<path_and_identifier> collect_dev_video_path_and_identifier();
        }  // namespace v4l_enum
    }  // namespace platform
}  // namespace librealsense
