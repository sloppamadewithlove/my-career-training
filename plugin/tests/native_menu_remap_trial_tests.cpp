#include "NativeMenuRemapTrial.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

int failures = 0;

void expect(bool ok, const char* label) {
    if (ok) return;
    std::fprintf(stderr, "FAIL %s\n", label);
    ++failures;
}

bool same(const char* got, const char* want) {
    return got != nullptr && want != nullptr && std::strcmp(got, want) == 0;
}

void encode(unsigned char out[8], int index, int number) {
    const auto packedIndex = static_cast<unsigned>(index);
    const auto packedNumber = static_cast<unsigned>(number);
    for (int byte = 0; byte < 4; ++byte) {
        out[byte] = static_cast<unsigned char>((packedIndex >> (8 * byte)) & 0xff);
        out[4 + byte] = static_cast<unsigned char>((packedNumber >> (8 * byte)) & 0xff);
    }
}

bool bytesAre(const unsigned char* got, int index, int number) {
    unsigned char want[8] = {};
    encode(want, index, number);
    return std::memcmp(got, want, 8) == 0;
}

void mustRefuse(const mct::RemapProposal& proposal, const char* why) {
    expect(proposal.refused && !proposal.offerReplace && !proposal.offerRestore && same(proposal.reason, why),
           why);
}

mct::RemapScope scope(const char* session = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee") {
    mct::RemapScope out;
    out.owned = true;
    out.offline = true;
    out.fresh = true;
    out.online = false;
    out.session = session;
    out.threadToken = "12";
    return out;
}

mct::RemapName fn(int index, int number = 0) {
    mct::RemapName name;
    name.index = index;
    name.number = number;
    return name;
}

bool closed(const mct::RemapStatus& status) {
    return !status.actionConsumptionVerified && !status.menuRewriteVerified && !status.verifiedAbi;
}

bool learn(mct::NativeMenuRemapTrial& trial, const mct::RemapScope& current, double& now, const int* ids) {
    const mct::RemapMenu menus[4] = {mct::RemapMenu::Root, mct::RemapMenu::Garage, mct::RemapMenu::Root,
                                     mct::RemapMenu::Options};
    for (int i = 0; i < 4; ++i) {
        const auto identity = static_cast<std::uint64_t>(0x40 + i);
        const auto pre = trial.observe(current, mct::RemapPhase::Pre, menus[i], fn(ids[i]), identity, now);
        if (pre.refused || pre.offerReplace || pre.offerRestore || !same(pre.reason, "await_post")) return false;
        now += 1.0;
        const auto post = mct::remapPost(trial, current, menus[i], fn(ids[i]), identity, now);
        if (post.refused || post.offerReplace || post.offerRestore ||
            !same(post.reason, i == 3 ? "armed" : "calibrating"))
            return false;
        now += 1.0;
    }
    const auto status = trial.status();
    return status.pairs == 4 && same(status.state, "armed") && closed(status) && !status.parameterRewriteApplied &&
           !status.rewriteAttempted;
}

} // namespace

