// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

#include "v4l-enumerator.h"

#include "v4l-ioctl.h"
#include "v4l-mipi-logic.h"
#include "v4l-usb-logic.h"
#include "types.h"
#include <src/librealsense-exception.h>
#include <src/platform/mipi-device-info.h>
#include <rsutils/string/from.h>
#include <rsutils/accelerators/gpu.h>

#include <algorithm>
#include <cstring>
#include <fstream>
#include <map>
#include <regex>
#include <set>
#include <sstream>

#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#include <linux/videodev2.h>

namespace librealsense
{
    namespace platform
    {
        namespace v4l_enum
        {
        std::vector<path_and_identifier> collect_dev_video_path_and_identifier()
        {
            // building vector of /dev/videoX files with path, major, minor
            std::vector<path_and_identifier> dev_videos;
            DIR * dev_dir = opendir("/dev");
            if (!dev_dir)
            {
                LOG_ERROR("Cannot access /dev");
                throw linux_backend_exception(rsutils::string::from() << "Cannot access /dev");
            }

            // searching for match in /dev, in means of major, minor
            while (dirent * entry = readdir(dev_dir))
            {
                std::string name = entry->d_name;
                std::string dev_path = "/dev/" + name;

                struct stat st = {};
                if (stat(dev_path.c_str(), &st) < 0)
                {
                    continue;
                }
                dev_videos.push_back({dev_path, {major(st.st_rdev), minor(st.st_rdev)}});
            }
            closedir(dev_dir);

            return dev_videos;
        }

        bool get_identifier_from_v4l_video_path(const std::string& v4l_video_path, identifier& key)
        {
            // dev file is in paths:
            // - /sys/class/video4linux/videoX/dev for video files
            // - /sys/class/d4xx-class/d4xx-dfu-30-XXXa for mipi dfu files

            // dev file contains major_number:minor_number
            // while major_number is typically 81 for video4linux devices and 506 for d4xx-class devices

            std::ifstream dev_file(v4l_video_path + "/dev");
            if (!dev_file)
            {
                LOG_ERROR("Cannot access " + v4l_video_path + "/dev");
                return false;
            }

            std::string dev_line;
            std::getline(dev_file, dev_line);
            char sep = '\0';
            std::istringstream iss(dev_line);
            if (!(iss >> key.major >> sep >> key.minor) || sep != ':') {
                LOG_ERROR("Could not read major and minor from " + v4l_video_path + "/dev");
                return false;
            }
            return true;
        }

        std::vector<std::pair <std::string, std::string>> generate_v4l_to_dev_video_paths(const std::vector<path_and_identifier>& v4l_videos,
                                                                                                          const std::vector<path_and_identifier>& dev_videos)
        {
            std::vector<std::pair<std::string, std::string>> v4l_to_dev_video_paths;

            // going over video paths like /sys/class/video4linux/videoX
            // find their mapping in /dev/videoY
            // above videoX and videoY are often the same, but not always
            // for example when working with unprivileged containers, the name in /dev may not contain the string "video"
            // it depends on how the devices have been mapped (bind-mounted) into the container
            for(auto&& v4l_video : v4l_videos)
            {
                // searching for match in /dev, in means of major, minor
                for (auto&& dev_video : dev_videos)
                {
                    if (v4l_video.key== dev_video.key)
                    {
                        v4l_to_dev_video_paths.push_back(std::make_pair(v4l_video.path, dev_video.path));
                        break;
                    }
                }
            }
            return v4l_to_dev_video_paths;
        }

        bool get_devname_from_mipi_dfu_path(const path_and_identifier& dfu_path, std::string& dev_name)
        {
            DIR * dev_dir = opendir("/dev");
            if (!dev_dir)
            {
                LOG_ERROR("Cannot access /dev");
                throw linux_backend_exception(rsutils::string::from() << "Cannot access /dev");
            }

            // searching for match in /dev, in means of major, minor
            while (dirent * entry = readdir(dev_dir))
            {
                std::string name = entry->d_name;
                if (name.compare(0, 8, "d4xx-dfu") != 0)
                {
                    continue;
                }
                std::string dev_path = "/dev/" + name;

                struct stat st = {};
                if (stat(dev_path.c_str(), &st) < 0)
                {
                    continue;
                }
                identifier st_key {major(st.st_rdev), minor(st.st_rdev)};
                if (dfu_path.key == st_key)
                {
                    dev_name = name;
                    closedir(dev_dir);
                    return true;
                }
            }
            closedir(dev_dir);
            return false;
        }

