cmake_minimum_required(VERSION 3.24)
project(MctNativeLauncher LANGUAGES CXX)

# This helper ships in its own runtime directory. Link its C/C++ runtime so a
# player does not need the developer toolchain or adjacent MSVC runtime DLLs.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "MctNativeLauncher is a 64-bit Windows MSVC program.")
endif()

get_filename_component(MCT_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(MCT_DETOURS_ARCHIVE "${MCT_REPO_ROOT}/../tools/detours-v4.0.1.tar.gz")
set(MCT_JSON_SOURCE "${MCT_REPO_ROOT}/build/plugin/_deps/mct_json-src")
if(NOT MCT_DETOURS_SOURCE_ARCHIVE AND EXISTS "${MCT_DETOURS_ARCHIVE}")
  set(MCT_DETOURS_SOURCE_ARCHIVE "${MCT_DETOURS_ARCHIVE}" CACHE FILEPATH
    "Optional local archive for the pinned Detours sources.")
endif()
if(NOT FETCHCONTENT_SOURCE_DIR_MCT_JSON AND EXISTS "${MCT_JSON_SOURCE}/include/nlohmann/json.hpp")
  # Reuse the tree fetched and hash-checked by the plugin build. A fresh clone
  # instead downloads the same immutable archive below.
  set(FETCHCONTENT_SOURCE_DIR_MCT_JSON "${MCT_JSON_SOURCE}" CACHE PATH
    "Optional existing nlohmann_json 3.12 source tree from the plugin build.")
endif()
set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
set(JSON_Install OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(mct_json
  URL https://codeload.github.com/nlohmann/json/tar.gz/refs/tags/v3.12.0
  URL_HASH SHA256=4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(mct_json)

add_subdirectory("${MCT_REPO_ROOT}/native_file_view" "${CMAKE_BINARY_DIR}/native_file_view")

set(MCT_LAUNCH_SOURCES
  src/LaunchText.cpp
  src/LaunchFiles.cpp
  src/LaunchCommit.cpp
  src/WinFileHold.cpp)
set(MCT_LAUNCH_FLAGS /W4 /EHsc /utf-8 /permissive- /FS)
set(MCT_LAUNCH_DEFS UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX _WIN32_WINNT=0x0A00)

set(MCT_DLL_PIN_HEADER "${CMAKE_CURRENT_BINARY_DIR}/generated/MctFileViewDllPin.h")
add_custom_command(
  OUTPUT "${MCT_DLL_PIN_HEADER}"
  COMMAND ${CMAKE_COMMAND}
          -DINPUT=$<TARGET_FILE:MctNativeFileView64>
          -DOUTPUT=${MCT_DLL_PIN_HEADER}
          -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/pin_dll_sha.cmake
  DEPENDS MctNativeFileView64
  VERBATIM)
set_source_files_properties("${MCT_DLL_PIN_HEADER}" PROPERTIES GENERATED TRUE)

add_executable(MctNativeLauncher ${MCT_LAUNCH_SOURCES} src/WinLaunch.cpp src/launcher_main.cpp "${MCT_DLL_PIN_HEADER}")
target_include_directories(MctNativeLauncher PRIVATE
  include
  "${MCT_REPO_ROOT}/native_file_view/include"
  "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_link_libraries(MctNativeLauncher PRIVATE nlohmann_json::nlohmann_json mct_detours bcrypt psapi)
target_compile_options(MctNativeLauncher PRIVATE ${MCT_LAUNCH_FLAGS})
target_compile_definitions(MctNativeLauncher PRIVATE ${MCT_LAUNCH_DEFS})
target_compile_features(MctNativeLauncher PRIVATE cxx_std_17)
target_link_options(MctNativeLauncher PRIVATE "/SUBSYSTEM:WINDOWS" "/ENTRY:wmainCRTStartup")

add_executable(mct_native_launcher_tests ${MCT_LAUNCH_SOURCES} tests/launcher_tests.cpp "${MCT_DLL_PIN_HEADER}")
target_include_directories(mct_native_launcher_tests PRIVATE
  include
  "${MCT_REPO_ROOT}/native_file_view/include"
  "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_link_libraries(mct_native_launcher_tests PRIVATE nlohmann_json::nlohmann_json bcrypt)
target_compile_options(mct_native_launcher_tests PRIVATE ${MCT_LAUNCH_FLAGS})
target_compile_definitions(mct_native_launcher_tests PRIVATE ${MCT_LAUNCH_DEFS})
target_compile_features(mct_native_launcher_tests PRIVATE cxx_std_17)
add_dependencies(mct_native_launcher_tests MctNativeLauncher)

set(MCT_LAUNCH_OUTPUT "${CMAKE_BINARY_DIR}/bin")
foreach(target IN ITEMS MctNativeLauncher mct_native_launcher_tests)
  set_target_properties(${target} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${MCT_LAUNCH_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${MCT_LAUNCH_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${MCT_LAUNCH_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${MCT_LAUNCH_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${MCT_LAUNCH_OUTPUT}")
endforeach()

add_custom_command(TARGET MctNativeLauncher POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "${CMAKE_CURRENT_SOURCE_DIR}/NOTICE"
          "$<TARGET_FILE_DIR:MctNativeLauncher>/NOTICE"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "${CMAKE_CURRENT_SOURCE_DIR}/DETOURS-MIT-LICENSE.txt"
          "$<TARGET_FILE_DIR:MctNativeLauncher>/DETOURS-MIT-LICENSE.txt"
  VERBATIM)

include(CTest)
if(BUILD_TESTING)
  add_test(NAME native_launcher_pure COMMAND mct_native_launcher_tests)
endif()
