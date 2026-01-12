info("Building with CUDA requires CMake v3.8+")
cmake_minimum_required(VERSION 3.10)
enable_language( CUDA )

find_package(CUDA REQUIRED)

include_directories(${CUDA_INCLUDE_DIRS})
SET(ALL_CUDA_LIBS ${CUDA_LIBRARIES} ${CUDA_cusparse_LIBRARY} ${CUDA_cublas_LIBRARY})
SET(LIBS ${LIBS} ${ALL_CUDA_LIBS})

message(STATUS "CUDA_LIBRARIES: ${CUDA_INCLUDE_DIRS} ${ALL_CUDA_LIBS}")

set(CUDA_PROPAGATE_HOST_FLAGS OFF)
set(CUDA_SEPARABLE_COMPILATION ON)

# Check if variable is available (means CMake >= 3.18)
if(POLICY CMP0104)
    # Use modern approach
    cmake_policy(SET CMP0104 NEW)
    # Set your target architectures below. Example: Turing and Ampere
    set(CMAKE_CUDA_ARCHITECTURES 62 75 80 110 120)
else()
    # Fallback for older CMake: set the classical NVCC flags
    set(CUDA_NVCC_FLAGS "${CUDA_NVCC_FLAGS} -gencode arch=compute_62,code=sm_62 -gencode arch=compute_75,code=sm_75 -gencode arch=compute_80,code=sm_80 -gencode arch=compute_110,code=sm_110 -gencode arch=compute_120,code=sm_120")
endif()