        bool get_devname_from_v4l_video_path(const std::string& v4l_video_path, std::string& dev_name,
                                                         const std::vector<std::pair <std::string, std::string>>& v4l_to_dev_video_paths)
        {
            for (auto&& v4l_to_dev_pair : v4l_to_dev_video_paths)
            {
                if (v4l_to_dev_pair.first == v4l_video_path)
                {
                    dev_name = v4l_to_dev_pair.second;
                    return true;
                }
            }
            return false;
        }

        std::vector<path_and_identifier> collect_v4l_video_path_and_identifier()
        {
            std::vector<path_and_identifier> v4l_videos;
            // Enumerate all subdevices present on the system
            DIR * dir = opendir("/sys/class/video4linux");
            if(!dir)
            {
                LOG_INFO("Cannot access /sys/class/video4linux");
                return v4l_videos;
            }
            while (dirent * entry = readdir(dir))
            {
                std::string name = entry->d_name;
                if(name == "." || name == "..") continue;

                // Resolve a pathname to ignore virtual video devices and  sub-devices
                static const std::regex video_dev_pattern("(\\/video\\d+)$");

                std::string path = "/sys/class/video4linux/" + name;
                std::string v4l_path{};
                char buff[PATH_MAX] = {0};
                if (realpath(path.c_str(), buff) != nullptr)
                {
                    v4l_path = std::string(buff);
                    if (v4l_path.find("virtual") != std::string::npos)
                        continue;
                    if (!std::regex_search(v4l_path, video_dev_pattern))
                    {
                        //LOG_INFO("Skipping Video4Linux entry " << v4l_path << " - not a device");
                        continue;
                    }
                    identifier key{0, 0};
                    if (!get_identifier_from_v4l_video_path(v4l_path, key))
                        continue;

                    v4l_videos.push_back({v4l_path, key});
                }
            }
            closedir(dir);

            // UVC nodes shall be traversed in ascending order for metadata nodes assignment ("dev/video1, Video2..
            // Replace lexicographic with numeric sort to ensure "video2" is listed before "video11"
            std::sort(v4l_videos.begin(), v4l_videos.end(),
                      [](const path_and_identifier& first, const path_and_identifier& second)
            {
                // getting videoXX
                std::string first_video = first.path.substr(first.path.find_last_of('/') + 1);
                std::string second_video = second.path.substr(second.path.find_last_of('/') + 1);

                // getting the index XX from videoXX
                std::stringstream first_index(first_video.substr(first_video.find_first_of("0123456789")));
                std::stringstream second_index(second_video.substr(second_video.find_first_of("0123456789")));
                int left_id = 0, right_id = 0;
                first_index >> left_id;
                second_index >> right_id;
                return left_id < right_id;
            });
            return v4l_videos;
        }

        std::vector<std::string> get_mipi_dfu_paths()
        {
            std::vector<std::string> dfu_paths;
            static const std::regex dfu_dev_pattern("./d4xx-dfu.");
            // Enumerate all d4xx dfu devices present on the system
            DIR * dir = opendir("/sys/class/d4xx-class");
            if(!dir)
            {
                LOG_INFO("Cannot access /sys/class/d4xx-class");
                return dfu_paths;
            }
            while (dirent * entry = readdir(dir))
            {
                std::string name = entry->d_name;
                if(name == "." || name == "..") continue;
                std::string path = "/sys/class/d4xx-class/" + name;
                std::string real_path{};
                char buff[PATH_MAX] = {0};
                if (realpath(path.c_str(), buff) != nullptr)
                {
                    real_path = std::string(buff);
                    if (real_path.find("virtual") == std::string::npos)
                        continue;
                    if (!std::regex_search(real_path, dfu_dev_pattern))
                    {
                        continue;
                    }
                    identifier key{0, 0};
                    if (!get_identifier_from_v4l_video_path(real_path, key))
                    {
                        continue;
                    }

                    path_and_identifier dfu_path {real_path, key};
                    std::string devname;
                    if (get_devname_from_mipi_dfu_path(dfu_path, devname))
                    {
                        if (devname.empty())
                        {
                            LOG_ERROR("No DEVNAME found for " + real_path);
                            continue;
                        }
                        if ( std::find(dfu_paths.begin(), dfu_paths.end(), devname) == dfu_paths.end() )
                        {
                            dfu_paths.push_back(devname);
                        }
                    }
                    else
                    {
                        continue;
                    }
                }
            }
            closedir(dir);
            return dfu_paths;
        }

