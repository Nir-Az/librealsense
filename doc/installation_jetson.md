# NVIDIA® Jetson™ Devices

**NOTE**: See [support-matrix.md](./support-matrix.md) to learn more about Jetson support for RealSense devices.

> Check out [www.jetsonhacks.com](http://www.jetsonhacks.com/) for great content on everything Jetson! (not affiliated with RealSense)

## Getting started

### 1. Prerequisites

* NVIDIA® **Jetson Nano™**, **Jetson AGX Xavier™**, **Jetson AGX Orin™**, or **Jetson Orin Nano™** board
* A supported RealSense Camera device (USB or MIPI/GMSL)

## RealSense Device Support on Jetson

RealSense supports two types of camera connections on Jetson platforms:

### USB Devices (D455, D435i, etc.)
- Connect via standard USB 3.0/3.1 ports
- Examples: D455, D435i, D415
- Might Require kernel patches for optimal performance - 
### MIPI/GMSL Devices (D457)
- Connect via MIPI CSI interface using a GMSL to MIPI Deserializer
- Examples: D457
- Require additional MIPI driver installation
- **Hardware requirement**: GMSL to MIPI Deserializer board (sold separately)

### 2. Establish Developer's Environment

Follow [official instructions](https://developer.nvidia.com/embedded/learn/getting-started-jetson) to get your board ready. This guide supports **NVIDIA® L4T Ubuntu 20.04/22.04** with JetPack versions 5.0.2 and later.

For **Jetson Nano™** we strongly recommend enabling the Barrel Jack connector for extra power (See [jetsonhacks.com/jetson-nano-use-more-power/](https://www.jetsonhacks.com/2019/04/10/jetson-nano-use-more-power/) to learn how)

![Jetson with RealSense](./img/jetson-orin-realsense.jpg)

---

## Installation Options

Choose the installation method based on your device type and requirements:

### Option 1: USB Devices Only (D455, D435i, etc.)

**For USB devices like D455, D435i, D415**, you might need to apply kernel patches for optimal performance, depend on the kernel version.

#### Prerequisites
- Verify board type and JetPack version compatibility
- Ensure internet connection and ~2.5GB free space
- Configure Jetson into Max power mode
- Disconnect any attached USB/UVC cameras

#### Installation Steps

1. **Apply Kernel Patches**:
   ```sh
   cd /path/to/librealsense
   ./scripts/patch-realsense-ubuntu-L4T.sh
   ```
   
   This script will:
   - Fetch required kernel source trees (~30 minutes)
   - Apply RealSense-specific kernel patches
   - Build and install modified kernel modules

2. **Build LibRealSense SDK**:
   ```sh
   sudo apt-get install git libssl-dev libusb-1.0-0-dev libudev-dev pkg-config libgtk-3-dev -y
   ./scripts/setup_udev_rules.sh
   mkdir build && cd build
   cmake .. -DBUILD_EXAMPLES=true -DFORCE_RSUSB_BACKEND=false -DBUILD_WITH_CUDA=true
   make -j$(($(nproc)-1))
   sudo make install
   ```

3. **Test the installation**:
   ```sh
   realsense-viewer
   ```

### Option 2: MIPI/GMSL Devices (D457) + USB Devices

**For MIPI/GMSL devices like D457**, you need both USB support and the RealSense MIPI driver.

#### Prerequisites
- GMSL to MIPI Deserializer board (hardware sold separately)
- Completed USB device setup from Option 1

#### Installation Steps

1. **Complete USB device setup first** using Option 1 above

2. **Install RealSense MIPI Platform Driver**:
   
   Follow the comprehensive installation guide at:
   [RealSense MIPI Platform Driver](https://github.com/IntelRealSense/realsense_mipi_platform_driver/blob/master/README.md)

3. **Hardware Setup**:
   - Connect your D457 to the GMSL to MIPI Deserializer
   - Connect the deserializer to your Jetson's MIPI CSI port
   - Ensure proper power connections

4. **Verify Installation**:
   ```sh
   realsense-viewer
   ```
   
   You should see both USB and MIPI devices if connected.

#### Hardware Requirements for MIPI/GMSL

- **GMSL to MIPI Deserializer**: Required hardware component (sold separately)
- **Compatible Jetson boards**: AGX Xavier, AGX Orin (recommended)
- **D457 camera**: GMSL-compatible RealSense device

### Alternative: Debian Packages (USB devices only, limited functionality)

**For quick setup with basic USB device support** (without full kernel optimizations)

 The minimum JetPack SDK required to run the precompiled Debians is [JetPack version 5.0.2](https://developer.nvidia.com/jetpack-sdk-441-archive) ( L4T 35.1 , CUDA version 11.4).

<u>Installation steps:</u>

1. Register the server's public key:

    ```sh
    sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE || sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE
    ```

2. Add the server to the list of repositories:

    ```sh
    sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" -u
    ```

3. Install the SDK:

    ```sh
    sudo apt-get install librealsense2-utils librealsense2-dev
    ```

4. Test the installation:

    ```sh
    realsense-viewer
    ```

**Limitations**: This method provides basic USB device support but may not include all optimizations available through kernel patching.

### Alternative: RSUSB Backend (No Kernel Patching)

**For quick prototyping or when kernel patching is not feasible**

This method uses a user-space USB implementation without kernel modifications:

```sh
cd /path/to/librealsense
./scripts/libuvc_installation.sh
```

**Limitations**: 
- Reduced performance compared to native kernel drivers
- Limited multi-camera support
- Some advanced features may not be available

---

## Troubleshooting

### USB Device Issues
- Ensure sufficient power supply (especially for Jetson Nano)
- Verify USB 3.0 connection
- Check that kernel patches were applied successfully

### MIPI Device Issues
- Verify GMSL to MIPI Deserializer connections
- Check MIPI driver installation
- Ensure D457 is properly powered

### General Issues
- Verify JetPack version compatibility
- Check available disk space before building
- Ensure internet connectivity during installation

For additional support, visit the [RealSense GitHub Issues](https://github.com/IntelRealSense/librealsense/issues) page.

![Jetson Orin with RealSense Camera](./img/jetson-orin-d400.png)
