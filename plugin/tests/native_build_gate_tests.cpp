#include "NativeBuildGate.h"

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

static bool contains(const mct::NativeGateDecision& decision, const char* reason) {
    for (const auto& item : decision.blockingReasons)
        if (item == reason) return true;
    return false;
}

static void requireClosed(const mct::NativeGateDecision& decision, const char* reason) {
    require(!decision.mutationsAllowed, "Mutation was authorized");
    require(!decision.verifiedCompatible, "Detection was treated as compatibility");
    require(!decision.pluginApiTouch, "Policy authorized a plugin API touch");
    require(!decision.launcherWrite, "Policy authorized a launcher write");
    require(decision.schemaVersion == 1, "Schema changed");
    require(contains(decision, "mutation_not_verified"), "Mutation refusal was omitted");
    require(!mct::NativeBuildGate::mutationSupported, "Mutation support was enabled");
    if (reason) {
        require(!decision.readOnlyDiagnosticEligible, "Read-only trial opened incorrectly");
        require(decision.trial.empty(), "Ineligible trial was named");
        require(decision.reason == reason, reason);
    }
}

static mct::NativeBuildObservation ready() {
    mct::NativeBuildObservation observation;
    observation.executableSha256 = mct::NativeBuildGate::diagnosticExecutableSha256;
    observation.fileVersion = mct::NativeBuildGate::diagnosticFileVersion;
    observation.steamBuildId = mct::NativeBuildGate::diagnosticSteamBuildId;
    observation.bakkesmodCoreVersion = mct::NativeBuildGate::diagnosticBakkesmodCoreVersion;
    observation.owned = true;
    observation.offline = true;
    observation.fresh = true;
    observation.online = false;
    return observation;
}

int main() {
    try {
        const auto opened = mct::NativeBuildGate::evaluate(ready());
        requireClosed(opened, nullptr);
        require(opened.readOnlyDiagnosticEligible, "Diagnostic target was not read-only eligible");
        require(opened.trial == "opt_in_read_only", "Trial was described as compatibility");
        require(opened.reason == "read_only_trial_only", "Read-only reason missing");
        require(opened.blockingReasons.size() == 1, "Read-only trial gained another grant");

        auto granted = ready();
        granted.callerAuthorization = true;
        const auto refusedGrant = mct::NativeBuildGate::evaluate(
            granted, {mct::NativeBuildGate::diagnosticExecutableSha256});
        requireClosed(refusedGrant, nullptr);
        require(refusedGrant.readOnlyDiagnosticEligible, "Caller catalog withdrew the read-only trial");
        require(!refusedGrant.mutationsAllowed && !refusedGrant.verifiedCompatible,
                "Caller catalog authorized mutation or compatibility");
        require(contains(refusedGrant, "caller_authorization_refused"), "Allowlist tampering was accepted");

        auto mismatched = ready();
        mismatched.executableSha256 = std::string(64, 'a');
        const auto tampered = mct::NativeBuildGate::evaluate(
            mismatched, {std::string(mct::NativeBuildGate::diagnosticExecutableSha256)});
        requireClosed(tampered, "executable_hash_mismatch");
        require(contains(tampered, "caller_authorization_refused"), "Tampered allowlist was used as policy");

        auto missing = ready();
        missing.executableSha256.clear();
        requireClosed(mct::NativeBuildGate::evaluate(missing), "missing_executable_hash");

        auto online = ready();
        online.online = true;
        online.offline = false;
        const auto normalOnline = mct::NativeBuildGate::evaluate(online);
        requireClosed(normalOnline, "online_session");
        require(contains(normalOnline, "not_offline"), "Normal online launch looked offline");

        auto stale = ready();
        stale.fresh = false;
        requireClosed(mct::NativeBuildGate::evaluate(stale), "stale_session");

        auto unowned = ready();
        unowned.owned = false;
        requireClosed(mct::NativeBuildGate::evaluate(unowned), "unowned_session");

        auto swapped = ready();
        swapped.fileVersion = "229";
        swapped.bakkesmodCoreVersion = mct::NativeBuildGate::diagnosticFileVersion;
        const auto notEquivalent = mct::NativeBuildGate::evaluate(swapped);
        requireClosed(notEquivalent, "invalid_file_version");
        require(contains(notEquivalent, "invalid_bakkesmod_core_version"),
                "File version was accepted as the BakkesMod core version");

        auto steamCore = ready();
        steamCore.steamBuildId = "229";
        requireClosed(mct::NativeBuildGate::evaluate(steamCore), "invalid_steam_build_id");

        auto uppercase = ready();
        for (char& character : uppercase.executableSha256)
            if (character >= 'a' && character <= 'f') character = static_cast<char>(character - 32);
        requireClosed(mct::NativeBuildGate::evaluate(uppercase), "invalid_executable_hash");

        auto path = ready();
        path.executableSha256 = "a/b";
        requireClosed(mct::NativeBuildGate::evaluate(path), "invalid_executable_hash");

        requireClosed(mct::NativeBuildGate::evaluate({}), "missing_executable_hash");

        std::cout << "Native build gate refuses mutation and limits the read-only trial.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