        // True iff the string looks like a kernel i2c client id — digits, one
        // '-', then hex. Kernel uses snprintf("%d-%04x", adapter, addr).
        static bool is_i2c_id_shape(const std::string& s)
        {
            auto sep = s.find('-');
            if (sep == std::string::npos || sep == 0 || sep + 1 >= s.size())
                return false;
            auto is_digit = [](char c) { return c >= '0' && c <= '9'; };
            auto is_hex   = [](char c) {
                return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
            };
            return std::all_of(s.begin(), s.begin() + sep, is_digit)
                && std::all_of(s.begin() + sep + 1, s.end(), is_hex);
        }

        // Extract the i2c client id ("<adapter>-<addr>") from a DFU chardev name.
        // The driver names its CONFIG_OF chardev "d4xx-dfu-<adapter>-<addr>";
        // the rs-enum path uses the shorter "d4xx-dfu-<index>" form for which
        // per-i2c resolution is not possible. Returns "" on any non-conforming
        // name — callers fall back accordingly.
        static std::string dfu_devname_to_i2c_id(const std::string& dfu_devname)
        {
            static const std::string prefix = "d4xx-dfu-";
            if (dfu_devname.compare(0, prefix.size(), prefix) != 0)
                return {};
            std::string rest = dfu_devname.substr(prefix.size());
            return is_i2c_id_shape(rest) ? rest : std::string{};
        }

        // Read the DT `compatible` of a DFU chardev's owning i2c client via
        // /sys/bus/i2c/devices/<adapter>-<addr>/of_node/compatible. Returns
        // true when any entry equals "realsense,d5xx". `compatible` is a
        // concatenation of NUL-terminated strings, so we walk tokens rather
        // than substring-search (avoids matching "realsense,d5xxfoo").
        // Returns false for rs-enum-style short chardev names that cannot be
        // resolved to an i2c address.
        static bool mipi_dfu_devname_is_d5xx(const std::string& dfu_devname)
        {
            std::string i2c_id = dfu_devname_to_i2c_id(dfu_devname);
            if (i2c_id.empty())
            {
                LOG_DEBUG("MIPI DFU family detection: cannot parse i2c id from "
                          << dfu_devname << ", defaulting to D4xx");
                return false;
            }
            std::string compat_path = "/sys/bus/i2c/devices/" + i2c_id + "/of_node/compatible";
            std::ifstream compat_in(compat_path, std::ios::binary);
            if (!compat_in)
            {
                LOG_DEBUG("MIPI DFU family detection: cannot open " << compat_path
                          << ", defaulting to D4xx");
                return false;
            }
            std::string compat((std::istreambuf_iterator<char>(compat_in)), std::istreambuf_iterator<char>());
            static const std::string target = "realsense,d5xx";
            for (size_t pos = 0; pos < compat.size(); )
            {
                size_t end = compat.find('\0', pos);
                if (end == std::string::npos)
                    end = compat.size();
                if (compat.compare(pos, end - pos, target) == 0)
                    return true;
                pos = end + 1;
            }
            return false;
        }

