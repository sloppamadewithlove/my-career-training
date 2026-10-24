cmake_minimum_required(VERSION 3.24)
project(MctNativeFileView LANGUAGES CXX)

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "native_file_view is a 64-bit Windows MSVC fixture.")
endif()

set(MCT_DETOURS_URL "https://codeload.github.com/microsoft/Detours/tar.gz/e4bfd6b03e50de46b47abfbd1e46b384f0c5f833")
set(MCT_DETOURS_HASH "SHA256=d24f5dd1f977c33301ebd9f3be064e938a7908954df15b31235c9ca6691cb356")
set(MCT_DETOURS_SOURCE_ARCHIVE "" CACHE FILEPATH
  "Offline override for the pinned Detours v4.0.1 source archive. The archive hash must match the pin.")

include(FetchContent)
if(MCT_DETOURS_SOURCE_ARCHIVE)
  FetchContent_Declare(mct_detours
    URL "${MCT_DETOURS_SOURCE_ARCHIVE}"
    URL_HASH "${MCT_DETOURS_HASH}"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
else()
  FetchContent_Declare(mct_detours
    URL "${MCT_DETOURS_URL}"
    URL_HASH "${MCT_DETOURS_HASH}"
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
endif()
FetchContent_MakeAvailable(mct_detours)

set(MCT_DETOURS_SRC "")
if(EXISTS "${mct_detours_SOURCE_DIR}/src/detours.h")
  set(MCT_DETOURS_SRC "${mct_detours_SOURCE_DIR}/src")
else()
  file(GLOB MCT_DETOURS_CHILDREN LIST_DIRECTORIES true "${mct_detours_SOURCE_DIR}/*")
  foreach(child IN LISTS MCT_DETOURS_CHILDREN)
    if(EXISTS "${child}/src/detours.h")
      set(MCT_DETOURS_SRC "${child}/src")
    endif()
  endforeach()
endif()
if(NOT MCT_DETOURS_SRC)
  message(FATAL_ERROR "Pinned Detours sources do not contain src/detours.h")
endif()

# Detours' own makefile compiles these translation units. uimports.cpp is included
# by creatwth.cpp. disasm.cpp selects the x64 decoder when this target is x64.
# The library stays static and is not an installed runtime.
add_library(mct_detours STATIC
  "${MCT_DETOURS_SRC}/detours.cpp"
  "${MCT_DETOURS_SRC}/modules.cpp"
  "${MCT_DETOURS_SRC}/disasm.cpp"
  "${MCT_DETOURS_SRC}/image.cpp"
  "${MCT_DETOURS_SRC}/creatwth.cpp")
target_include_directories(mct_detours PUBLIC "${MCT_DETOURS_SRC}")
target_compile_definitions(mct_detours PRIVATE WIN32_LEAN_AND_MEAN _WIN32_WINNT=0x0A00 _CRT_SECURE_NO_WARNINGS)
target_compile_options(mct_detours PRIVATE /W3 /EHsc /utf-8)
target_compile_features(mct_detours PUBLIC cxx_std_17)

set(MCT_VIEW_FLAGS /W4 /EHsc /utf-8 /permissive-)

add_library(MctNativeFileView64 SHARED src/file_view_dll.cpp src/MctNativeFileView64.def)
target_include_directories(MctNativeFileView64 PRIVATE include)
target_link_libraries(MctNativeFileView64 PRIVATE mct_detours)
target_compile_options(MctNativeFileView64 PRIVATE ${MCT_VIEW_FLAGS})
target_compile_definitions(MctNativeFileView64 PRIVATE UNICODE _UNICODE)
set_target_properties(MctNativeFileView64 PROPERTIES PREFIX "" OUTPUT_NAME "MctNativeFileView64")

add_executable(MctNativeFileFixture src/fixture.cpp)
target_compile_options(MctNativeFileFixture PRIVATE ${MCT_VIEW_FLAGS})
target_compile_definitions(MctNativeFileFixture PRIVATE UNICODE _UNICODE)
target_compile_features(MctNativeFileFixture PRIVATE cxx_std_17)

add_executable(mct_native_file_view_tests tests/file_view_tests.cpp src/fixture_launch.cpp)
target_include_directories(mct_native_file_view_tests PRIVATE include)
target_link_libraries(mct_native_file_view_tests PRIVATE mct_detours bcrypt)
target_compile_options(mct_native_file_view_tests PRIVATE ${MCT_VIEW_FLAGS})
target_compile_definitions(mct_native_file_view_tests PRIVATE UNICODE _UNICODE)
target_compile_features(mct_native_file_view_tests PRIVATE cxx_std_17)

set(MCT_FILE_VIEW_OUTPUT "${CMAKE_BINARY_DIR}/bin")
foreach(target IN ITEMS MctNativeFileFixture MctNativeFileView64 mct_native_file_view_tests)
  set_target_properties(${target} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${MCT_FILE_VIEW_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_DEBUG "${MCT_FILE_VIEW_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${MCT_FILE_VIEW_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO "${MCT_FILE_VIEW_OUTPUT}"
    RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL "${MCT_FILE_VIEW_OUTPUT}")
endforeach()

include(CTest)
if(BUILD_TESTING)
  foreach(scenario IN ITEMS plain redirect missing-payload invalid-payload private-missing alias dll-path timeout path-bounds payload-revalidate ambient-handles)
    add_test(NAME "native_file_view_${scenario}" COMMAND mct_native_file_view_tests "${scenario}")
  endforeach()
endif()
