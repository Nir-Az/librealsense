// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2015-2024 RealSense, Inc. All Rights Reserved.

#include "backend-v4l2.h"
#include "v4l-uvc-device.h"
#include "v4l-product-quirks.h"  // is_d5xx_product_line()
#include "v4l-enumerator-mipi.h"  // foreach_mipi_device(), for query_mipi_devices()
#include "v4l-mipi-logic.h"
#include "v4l-usb-logic.h"
#include <src/platform/command-transfer.h>
#include <src/platform/hid-data.h>
#include <src/core/time-service.h>
#include <src/core/notification.h>
#include "backend-hid.h"
#include "backend.h"
#include "types.h"
#if defined(USING_UDEV)
#include "udev-device-watcher.h"
#else
#include "../polling-device-watcher.h"
#endif
#include "usb/usb-enumerator.h"
#include "usb/usb-device.h"

#include <rsutils/string/from.h>

#include <cassert>
#include <cstdlib>
#include <cstdio>
#include <cstring>

#include <algorithm>
#include <functional>
#include <map>
#include <string>
#include <sstream>
#include <fstream>
#include <regex>
#include <thread>
#include <utility> // for pair
#include <chrono>
#include <thread>
#include <atomic>
#include <iomanip> // std::put_time

#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <limits.h>
#include <cmath>
#include <errno.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/sysmacros.h> // minor(...), major(...)
#include <linux/usb/video.h>
#include <linux/media.h>
#include <linux/uvcvideo.h>
#include <linux/videodev2.h>
#include <regex>
#include <list>

#include <cstddef> // offsetof

#include <sys/signalfd.h>
#include <signal.h>
#include "rsutils/accelerators/gpu.h"

#pragma GCC diagnostic ignored "-Woverflow"


namespace librealsense
{
    namespace platform
    {
        void v4l_mipi_device::set_metadata_attributes(buffers_mgr& buf_mgr, __u32 bytesused, uint8_t* md_start)
        {
            buf_mgr.set_md_attributes(bytesused, md_start);
        }

        bool v4l_mipi_device::is_platform_jetson() const
        {
            v4l2_capability cap = get_dev_capabilities(_name);

            std::string driver_str = reinterpret_cast<char*>(cap.driver);
            // checking if "tegra" is part of the driver string
            size_t pos = driver_str.find("tegra");
            return pos != std::string::npos;
        }

        v4l_uvc_meta_device::v4l_uvc_meta_device(const uvc_device_info& info, bool use_memory_map):
            v4l_uvc_device(info,use_memory_map),
            _md_fd(0),
            _md_name(info.metadata_node_id),
            _are_device_capabilities_assigned(false)
        {
        }

        v4l_uvc_meta_device::~v4l_uvc_meta_device()
        {
        }

        void v4l_uvc_meta_device::streamon() const
        {
            bool jetson_platform = is_platform_jetson();
            if ((_md_fd != -1) && jetson_platform)
            {
                // D457 development - added for mipi device, for IR because no metadata there
                // Metadata stream shall be configured first to allow sync with video node
                stream_ctl_on(_md_fd, _md_type);
            }

            // Invoke UVC streaming request
            v4l_uvc_device::streamon();

            // Metadata stream configured last for IPU6 and it will be in sync with video node
            if ((_md_fd != -1) && !jetson_platform)
            {
                stream_ctl_on(_md_fd, _md_type);
            }

        }

        void v4l_uvc_meta_device::streamoff() const
        {
            bool jetson_platform = is_platform_jetson();
            // IPU6 platform should stop md, then video
            if (jetson_platform)
                v4l_uvc_device::streamoff();

            if (_md_fd != -1)
            {
                // D457 development - added for mipi device, for IR because no metadata there
                stream_off(_md_fd, _md_type);
            }
            if (!jetson_platform)
                v4l_uvc_device::streamoff();
        }

        void v4l_uvc_meta_device::negotiate_kernel_buffers(size_t num) const
        {
            v4l_uvc_device::negotiate_kernel_buffers(num);

            if (_md_fd == -1)
            {
                // D457 development - added for mipi device, for IR because no metadata there
                return;
            }
            req_io_buff(_md_fd, num, _name,
                        _use_memory_map ? V4L2_MEMORY_MMAP : V4L2_MEMORY_USERPTR,
                        _md_type);
        }