        void foreach_mipi_device(
                std::function<void(const mipi_device_info&,
                                   const std::string&)> action)
        {
            typedef std::pair<mipi_device_info,std::string> node_info;
            std::vector<node_info> mipi_devices;

            std::vector<std::string> mipi_dfu_paths = get_mipi_dfu_paths();
            for(auto it = mipi_dfu_paths.begin(); mipi_dfu_paths.size() && it != mipi_dfu_paths.end(); ++it)
            {
                auto mipi_dfu_path = "/dev/" + *it;
                std::string dfu_ver;
                for (int retry = 10; retry; retry--) {
                    std::ifstream fw_path_in_device(mipi_dfu_path);
                    std::getline(fw_path_in_device, dfu_ver);
                    if (dfu_ver.size()) {
                        fw_path_in_device.close();
                        break;
                    }
                    fw_path_in_device.close();
                }
                // look for "recovery" string, if no - skip.
                if (dfu_ver.find("recovery") == std::string::npos)
                    continue;
                mipi_device_info info{};
                // The DFU chardev read format is identical for D4xx and D5xx in recovery
                // ("DFU info: recovery: <serial>"); derive the family from the DT compatible.
                const bool is_d5xx = mipi_dfu_devname_is_d5xx(*it);
                info.pid = is_d5xx ? 0xbbdd : 0xbbcd;   // D500_MIPI_RECOVERY_PID / RS400_MIPI_RECOVERY_PID
                info.vid = is_d5xx ? 0x38e5 : 0x8086;   // VID_REALSENSE_CAMERA (D5xx) / VID_INTEL_CAMERA (D4xx)
                info.id = *it;
                info.device_path = mipi_dfu_path;
                info.unique_id = *it;
                info.dfu_device_path = mipi_dfu_path;
                // The expected string is  "DFU info:  recovery:  209443110028"
                std::string delimiter = ":";
                dfu_ver.erase(0, dfu_ver.find(delimiter) + delimiter.length());
                dfu_ver.erase(0, dfu_ver.find(delimiter) + delimiter.length());
                // Trim leading whitespace
                dfu_ver.erase(0, dfu_ver.find_first_not_of(' '));
                info.serial_number = dfu_ver;
                mipi_devices.emplace_back(info, *it);
            }
            try
            {
                // Dispatch registration for enumerated MIPI Recovery devices
                for (auto&& dev : mipi_devices)
                    action(dev.first, dev.second);
            }
            catch(const std::exception & e)
            {
                LOG_ERROR("Registration of MIPI recovery device failed: " << e.what());
            }
        }

        std::vector<node_info> match_video_with_metadata_nodes(const std::vector<node_info>& uvc_nodes)
        {
            // Assume uvc_nodes is already sorted according to videoXX (video0, then video1...)
            // Assume for each metadata node with index N there is a origin streaming node with index (N-1)
            std::vector<node_info> uvc_devices;
            for (auto&& cur_node : uvc_nodes)
            {
                try
                {
                    if (!(cur_node.first.uvc_capabilities & V4L2_CAP_META_CAPTURE))
                        uvc_devices.emplace_back(cur_node);
                    else
                    {
                        if (uvc_devices.empty())
                        {
                            LOG_ERROR("UVC meta-node with no video streaming node encountered: " << std::string(cur_node.first));
                            continue;
                        }

                        // Update the preceding uvc item with metadata node info
                        auto uvc_node = uvc_devices.back();

                        if (uvc_node.first.uvc_capabilities & V4L2_CAP_META_CAPTURE)
                        {
                            LOG_ERROR("Consequtive UVC meta-nodes encountered: " << std::string(uvc_node.first) << " and " << std::string(cur_node.first) );
                            continue;
                        }

                        if (uvc_node.first.has_metadata_node)
                        {
                            LOG_ERROR( "Metadata node for uvc device: " << std::string(uvc_node.first) << " was previously assigned ");
                            continue;
                        }

                        // modify the last element with metadata node info
                        uvc_node.first.has_metadata_node = true;
                        uvc_node.first.metadata_node_id = cur_node.first.id;
                        uvc_devices.back() = uvc_node;
                    }
                }
                catch(const std::exception & e)
                {
                    LOG_ERROR("Failed to map meta-node "  << std::string(cur_node.first) <<", error encountered: " << e.what());
                }
            }
            return uvc_devices;
        }

