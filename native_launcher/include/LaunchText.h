#pragma once

#include "LaunchProtocol.h"

#include <string>

bool MctInvocationIsLaunch(int argc, wchar_t** argv);

const char* MctUsageText();

bool MctParseLaunchPlan(const std::string& bytes, MctLaunchPlan* plan, std::wstring* error);

bool MctBuildOfflineCommandLine(const std::wstring& exePath, std::wstring* command, std::wstring* error);

bool MctBuildChildEnvironment(const std::wstring& parent, const std::wstring& session, std::wstring* block,
                              std::wstring* error);

bool MctEnvironmentHasExactEntry(const std::wstring& block, const wchar_t* key, const std::wstring& value);

std::string MctWideToUtf8(const std::wstring& text);

std::string MctErrorReceiptJson(const std::wstring& error);

std::string MctLaunchReceiptJson(const MctResolvedLaunch& resolved, const MctOwnedLaunch& owned);

std::string MctExitReceiptJson(const MctResolvedLaunch& resolved, const MctOwnedLaunch& owned, DWORD exitCode);
