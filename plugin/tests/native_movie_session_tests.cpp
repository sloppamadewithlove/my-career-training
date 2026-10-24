#include "NativeMovieSession.h"

#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using Session = mct::NativeMovieSession;

const char* kNonceA = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const char* kNonceB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

bool exactHello(const std::string& body, const std::string& nonce) {
    return body == std::string("ready:") + nonce;
}

Session::Message hello(const char* nonce) {
    return {nonce, std::string("ready:") + nonce, true};
}

Session::Message choice(const char* nonce, const char* body) {
    return {nonce, body, false};
}

void testHelloExpiresWhilePublishing() {
    Session session;
    require(!session.bind(kNonceA), "The first nonce is not a rotation");
    session.noteHello(0);
    require(session.ready(0) && session.ready(4.999), "A fresh handshake is live");
    for (int i = 0; i <= 20; ++i) {
        const double time = i * Session::kPublishIntervalSeconds;
        require(session.allowPublish(time), "Heartbeat interval was not honored");
        session.notePublish(time);
        require(!session.allowPublish(time + 0.249), "A publish was allowed again inside 250ms");
    }
    require(session.ready(4.999), "View writes extended the handshake");
    require(!session.ready(5.0), "Handshake stayed live for 5 seconds without a new HELLO");
    require(session.helloExpired(5.0), "Expiry was not visible after the handshake window");
    session.notePublish(5.0);
    require(!session.ready(5.0), "Another view write revived an expired handshake");
    session.noteHello(4.0);
    require(session.ready(8.999), "A newer HELLO did not move the liveness window");
    require(!session.ready(9.0), "The refreshed handshake outlived its own 5 seconds");
}

void testBackwardClock() {
    Session session;
    session.bind(kNonceA);
    session.noteHello(10);
    session.notePublish(10);
    require(session.ready(10) && !session.allowPublish(10.1), "Forward clock baseline");
    require(!session.ready(9.0), "A backward reading kept the handshake immortal");
    require(session.allowPublish(9.0), "A backward reading froze the next view write");
    session.notePublish(9.0);
    require(!session.allowPublish(9.249), "The new publish anchor did not hold for 250ms");
    require(session.allowPublish(9.25), "The interval did not elapse after the backward anchor");
    session.noteHello(9.0);
    require(session.ready(13.999) && !session.ready(14.0), "The replacement handshake used the old deadline");
}

void testNonceRotationWithoutGap() {
    Session session;
    session.bind(kNonceA);
    session.noteHello(1);
    session.notePublish(1);
    require(session.enqueue(choice(kNonceA, "open-training")), "Current choice was rejected");
    require(session.enqueue(hello(kNonceA)), "Current HELLO was rejected");
    require(session.ready(1), "Handshake missing before rotation");
    require(session.bind(kNonceB), "A new agreed nonce did not reset the open scope");
    require(!session.ready(1), "Readiness survived nonce rotation");
    require(session.queued() == 0, "The previous nonce left queued work");
    require(!session.allowPublish(1), "Rotation bypassed the 250ms publish interval");
    require(session.allowPublish(1.25), "Rotation froze the replacement view past the interval");
    const auto drained = session.drain(1, exactHello);
    require(drained.empty(), "Cleared messages from the old nonce were applied");
    require(!session.bind(kNonceB), "Repeating the current nonce reset the scope");
    session.noteHello(2);
    require(session.ready(2), "The new nonce did not accept its own HELLO");
    require(session.enqueue(choice(kNonceA, "stale-click")), "A stale queued choice could not be represented");
    require(session.enqueue(choice(kNonceB, "fresh-click")), "The new scope rejected its choice");
    const auto mixed = session.drain(2, exactHello);
    require(mixed.size() == 2, "Rotation drain dropped a current choice or kept a third");
    require(mixed[0].kind == Session::Decision::Kind::Stale && mixed[0].body == "stale-click",
        "An old queued choice was promoted into the new scope");
    require(mixed[1].kind == Session::Decision::Kind::Choice && mixed[1].body == "fresh-click",
        "The current choice was not applied");
    require(session.ready(2), "Refusing a stale choice cleared the new handshake");
    require(session.queued() == 0, "A stale choice stayed queued after refusal");
}