        uvc_device_info get_info_from_usb_device_path( const std::string & video_path,
                                                                       const std::string & dev_name,
                                                                       const std::string & name )
        {
            std::string busnum, devnum, devpath;

            if (!v4l_usb_logic::is_usb_path_valid(video_path, dev_name, busnum, devnum, devpath))
            {
#ifndef RS2_USE_CUDA
                if (rsutils::rs2_is_cuda_available())
                {
                    /* On the Jetson TX, the camera module is CSI & I2C and does not report as this code expects
                    Patch suggested by JetsonHacks: https://github.com/jetsonhacks/buildLibrealsense2TX */
                    LOG_INFO("Failed to read busnum/devnum. Device Path: " << ("/sys/class/video4linux/" + name));
                }
#endif
               throw linux_backend_exception("Failed to read busnum/devnum of usb device");
            }

            LOG_INFO("Enumerating UVC " << name << " v4l_path=" << video_path << " dev_name=" << dev_name);

            camera_identifier_v4l_usb usb_id;
            usb_id.resolve(name);

            uvc_device_info info{};
            info.pid = usb_id.get_pid();
            info.vid = usb_id.get_vid();
            info.mi = v4l_usb_logic::read_interface_number(name);
            info.id = dev_name;
            info.device_path = video_path;
            info.unique_id = busnum + "-" + devpath + "-" + devnum;
            // Find the USB specification (USB2/3) type from the underlying device, traversing from
            // /sys/devices/.../M-N/3-6:1.0/video4linux/video0 up to /sys/devices/.../M-N/version
            info.usb_conn_spec = v4l_usb_logic::get_usb_connection_type(video_path + "/../../../");
            info.uvc_capabilities = get_dev_capabilities(dev_name).device_caps;

            return info;
        }

        uvc_device_info get_info_from_mipi_device_path(const std::string& video_path, const std::string& name,
                                                                       camera_identifier_v4l_mipi& mipi_id)
        {
            auto dev_name = "/dev/" + name;

            std::string bus_info, card;
            v4l_mipi_logic::get_device_info(dev_name, bus_info, card);

            // Resolve PID/VID from the depth node; sibling color/IR/IMU nodes inherit it via mipi_id
            try
            {
                if (v4l_mipi_logic::is_device_depth_node(dev_name))
                    mipi_id.resolve(dev_name);
            }
            catch(const std::exception & e)
            {
                LOG_WARNING("MIPI device product id detection issue, device will be skipped: " << e.what());
                mipi_id.reset();
            }

            uint16_t mi{};
            int cam_id{};
            v4l_mipi_logic::derive_mi_and_cam_id(v4l_mipi_logic::parse_video_index(name), mi, cam_id);

            uvc_device_info info{};
            info.pid = mipi_id.get_pid();
            info.vid = mipi_id.get_vid();
            info.mi = mi;
            info.id = dev_name;
            info.device_path = video_path;
            // unique id for MIPI: This will assign sensor set for each camera. It cannot be generated as in usb,
            // because the params busnum, devpath and devnum are not available via mipi.
            // Assign unique id for mipi by appending camera id to bus_info (bus_info is same for each mipi port)
            // Note - jetson can use only bus_info, as card is different for each sensor and metadata node.
            info.unique_id = bus_info + "-" + std::to_string(cam_id);

            // Get DFU node for MIPI camera
            for (const auto& dfu_device_path : get_mipi_dfu_paths())
            {
                auto mipi_dfu_chardev = "/dev/" + dfu_device_path;
                int vfd = open(mipi_dfu_chardev.c_str(), O_RDONLY | O_NONBLOCK);
                if (vfd >= 0)
                {
                    // Use legacy DFU device node used in firmware_update_manager
                    info.dfu_device_path = mipi_dfu_chardev;
                    ::close(vfd); // file exists, close file and continue to assign it
                    break;
                }
            }
            info.usb_conn_spec = usb_undefined;
            info.is_mipi = true;
            info.uvc_capabilities = get_dev_capabilities(dev_name).device_caps;

            return info;
        }