        void v4l_uvc_meta_device::allocate_io_buffers(size_t buffers)
        {
            v4l_uvc_device::allocate_io_buffers(buffers);

            if (buffers)
            {
                for(size_t i = 0; i < buffers; ++i)
                {
                    // D457 development - added for mipi device, for IR because no metadata there
                    if (_md_fd == -1)
                        continue;
                    _md_buffers.push_back(std::make_shared<buffer>(_md_fd, _md_type, _use_memory_map, i));
                }
            }
            else
            {
                for(size_t i = 0; i < _md_buffers.size(); i++)
                {
                    _md_buffers[i]->detach_buffer();
                }
                _md_buffers.resize(0);
            }
        }

        void v4l_uvc_meta_device::map_device_descriptor()
        {
            v4l_uvc_device::map_device_descriptor();

            if (_md_fd>0)
                throw linux_backend_exception(rsutils::string::from() << _md_name << " descriptor is already opened");

            _md_fd = open_v4l_node(_md_name);
            if(_md_fd < 0)
            {
                return;  // Does not throw, MIPI device metadata not received through UVC, no metadata here may be valid
            }

            _fds.push_back(_md_fd);
            _max_fd = *std::max_element(_fds.begin(),_fds.end());

            if (!_are_device_capabilities_assigned)
            {
                assign_device_capabilities();
                _are_device_capabilities_assigned = true;
            }

        }

        void v4l_uvc_meta_device::assign_device_capabilities()
        {
            v4l2_capability cap = {};
            if(xioctl(_md_fd, VIDIOC_QUERYCAP, &cap) < 0)
            {
                if(errno == EINVAL)
                    throw linux_backend_exception(_md_name + " is no V4L2 device");
                else
                    throw linux_backend_exception(_md_name +  " xioctl(VIDIOC_QUERYCAP) for metadata failed");
            }

            if(!(cap.capabilities & V4L2_CAP_META_CAPTURE))
                throw linux_backend_exception(_md_name + " is not metadata capture device");

            if(!(cap.capabilities & V4L2_CAP_STREAMING))
                throw linux_backend_exception(_md_name + " does not support metadata streaming I/O");

            if(cap.capabilities & V4L2_CAP_META_CAPTURE)
                _md_type = LOCAL_V4L2_BUF_TYPE_META_CAPTURE;
        }


        void v4l_uvc_meta_device::unmap_device_descriptor()
        {
            v4l_uvc_device::unmap_device_descriptor();

            if(::close(_md_fd) < 0)
            {
                return;  // Does not throw, MIPI device metadata not received through UVC, no metadata here may be valid
            }

            _md_fd = 0;
        }

        void v4l_uvc_meta_device::set_format(stream_profile profile)
        {
            // Select video node streaming format
            v4l_uvc_device::set_format(profile);

            // Configure metadata node stream format
            v4l2_format fmt{ };
            fmt.type = _md_type;

            if (xioctl(_md_fd, VIDIOC_G_FMT, &fmt))
            {
                return;  // Does not throw, MIPI device metadata not received through UVC, no metadata here may be valid
            }

            if (fmt.type != _md_type)
                throw linux_backend_exception("ioctl(VIDIOC_G_FMT): " + _md_name + " node is not metadata capture");

            bool success = false;

            for (const uint32_t& request : { V4L2_META_FMT_D4XX, V4L2_META_FMT_UVC})
            {
                // Configure metadata format - try d4xx, then fallback to currently retrieve UVC default header of 12 bytes
                memcpy(fmt.fmt.raw_data, &request, sizeof(request));
                // use only for IPU6?
                if ((_dev.cap.capabilities & V4L2_CAP_VIDEO_CAPTURE_MPLANE) && !is_platform_jetson())
                {
                    /* Sakari patch for videodev2.h. This structure will be within kernel > 6.4 */
                    struct v4l2_meta_format {
                        uint32_t    dataformat;
                        uint32_t    buffersize;
                        uint32_t    width;
                        uint32_t    height;
                        uint32_t    bytesperline;
                    } meta;
                    // copy fmt from g_fmt ioctl
                    memcpy(&meta, fmt.fmt.raw_data, sizeof(meta));
                    // set fmt width, d4xx metadata is only one line
                    meta.dataformat = request;
                    meta.width      = profile.width;
                    meta.height     = 1;
                    memcpy(fmt.fmt.raw_data, &meta, sizeof(meta));
                }

                if(xioctl(_md_fd, VIDIOC_S_FMT, &fmt) >= 0)
                {
                    LOG_INFO("Metadata node was successfully configured to " << fourcc_to_string(request) << " format" <<", fd " << std::dec <<_md_fd);
                    success  =true;
                    break;
                }
                else
                {
                    LOG_WARNING("Metadata node configuration failed for " << fourcc_to_string(request));
                }
            }

            if (!success)
                throw linux_backend_exception(_md_name + " ioctl(VIDIOC_S_FMT) for metadata node failed");

        }