void testSpamDropAndCap() {
    Session session;
    session.bind(kNonceA);
    session.noteHello(0);
    require(session.enqueue(hello(kNonceA)), "HELLO enqueue failed");
    require(session.enqueue({kNonceA, "ready:nope", true}), "Malformed HELLO enqueue failed");
    for (int i = 0; i < 3; ++i)
        require(session.enqueue(choice(kNonceA, i == 0 ? "first" : i == 1 ? "second" : "third")),
            "Choice enqueue failed");
    require(session.queued() == 5, "Queued count did not match the burst");
    const auto burst = session.drain(0, exactHello);
    require(burst.size() == 5, "Drain postponed part of the burst");
    require(burst[0].kind == Session::Decision::Kind::Hello, "Exact HELLO was treated as a choice");
    require(burst[1].kind == Session::Decision::Kind::RejectedHello, "Malformed HELLO was accepted");
    require(burst[2].kind == Session::Decision::Kind::Choice && burst[2].body == "first",
        "The first choice in the interval was not the one kept");
    require(burst[3].kind == Session::Decision::Kind::Dropped && burst[4].kind == Session::Decision::Kind::Dropped,
        "Extra choices were kept for later");
    require(session.queued() == 0, "Dropped choices returned to the queue");
    require(session.ready(4.999) && !session.ready(5.0), "Classifying the burst extended the handshake");
    require(!session.allowChoice(0.249), "A second choice was allowed inside the same interval");
    require(session.allowChoice(0.25), "The next interval did not accept one choice");

    Session rejected;
    rejected.bind(kNonceA);
    rejected.noteHello(0);
    require(rejected.enqueue({kNonceA, "ready:nope", true}), "Rejected HELLO could not be queued");
    const auto only = rejected.drain(4, exactHello);
    require(only.size() == 1 && only[0].kind == Session::Decision::Kind::RejectedHello,
        "Malformed HELLO was not refused");
    require(rejected.ready(4.999) && !rejected.ready(5.0), "A rejected HELLO refreshed liveness");

    Session capped;
    capped.bind(kNonceA);
    for (std::size_t i = 0; i < Session::kQueueLimit; ++i)
        require(capped.enqueue(choice(kNonceA, "x")), "The queue refused a message inside its cap");
    require(!capped.enqueue(choice(kNonceA, "overflow")), "The queue grew past 8");
    const auto cappedDrain = capped.drain(0, exactHello);
    require(cappedDrain.size() == Session::kQueueLimit, "The capped queue was not fully decided");
    require(cappedDrain.front().kind == Session::Decision::Kind::Choice, "The capped queue applied nothing");
    for (std::size_t i = 1; i < cappedDrain.size(); ++i)
        require(cappedDrain[i].kind == Session::Decision::Kind::Dropped, "A capped extra choice was postponed");
    require(capped.enqueue(choice(kNonceA, "after")), "The queue stayed full after a full drain");
}

void testSameNonceDoesNotResetPublish() {
    Session session;
    session.bind(kNonceA);
    session.notePublish(3);
    require(!session.bind(kNonceA), "Same nonce reported a rotation");
    require(!session.allowPublish(3.1), "Same-nonce bind cleared the publish interval");
    require(session.bind(kNonceB), "Rotation did not occur");
    require(!session.allowPublish(3.1), "Rotation published again inside 250ms");
    require(session.allowPublish(3.25), "Rotation never released the next view write");
}
}

int main() {
    try {
        testHelloExpiresWhilePublishing();
        testBackwardClock();
        testNonceRotationWithoutGap();
        testSpamDropAndCap();
        testSameNonceDoesNotResetPublish();
        std::cout << "Native movie session checks passed; no game was launched.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