        std::vector<node_info> get_mipi_rs_enum_nodes()
        {
            std::vector<node_info> mipi_rs_enum_nodes;

            // Enumerate mipi nodes by links with usage of rs-enum script
            std::vector<std::string> video_sensors = {"depth", "color", "ir", "imu"};
            const int MAX_V4L2_DEVICES = 8; // assume maximum 8 mipi devices

            // Carries a camera's PID/VID from its depth node to its sibling nodes
            camera_identifier_v4l_mipi mipi_id;
            for (int i = 0; i < MAX_V4L2_DEVICES; i++)
            {
                mipi_id.reset(); // reset per camera; depth node sets it, siblings inherit
                for (const auto& vs : video_sensors)
                {
                    int vfd = -1;
                    std::string device_path = v4l_mipi_logic::rs_enum_video_node_name(vs, i, false);
                    std::string device_md_path = v4l_mipi_logic::rs_enum_video_node_name(vs, i, true);
                    std::string video_path = "/dev/" + device_path;
                    std::string video_md_path = "/dev/" + device_md_path;
                    std::string dfu_device_path = v4l_mipi_logic::rs_enum_dfu_node_path(i);
                    uvc_device_info info{};

                    // Get Video node
                    // Check if file on video_path is exists
                    vfd = open(video_path.c_str(), O_RDONLY | O_NONBLOCK);

                    if (vfd < 0) // file does not exists, continue to the next one
                        continue;
                    else
                        ::close(vfd); // file exists, close file and continue to assign it
                    try
                    {
                        info = get_info_from_mipi_device_path(video_path, device_path, mipi_id);
                    }
                    catch(const std::exception & e)
                    {
                        LOG_WARNING("MIPI video device issue: " << e.what());
                        continue;
                    }

                    // Get DFU node for MIPI camera
                    vfd = open(dfu_device_path.c_str(), O_RDONLY | O_NONBLOCK);

                    if (vfd >= 0)
                    {
                        ::close(vfd); // file exists, close file and continue to assign it
                        info.dfu_device_path = dfu_device_path;
                    }

                    info.mi = vs.compare("imu") ? 0 : 4;
                    info.unique_id += "-" + std::to_string(i);
                    info.uvc_capabilities &= ~(V4L2_CAP_META_CAPTURE); // clean caps
                    mipi_rs_enum_nodes.emplace_back(info, video_path);

                    // Get metadata node
                    // Check if file on video_md_path is exists
                    vfd = open(video_md_path.c_str(), O_RDONLY | O_NONBLOCK);

                    if (vfd < 0) // file does not exists, continue to the next one
                        continue;
                    else
                        ::close(vfd); // file exists, close file and continue to assign it

                    try
                    {
                        info = get_info_from_mipi_device_path(video_md_path, device_md_path, mipi_id);
                    }
                    catch(const std::exception & e)
                    {
                        LOG_WARNING("MIPI video metadata device issue: " << e.what());
                        continue;
                    }
                    info.mi = 3;
                    info.unique_id += "-" + std::to_string(i);
                    mipi_rs_enum_nodes.emplace_back(info, video_md_path);
                }
            }
            return mipi_rs_enum_nodes;
        }

        bool get_info_from_v4l_video_path( const std::string & v4l_video_path, const std::string & dev_name,
                                                           uvc_device_info & info, bool is_mipi_rs_enum_nodes_empty, camera_identifier_v4l_mipi& mipi_id)
        {
            bool res = false;

            // following line grabs video0 from "/sys/devices/.../video0" paths
            auto name = v4l_video_path.substr(v4l_video_path.find_last_of('/') + 1);

            if (v4l_usb_logic::is_usb_device_path(v4l_video_path))
            {
                info = get_info_from_usb_device_path(v4l_video_path, dev_name, name);
                res = true;
            }
            else if(is_mipi_rs_enum_nodes_empty) //video4linux devices that are not USB devices and not previously enumerated by rs links
            {
                // filter out all possible codecs, work only with compatible driver
                static const std::regex rs_mipi_compatible(".vi:|ipu6");
                info = get_info_from_mipi_device_path(v4l_video_path, name, mipi_id);
                if (regex_search(info.unique_id, rs_mipi_compatible)) {
                    res = true;
                }
            }
            else // continue as we already have mipi nodes enumerated by rs links in uvc_nodes
            {
                // empty
            }
            return res;
        }