        void v4l_uvc_meta_device::prepare_capture_buffers()
        {
            if (_md_fd != -1)
            {
                // D457 development - added for mipi device, for IR because no metadata there
                // Meta node to be initialized first to enforce initial sync
                for (auto&& buf : _md_buffers) buf->prepare_for_streaming(_md_fd);
            }

            // Request streaming for video node
            v4l_uvc_device::prepare_capture_buffers();
        }

        // Retrieve metadata from a dedicated UVC node. For kernels 4.16+
        void v4l_uvc_meta_device::acquire_metadata(buffers_mgr & buf_mgr,fd_set &fds, bool)
        {
            //Use non-blocking metadata node polling
            if(_md_fd > 0 && FD_ISSET(_md_fd, &fds))
            {
                // In scenario if [md+vid] ->[md] ->[md,vid] the third md should not be retrieved but wait for next select
                if (buf_mgr.metadata_size())
                {
                    LOG_WARNING("Metadata override requested but avoided skipped");
                    // D457 wa - return removed
                    //return;
                    // In scenario: {vid[i]} ->{md[i]} ->{md[i+1],vid[i+1]}:
                    // - vid[i] will be uploaded to user callback without metadata (for now)
                    // - md[i] will be dropped
                    // - vid[i+1] and md[i+1] will be uploaded together - back to stable stream
                    auto md_buf = buf_mgr.get_buffers().at(e_metadata_buf);
                    md_buf._data_buf->request_next_frame(md_buf._file_desc,true);
                }
                FD_CLR(_md_fd,&fds);

                v4l2_buffer buf{};
                buf.type = _md_type;
                buf.memory = _use_memory_map ? V4L2_MEMORY_MMAP : V4L2_MEMORY_USERPTR;

                // W/O multiplexing this will create a blocking call for metadata node
                if(xioctl(_md_fd, VIDIOC_DQBUF, &buf) < 0)
                {
                    if (handle_enodev_on_dqbuf("md fd", _md_fd))
                        return;
                    LOG_DEBUG_V4L("Dequeued empty buf for md fd " << std::dec << _md_fd);
                }

                //V4l debugging message
                auto mdbuf = _md_buffers[buf.index]->get_frame_start();
                auto hwts = *(uint32_t*)((mdbuf+2));
                auto fn = *(uint32_t*)((mdbuf+38));
                LOG_DEBUG_V4L("Dequeued md buf " << std::dec << buf.index << " for fd " << _md_fd << " seq " << buf.sequence
                             << " fn " << fn << " hw ts " << hwts
                              << " v4lbuf ts usec " << buf.timestamp.tv_usec);

                auto buffer = _md_buffers[buf.index];
                buf_mgr.handle_buffer(e_metadata_buf, _md_fd, buf, buffer);

                // pushing metadata buffer to syncer
                _video_md_syncer.push_metadata({std::make_shared<v4l2_buffer>(buf), _md_fd, buf.index});
                buf_mgr.handle_buffer(e_metadata_buf, -1);
            }
        }

        v4l_mipi_device::v4l_mipi_device(const uvc_device_info& info, bool use_memory_map):
            v4l_uvc_meta_device(info,use_memory_map)
        {}

        v4l_mipi_device::~v4l_mipi_device()
        {}

        bool v4l_mipi_device::get_pu(rs2_option opt, int32_t& value) const
        {
            v4l2_ext_control control{v4l_mipi_logic::option_to_cid(opt), 0, 0, 0};
            // Extract the control group from the underlying control query
            v4l2_ext_controls ctrls_block { control.id&0xffff0000, 1, 0, 0, 0, &control};

            if (xioctl(_fd, VIDIOC_G_EXT_CTRLS, &ctrls_block) < 0)
            {
                if (errno == EIO || errno == EAGAIN) // TODO: Log?
                    return false;

                throw linux_backend_exception(rsutils::string::from()
                                              << "xioctl(VIDIOC_G_EXT_CTRLS) failed on option " << rs2_option_to_string(opt)
                                              << ", errno=" << errno );
            }

            if (opt == RS2_OPTION_ENABLE_AUTO_EXPOSURE)
                control.value = (V4L2_EXPOSURE_MANUAL==control.value) ? 0 : 1;
            value = control.value;

            return true;
        }