int main() {
    const int synthetic[] = {11, 22, 33, 44};
    const int observed[] = {94486, 135714, 135715, 135724};

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "start");
        expect(learn(trial, current, now, synthetic), "calibration");
        const auto offer = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11),
                                          0xA5A5A5A5A5A5A5A5ULL, now);
        expect(offer.offerReplace && !offer.offerRestore && !offer.refused, "one-shot offer");
        expect(bytesAre(offer.bytes, 33, 0) && !bytesAre(offer.bytes, 135715, 0), "replacement is learned C");
        unsigned char identityBytes[8] = {};
        const auto identity = 0xA5A5A5A5A5A5A5A5ULL;
        std::memcpy(identityBytes, &identity, 8);
        expect(std::memcmp(offer.bytes, identityBytes, 8) != 0, "opaque identity stays out of the proposal");
        expect(!trial.status().parameterRewriteApplied && closed(trial.status()), "offer is not a write ack");
        trial.acknowledgeWrite(true);
        expect(trial.status().parameterRewriteApplied && trial.status().rewriteAttempted && closed(trial.status()),
               "write ack");
        now += 1.0;
        const auto post = mct::remapPost(trial, current, mct::RemapMenu::Root, fn(33), identity, now);
        expect(post.offerRestore && !post.offerReplace && post.originalBytesAvailable && bytesAre(post.bytes, 11, 0),
               "restore offer");
        trial.acknowledgeRestore(true);
        expect(trial.status().restoreAcknowledged && !trial.status().restoreAborted && closed(trial.status()),
               "restore ack");
        now += 1.0;
        const auto sixth = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 99, now);
        mustRefuse(sixth, "one_shot_spent");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        expect(trial.start(current, 0.0), "missing start");
        const auto pre = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, 1.0);
        expect(!pre.refused && !pre.offerReplace, "open pair");
        mustRefuse(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, 2.0), "nested_pre");
        mustRefuse(trial.observe(current, mct::RemapPhase::Post, mct::RemapMenu::Root, fn(11), 1, 3.0), "nested_pre");
        expect(trial.status().pairs == 0 && !trial.status().restoreAborted, "missing post stops calibration");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        expect(trial.start(current, 0.0), "mismatch start");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 5, 1.0).refused,
               "mismatch pre");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Root, fn(99), 5, 2.0), "name_mismatch");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 5, 3.0), "name_mismatch");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        expect(trial.start(current, 0.0), "param start");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 5, 1.0).refused,
               "param pre");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 6, 2.0), "param_mismatch");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "scope start");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 7, now).refused,
               "scope pre");
        now += 1.0;
        expect(!mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 7, now).refused, "scope post");
        auto other = scope("bbbbbbbb-cccc-4ddd-8eee-ffffffffffff");
        now += 1.0;
        mustRefuse(trial.observe(other, mct::RemapPhase::Pre, mct::RemapMenu::Garage, fn(22), 8, now), "scope");
        mustRefuse(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Garage, fn(22), 8, now + 1.0),
                   "scope");
        expect(!trial.status().restoreAborted && !trial.status().parameterRewriteApplied, "scope before any offer");
        expect(trial.start(other, now + 2.0), "fresh nonce");
        const auto restarted = trial.observe(other, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 7, now + 3.0);
        expect(!restarted.offerReplace && !restarted.refused && same(restarted.reason, "await_post"),
               "old A is not a rewrite");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        expect(trial.start(current, 0.0), "menu start");
        mustRefuse(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Garage, fn(11), 1, 1.0), "menu");
        expect(trial.start(current, 2.0), "menu restart");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, 3.0).refused,
               "menu pre");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Garage, fn(11), 1, 4.0), "menu");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "duplicate start");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, now).refused,
               "duplicate A");
        now += 1.0;
        expect(!mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 1, now).refused, "duplicate A post");
        now += 1.0;
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Garage, fn(22), 2, now).refused,
               "duplicate B");
        now += 1.0;
        expect(!mct::remapPost(trial, current, mct::RemapMenu::Garage, fn(22), 2, now).refused, "duplicate B post");
        now += 1.0;
        mustRefuse(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 3, now), "same_ac");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "write-fail start");
        expect(learn(trial, current, now, synthetic), "write-fail calibration");
        const auto offer = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 9, now);
        expect(offer.offerReplace && !trial.status().parameterRewriteApplied, "write not applied yet");
        trial.acknowledgeWrite(false);
        expect(trial.status().rewriteAttempted && !trial.status().parameterRewriteApplied &&
                   !trial.status().restoreAborted && closed(trial.status()),
               "failed write ack");
        mustRefuse(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 10, now + 1.0),
                   "write_not_applied");
        trial.acknowledgeWrite(true);
        expect(!trial.status().parameterRewriteApplied, "late ack cannot apply");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "restore start");
        expect(learn(trial, current, now, synthetic), "restore calibration");
        expect(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 9, now).offerReplace,
               "restore setup");
        trial.acknowledgeWrite(true);
        now += 1.0;
        const auto mismatched = mct::remapPost(trial, current, mct::RemapMenu::Root, fn(33), 8, now);
        expect(mismatched.refused && mismatched.restoreAborted && !mismatched.offerRestore &&
                   mismatched.originalBytesAvailable && bytesAre(mismatched.bytes, 11, 0),
               "restore_aborted");
        expect(trial.status().parameterRewriteApplied && !trial.status().menuRewriteVerified &&
                   !trial.status().actionConsumptionVerified && trial.status().restoreAborted,
               "ack remains distinct from a failed read");
        trial.acknowledgeRestore(true);
        expect(!trial.status().restoreAcknowledged, "restore ack after mismatch is ignored");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "readback start");
        expect(learn(trial, current, now, synthetic), "readback calibration");
        expect(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 9, now).offerReplace,
               "readback offer");
        trial.acknowledgeWrite(true);
        now += 1.0;
        const auto readBack = mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 9, now);
        expect(readBack.restoreAborted && !readBack.offerRestore && bytesAre(readBack.bytes, 11, 0),
               "post must read C");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        expect(trial.start(current, 0.0), "timer start");
        const auto edge = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, 90.0);
        expect(!edge.refused && !edge.offerReplace, "ninety seconds still open");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 1, 90.1), "expired");
        expect(!trial.status().restoreAborted, "expiry before a proposal needs no restore");
        expect(trial.start(current, 0.0), "monotonic restart");
        expect(!trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 1, 5.0).refused,
               "monotonic pre");
        mustRefuse(mct::remapPost(trial, current, mct::RemapMenu::Root, fn(11), 1, 4.0), "time");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 0.0;
        expect(trial.start(current, now), "pending start");
        expect(learn(trial, current, now, synthetic), "pending calibration");
        expect(trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(11), 9, now).offerReplace,
               "pending offer");
        auto left = current;
        left.online = true;
        const auto lost = trial.observe(left, mct::RemapPhase::Post, mct::RemapMenu::Root, fn(33), 9, now + 1.0);
        expect(lost.restoreAborted && lost.originalBytesAvailable && !lost.offerReplace && !lost.offerRestore &&
                   bytesAre(lost.bytes, 11, 0),
               "scope loss exposes original bytes only");
        expect(!trial.status().parameterRewriteApplied, "scope loss is not a write");
        trial.acknowledgeWrite(true);
        expect(!trial.status().parameterRewriteApplied && trial.status().restoreAborted, "no write from this class");
    }

    {
        mct::NativeMenuRemapTrial trial;
        auto current = scope();
        double now = 1.0;
        expect(trial.start(current, now), "nonce start");
        expect(learn(trial, current, now, observed), "one session can learn observed ids");
        const auto offer = trial.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(observed[0]), 9, now);
        expect(offer.offerReplace && bytesAre(offer.bytes, observed[2], 0), "same-session C");
        auto fresh = scope("cccccccc-dddd-4eee-8fff-aaaaaaaaaaaa");
        expect(trial.start(fresh, now + 1.0), "new session drops ids");
        const auto again = trial.observe(fresh, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(observed[0]), 9, now + 2.0);
        expect(!again.offerReplace && !again.refused, "observed ids do not cross a nonce");
        expect(!trial.status().parameterRewriteApplied, "new session has no write");
    }

    {
        mct::NativeMenuRemapTrial idle;
        auto current = scope();
        mustRefuse(idle.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(94486), 1, 1.0), "not_started");
        expect(!idle.start(current, -1.0), "negative time");
        current.online = true;
        expect(!idle.start(current, 1.0), "online scope");
        current = scope();
        expect(idle.start(current, 1.0), "malformed start");
        mustRefuse(idle.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(-1), 1, 2.0), "malformed_name");
        expect(idle.start(current, 3.0), "phase restart");
        mustRefuse(idle.observe(current, static_cast<mct::RemapPhase>(9), mct::RemapMenu::Root, fn(11), 1, 4.0),
                   "malformed_phase");
        expect(idle.start(current, 5.0), "index cap restart");
        mustRefuse(idle.observe(current, mct::RemapPhase::Pre, mct::RemapMenu::Root, fn(1000001), 1, 6.0),
                   "malformed_name");
    }

    if (failures != 0) {
        std::fprintf(stderr, "%d native menu remap trial checks failed\n", failures);
        return 1;
    }
    std::puts("Native menu remap trial calibration passed.");
    return 0;
}
