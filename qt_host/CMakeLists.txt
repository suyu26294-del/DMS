cmake_minimum_required(VERSION 3.20)
project(dms_qt_host LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Network)

add_executable(dms_qt_host main.cpp)
target_link_libraries(dms_qt_host PRIVATE Qt6::Widgets Qt6::Network)