        bool v4l_mipi_device::set_pu(rs2_option opt, int32_t value)
        {
            v4l2_ext_control control{v4l_mipi_logic::option_to_cid(opt), 0, 0, value};
            if (opt == RS2_OPTION_ENABLE_AUTO_EXPOSURE)
                control.value = value ? V4L2_EXPOSURE_APERTURE_PRIORITY : V4L2_EXPOSURE_MANUAL;

            // Extract the control group from the underlying control query
            v4l2_ext_controls ctrls_block{ control.id & 0xffff0000, 1, 0, 0, 0, &control };
            if (xioctl(_fd, VIDIOC_S_EXT_CTRLS, &ctrls_block) < 0)
            {
                if (errno == EIO || errno == EAGAIN) // TODO: Log?
                    return false;

                throw linux_backend_exception(rsutils::string::from()
                                              << "xioctl(VIDIOC_S_EXT_CTRLS) failed on option " << rs2_option_to_string(opt)
                                              << ", value=" << value << ", errno=" << errno );
            }

            return true;
        }

        bool v4l_mipi_device::set_xu(const extension_unit& xu, uint8_t control, const uint8_t* data, int size)
        {
            v4l2_ext_control xctrl{v4l_mipi_logic::xu_to_cid(xu,control,is_d5xx_product_line(_info.pid)), uint32_t(size), 0, 0};
            switch (size)
            {
                case 1: xctrl.value   = *(reinterpret_cast<const uint8_t*>(data)); break;
                case 2: xctrl.value   = *reinterpret_cast<const uint16_t*>(data); break; // TODO check signed/unsigned
                case 4: xctrl.value   = *reinterpret_cast<const int32_t*>(data); break;
                case 8: xctrl.value64 = *reinterpret_cast<const int64_t*>(data); break;
                default:
                    xctrl.p_u8 = const_cast<uint8_t*>(data); // TODO aggregate initialization with union
            }

            if (v4l_mipi_logic::is_auto_exposure_control(control))
                xctrl.value = xctrl.value ? V4L2_EXPOSURE_APERTURE_PRIORITY : V4L2_EXPOSURE_MANUAL;

            // Extract the control group from the underlying control query
            v4l2_ext_controls ctrls_block { xctrl.id&0xffff0000, 1, 0, 0, 0, &xctrl };

            int retVal = xioctl(_fd, VIDIOC_S_EXT_CTRLS, &ctrls_block);
            if (retVal < 0)
            {
                if (errno == EIO || errno == EAGAIN) // TODO: Log?
                    return false;

                throw linux_backend_exception(rsutils::string::from()
                                              << "xioctl(VIDIOC_S_EXT_CTRLS) failed on control "
                                              << static_cast< int >( control ) << ", errno=" << errno );
            }
            return true;
        }

        bool v4l_mipi_device::get_xu(const extension_unit& xu, uint8_t control, uint8_t* data, int size) const
        {
            v4l2_ext_control xctrl{v4l_mipi_logic::xu_to_cid(xu,control,is_d5xx_product_line(_info.pid)), uint32_t(size), 0, 0};
            xctrl.p_u8 = data;

            v4l2_ext_controls ext {xctrl.id & 0xffff0000, 1, 0, 0, 0, &xctrl};

            // the ioctl fails once when performing send and receive right after it
            // it succeeds on the second time
            int tries = 2;
            while(tries--)
            {
                int ret = xioctl(_fd, VIDIOC_G_EXT_CTRLS, &ext);
                if (ret < 0)
                {
                    // exception is thrown if the ioctl fails twice
                    continue;
                }

                if (v4l_mipi_logic::is_auto_exposure_control(control))
                  xctrl.value = (V4L2_EXPOSURE_MANUAL == xctrl.value) ? 0 : 1;

                // used to parse the data when only a value is returned (e.g. laser power),
                // and not a pointer to a buffer of data (e.g. gvd)
                if (size < sizeof(__s64))
                    memcpy(data,(void*)(&xctrl.value), size);

                return true;
            }

            // sending error on ioctl failure
            if (errno == EIO || errno == EAGAIN) // TODO: Log?
                return false;
            throw linux_backend_exception(rsutils::string::from() << "xioctl(VIDIOC_G_EXT_CTRLS) failed on control " << static_cast<int>(control) << ", errno=" << errno);
        }

