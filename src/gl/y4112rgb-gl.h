// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2021 Intel Corporation. All Rights Reserved.

#pragma once

#include <map>
#include <vector>

#include "../proc/synthetic-stream.h"
#include "synthetic-stream-gl.h"

#include <librealsense2/rs.hpp>
#include "opengl3.h"  // in common/!

#include <memory>


namespace librealsense {
namespace gl {
    
    
class y411_2rgb : public stream_filter_processing_block, public gpu_processing_object
{
public:
    y411_2rgb();
    ~y411_2rgb() override;

    void cleanup_gpu_resources() override;
    void create_gpu_resources() override;

    rs2::frame process_frame(const rs2::frame_source& source, const rs2::frame& f) override;
private:
    int _enabled = 0;
    rs2::stream_profile _input_profile;
    rs2::stream_profile _output_profile;

    int _width, _height;

    std::shared_ptr<rs2::visualizer_2d> _viz;
    std::shared_ptr<rs2::fbo> _fbo;
};
    
    
}  // namespace gl
}  // namespace librealsense
