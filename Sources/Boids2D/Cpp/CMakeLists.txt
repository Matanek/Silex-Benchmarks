cmake_minimum_required(VERSION 3.28)

project(BoidsCpp LANGUAGES CXX)

include(FetchContent)

find_package(SDL3 CONFIG REQUIRED)

find_package(EnTT 4 CONFIG QUIET)
if(NOT EnTT_FOUND)
    FetchContent_Declare(
        EnTT
        GIT_REPOSITORY https://github.com/skypjack/entt.git
        GIT_TAG 85c6bba014049b5de8fad49d25424df2f1f6a8c1
    )
    FetchContent_MakeAvailable(EnTT)
endif()

find_program(SHADERCROSS_EXECUTABLE shadercross REQUIRED)

set(SHADER_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/../../../../Packages/GFX.Scene2D/Shaders/Drawing.hlsl")
set(SHADER_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/Shaders")

if(APPLE)
    set(SHADER_DESTINATION MSL)
    set(SHADER_EXTENSION msl)
    set(SHADER_FORMAT_DEFINE BOIDS_SHADER_FORMAT_MSL)
elseif(WIN32)
    set(SHADER_DESTINATION DXIL)
    set(SHADER_EXTENSION dxil)
    set(SHADER_FORMAT_DEFINE BOIDS_SHADER_FORMAT_DXIL)
else()
    set(SHADER_DESTINATION SPIRV)
    set(SHADER_EXTENSION spv)
    set(SHADER_FORMAT_DEFINE BOIDS_SHADER_FORMAT_SPIRV)
endif()

set(VERTEX_SHADER "${SHADER_DIRECTORY}/Drawing.vertex.${SHADER_EXTENSION}")
set(FRAGMENT_SHADER "${SHADER_DIRECTORY}/Drawing.fragment.${SHADER_EXTENSION}")

add_custom_command(
    OUTPUT "${VERTEX_SHADER}"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${SHADER_DIRECTORY}"
    COMMAND
        "${SHADERCROSS_EXECUTABLE}" "${SHADER_SOURCE}"
        --source HLSL
        --dest "${SHADER_DESTINATION}"
        --stage vertex
        --entrypoint vertex_main
        --output "${VERTEX_SHADER}"
    DEPENDS "${SHADER_SOURCE}"
    VERBATIM
)

add_custom_command(
    OUTPUT "${FRAGMENT_SHADER}"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${SHADER_DIRECTORY}"
    COMMAND
        "${SHADERCROSS_EXECUTABLE}" "${SHADER_SOURCE}"
        --source HLSL
        --dest "${SHADER_DESTINATION}"
        --stage fragment
        --entrypoint fragment_main
        --output "${FRAGMENT_SHADER}"
    DEPENDS "${SHADER_SOURCE}"
    VERBATIM
)

add_custom_target(
    BoidsCppShaders
    DEPENDS "${VERTEX_SHADER}" "${FRAGMENT_SHADER}"
)

add_executable(BoidsCppDirect Sources/Direct.cpp)
target_compile_features(BoidsCppDirect PRIVATE cxx_std_23)
target_link_libraries(BoidsCppDirect PRIVATE SDL3::SDL3)

add_executable(BoidsCppArchitectural Sources/Architectural.cpp)
add_dependencies(BoidsCppArchitectural BoidsCppShaders)
target_compile_features(BoidsCppArchitectural PRIVATE cxx_std_23)
target_compile_definitions(
    BoidsCppArchitectural
    PRIVATE
        ${SHADER_FORMAT_DEFINE}
        BOIDS_VERTEX_SHADER_PATH="${VERTEX_SHADER}"
        BOIDS_FRAGMENT_SHADER_PATH="${FRAGMENT_SHADER}"
)
target_link_libraries(BoidsCppArchitectural PRIVATE EnTT::EnTT SDL3::SDL3)