        control_range v4l_mipi_device::get_xu_range(const extension_unit& xu, uint8_t control, int len) const
        {
            v4l2_query_ext_ctrl xctrl_query{};
            xctrl_query.id = v4l_mipi_logic::xu_to_cid(xu,control,is_d5xx_product_line(_info.pid));

            if(0 > ioctl(_fd,VIDIOC_QUERY_EXT_CTRL,&xctrl_query)){
                throw linux_backend_exception(rsutils::string::from() << "xioctl(VIDIOC_QUERY_EXT_CTRL) failed, errno=" << errno);
            }

            if ((xctrl_query.elems !=1 ) ||
                (xctrl_query.minimum < std::numeric_limits<int32_t>::min()) ||
                (xctrl_query.maximum > std::numeric_limits<int32_t>::max()))
                throw linux_backend_exception(rsutils::string::from() << "Mipi Control range for " << xctrl_query.name
                    << " is not compliant with backend interface: [min,max,default,step]:\n"
                    << xctrl_query.minimum << ", " << xctrl_query.maximum << ", "
                    << xctrl_query.default_value << ", " << xctrl_query.step
                    << "\n Elements = " << xctrl_query.elems);

            if (v4l_mipi_logic::is_auto_exposure_control(control))
                return {0, 1, 1, 1};
            return { static_cast<int32_t>(xctrl_query.minimum), static_cast<int32_t>(xctrl_query.maximum),
                     static_cast<int32_t>(xctrl_query.step), static_cast<int32_t>(xctrl_query.default_value)};
        }

        control_range v4l_mipi_device::get_pu_range(rs2_option option) const
        {
            // Auto controls range is trimed to {0,1} range
            if(option >= RS2_OPTION_ENABLE_AUTO_EXPOSURE && option <= RS2_OPTION_ENABLE_AUTO_WHITE_BALANCE)
            {
                static const int32_t min = 0, max = 1, step = 1, def = 1;
                control_range range(min, max, step, def);

                return range;
            }

            struct v4l2_query_ext_ctrl query = {};
            query.id = v4l_mipi_logic::option_to_cid(option);
            if (xioctl(_fd, VIDIOC_QUERY_EXT_CTRL, &query) < 0)
            {
                // Some controls (exposure, auto exposure, auto hue) do not seem to work on V4L2
                // Instead of throwing an error, return an empty range. This will cause this control to be omitted on our UI sample.
                // TODO: Figure out what can be done about these options and make this work
                query.minimum = query.maximum = 0;
            }

            control_range range(query.minimum, query.maximum, query.step, query.default_value);

            return range;
        }

        std::shared_ptr<uvc_device> v4l_backend::create_uvc_device(uvc_device_info info) const
        {
            bool mipi_device = info.is_mipi;

            auto v4l_uvc_dev =        mipi_device ?         std::make_shared<v4l_mipi_device>(info) :
                              ((!info.has_metadata_node) ?  std::make_shared<v4l_uvc_device>(info) :
                                                            std::make_shared<v4l_uvc_meta_device>(info));

            return std::make_shared<platform::retry_controls_work_around>(v4l_uvc_dev);
        }

        std::vector<uvc_device_info> v4l_backend::query_uvc_devices() const
        {
            std::vector<uvc_device_info> uvc_nodes;

            v4l_enum::foreach_uvc_device(
            [&uvc_nodes](const uvc_device_info& i, const std::string&)
            {
                uvc_nodes.push_back(i);
            });

            return uvc_nodes;
        }

        std::shared_ptr<command_transfer> v4l_backend::create_usb_device(usb_device_info info) const
        {
            auto dev = usb_enumerator::create_usb_device(info);
             if(dev)
                 return std::make_shared<platform::command_transfer_usb>(dev);
             return nullptr;
        }

        std::vector<usb_device_info> v4l_backend::query_usb_devices() const
        {
            auto device_infos = usb_enumerator::query_devices_info();
            return device_infos;
        }

        std::vector<mipi_device_info> v4l_backend::query_mipi_devices() const
        {
            std::vector<mipi_device_info> mipi_nodes;

            v4l_enum::foreach_mipi_device(
            [&mipi_nodes](const mipi_device_info& i, const std::string&)
            {
                mipi_nodes.push_back(i);
            });

            return mipi_nodes;
        }
        std::shared_ptr<hid_device> v4l_backend::create_hid_device(hid_device_info info) const
        {
            return std::make_shared<v4l_hid_device>(info);
        }

        std::vector<hid_device_info> v4l_backend::query_hid_devices() const
        {
            std::vector<hid_device_info> results;
            v4l_hid_device::foreach_hid_device([&](const hid_device_info& hid_dev_info){
                results.push_back(hid_dev_info);
            });
            return results;
        }

        std::shared_ptr<device_watcher> v4l_backend::create_device_watcher() const
        {
#if defined(USING_UDEV)
            return std::make_shared< udev_device_watcher >( this );
#else
            return std::make_shared< polling_device_watcher >( this );
#endif
        }

        std::shared_ptr<backend> create_backend()
        {
            return std::make_shared<v4l_backend>();
        }
    }
}
