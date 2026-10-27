cmake_minimum_required(VERSION 3.16)
project(research_cosmetic_conflict_prototype LANGUAGES CXX)

# Standalone research diagnostic for conflict-preserving cosmetic override
# leases. No dependencies, no downloads, no network, no game/plugin build.
#
#   cmake -S . -B build-research-cosmetic
#   cmake --build build-research-cosmetic --config Release
#   ./build-research-cosmetic/research_cosmetic_conflict_prototype
#
# plugin/include/CosmeticOverrideState.h is included read-only and is never
# modified by this project. The prototype is not a production fix.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(research_cosmetic_conflict_prototype
    tools/research_cosmetic_conflict_prototype.cpp)

target_include_directories(research_cosmetic_conflict_prototype PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${CMAKE_CURRENT_SOURCE_DIR}/plugin/include)
