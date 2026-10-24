#pragma once

#include "LaunchCommit.h"
#include "WinFileHold.h"

MctLaunchHooks MctProductionHooks(MctHoldSet& holds);

bool MctWaitOwnedExit(const MctOwnedLaunch& owned, DWORD* exitCode, std::wstring* error);

void MctReleaseOwned(MctOwnedLaunch* owned);
