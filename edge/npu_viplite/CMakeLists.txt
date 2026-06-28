cmake_minimum_required(VERSION 3.10)

project(edge_qa_viplite)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED AI_SDK_ROOT)
  if(DEFINED ENV{TIMELAPSE_AI_SDK_ROOT})
    set(AI_SDK_ROOT "$ENV{TIMELAPSE_AI_SDK_ROOT}")
  else()
    set(AI_SDK_ROOT "/opt/timelapse/ai-sdk")
  endif()
endif()

set(AI_SDK_EXAMPLES "${AI_SDK_ROOT}/examples")

find_package(OpenCV REQUIRED)
find_package(JPEG REQUIRED)

include_directories(
  "${AI_SDK_EXAMPLES}/libawnn_viplite"
  "${AI_SDK_EXAMPLES}/libawutils"
  ${JPEG_INCLUDE_DIR}
)

add_executable(edge_qa_viplite
  edge_qa_viplite.cpp
  "${AI_SDK_EXAMPLES}/libawnn_viplite/awnn_lib.c"
  "${AI_SDK_EXAMPLES}/libawnn_viplite/awnn_quantize.c"
)

target_link_libraries(edge_qa_viplite
  ${OpenCV_LIBS}
  NBGlinker
  VIPhal
  ${JPEG_LIBRARIES}
  m
  dl
)