        std::vector<node_info> collect_uvc_nodes(const std::vector<path_and_identifier>& v4l_videos,
                                                                 const std::vector<std::pair <std::string, std::string>>& v4l_to_dev_video_paths)
        {
            std::vector<node_info> uvc_nodes = get_mipi_rs_enum_nodes();
            bool is_mipi_rs_enum_nodes_empty = uvc_nodes.empty();

            // Carries a fallback MIPI camera's PID/VID from its depth node to its sibling nodes across the loop
            camera_identifier_v4l_mipi mipi_id;
            for(auto&& v4l_video : v4l_videos)
            {
                try
                {
                    std::string dev_name;
                    if (!get_devname_from_v4l_video_path(v4l_video.path, dev_name, v4l_to_dev_video_paths))
                    {
                        continue;
                    }

                    uvc_device_info info;
                    if (get_info_from_v4l_video_path(v4l_video.path, dev_name, info, is_mipi_rs_enum_nodes_empty, mipi_id))
                    {
                        uvc_nodes.emplace_back(info, dev_name);
                    }
                }
                catch(const std::exception & e)
                {
                    LOG_INFO("Not a USB video device: " << e.what());
                }
            }

            return uvc_nodes;
        }

        // uvcvideo creates one /dev/videoN per UVC output terminal, numbered in VideoControl descriptor order, so
        // /dev/videoN order can disagree with VideoStreaming interface order (D585 2C reverses its two color
        // terminals). Sort by interface - the order Windows enumerates pins in - so a pin index means one endpoint.
        void sort_nodes_by_streaming_interface( std::vector<node_info>& nodes )
        {
            std::map<std::pair<std::string, uint16_t>, std::vector<size_t>> functions;
            for (size_t i = 0; i < nodes.size(); ++i)
                if (!nodes[i].first.is_mipi)  // a MIPI node has no USB descriptor to order by
                    functions[{ nodes[i].first.unique_id, nodes[i].first.mi }].push_back(i);

            for (auto&& function : functions)
            {
                auto& indices = function.second;
                if (indices.size() < 2)
                    continue;

                auto interfaces = v4l_usb_logic::read_streaming_interfaces_in_terminal_order(
                    nodes[indices.front()].first.device_path, function.first.second);
                if (interfaces.size() != indices.size())
                    continue;  // descriptor unreadable, or terminals with no node of their own - keep /dev/videoN order
                if (std::is_sorted(interfaces.begin(), interfaces.end()))
                    continue;  // terminals listed in interface order, as nearly every firmware does

                std::vector<std::pair<uint8_t, node_info>> group;
                for (size_t i = 0; i < indices.size(); ++i)
                    group.emplace_back(interfaces[i], nodes[indices[i]]);
                std::stable_sort(group.begin(), group.end(),
                                 [](const std::pair<uint8_t, node_info>& a, const std::pair<uint8_t, node_info>& b)
                                 { return a.first < b.first; });

                std::ostringstream reordered;
                for (size_t i = 0; i < indices.size(); ++i)
                {
                    nodes[indices[i]] = group[i].second;
                    reordered << " " << nodes[indices[i]].second;
                }
                LOG_DEBUG("Nodes of mi " << function.first.second << " reordered by streaming interface:" << reordered.str());
            }
        }

        void foreach_uvc_device( std::function<void(const uvc_device_info&, const std::string&)> action )
        {
            // building vector of /sys/class/video4linux/.../videoX files with path, major, minor
            std::vector<path_and_identifier> v4l_videos = collect_v4l_video_path_and_identifier();
            // building vector of /dev/videoX files with path, major, minor
            std::vector<path_and_identifier> dev_videos = collect_dev_video_path_and_identifier();
            // generate map of "/sys/class/video4linux/.../videoX" to "/dev/videoY"
            auto v4l_to_dev_video_paths = generate_v4l_to_dev_video_paths(v4l_videos, dev_videos);

            // Collect UVC nodes info to bundle metadata and video
            std::vector<node_info> uvc_nodes = collect_uvc_nodes(v4l_videos, v4l_to_dev_video_paths);

            // Matching video and metadata nodes
            std::vector<node_info> uvc_devices = match_video_with_metadata_nodes(uvc_nodes);

            sort_nodes_by_streaming_interface(uvc_devices);

            try
            {
                // Dispatch registration for enumerated uvc devices
                for (auto&& dev : uvc_devices)
                    action(dev.first, dev.second);
            }
            catch(const std::exception & e)
            {
                LOG_ERROR("Registration of UVC device failed: " << e.what());
            }
        }
        }  // namespace v4l_enum
    }  // namespace platform
}  // namespace librealsense
