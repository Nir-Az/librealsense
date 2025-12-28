## License: Apache 2.0. See LICENSE file in root directory.
## Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

#####################################################
##                   auto calibration              ##
#####################################################

import argparse
import json
import sys
import time

import pyrealsense2 as rs


ctx = rs.context()


def main(arguments=None):
    #args = parse_arguments(arguments)
    try:
        device = ctx.query_devices()[0]
    except IndexError:
        print('Device is not connected')
        sys.exit(1)
    if device.supports(rs.camera_info.connection_type):
        if device.get_info(rs.camera_info.connection_type) != "DDS":
            print('Device is not connected with DDS')
            sys.exit(1)
    depth_sensor = device.first_depth_sensor()
    embedded_filters = depth_sensor.query_embedded_filters()
    for filter in embedded_filters:


'''
def parse_arguments(args):
    parser = argparse.ArgumentParser(description=__desc__)
    #parser.add_argument('--exposure', default='auto', help="Exposure value or 'auto' to use auto exposure")
    return parser.parse_args(args)
'''


if __name__ == '__main__':
    main()
