#pragma once

#include "LocalBridge.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace mct {

// Typed choices for career creation, squad, season, and rules.
// Stateless and pure: it does not draw, read the clipboard, write a file,
// send a bridge command, or launch Rocket League.
// Root copies choices onto Dispatch rows, compares the full choice, and adds
// navigation. This header does not claim a finished native menu.

struct NativeManagementChoice {
    std::string id;
    std::string label;
    std::string reason;
    std::string action;
    bool enabled = false;
    Json payload = Json::object();
};

struct NativeManagementView {
    std::string title;
    std::string body;
    std::vector<NativeManagementChoice> choices;
};

class NativeCareerManagement {
public:
    static constexpr std::size_t kMaxChoices = 18;
    static constexpr std::size_t kMaxBody = 1800;
    static constexpr std::size_t kMaxLabel = 80;
    static constexpr std::size_t kMaxReason = 240;
    static constexpr std::size_t kScanCap = 64;
    static constexpr std::size_t kShownRows = 8;
    static constexpr const char* kDefaultClub = "My Career Club";
    static constexpr const char* kWait = "Wait for the current game transition to finish.";
    static constexpr const char* kPending = "Finish or abandon the current match before changing the career.";
    static constexpr const char* kLocalRewards =
        "These are local career records, not Rocket League inventory.";

    static_assert(kMaxChoices >= 14);
    static_assert(kMaxChoices <= 24);
    static_assert(kShownRows <= kScanCap);
    static_assert(kMaxLabel >= 16);
    static_assert(kMaxBody >= 256);

    static bool allowedAction(const std::string& action);
    static NativeManagementView create(const Json& state);
    static NativeManagementView squad(const Json& state);
    static NativeManagementView season(const Json& state);
    static NativeManagementView rules(const Json& state);
    static std::string careerSummary(const Json& state);
    static std::string rewardSummary(const Json& state);
};

namespace career_management_detail {

struct RecruitSpec {
    const char* id;
    const char* role;
    const char* name;
};

struct ClubSpec {
    const char* id;
    const char* name;
};

struct Member {
    std::string id;
    std::string name;
    std::string role;
    int level = 1;
    bool starter = false;
};

struct Roster {
    int format = 0;
    std::vector<Member> squad;
    std::vector<std::string> lineup;
    Member reserve;
};

struct Gate {
    bool enabled = false;
    std::string reason;
};

inline constexpr RecruitSpec kRecruits[] = {
    {"anchor", "keeper", "Anchor"},
    {"shield", "defender", "Shield"},
    {"relay", "passer", "Relay"},
    {"comet", "attacker", "Comet"},
    {"orbit", "all-rounder", "Orbit"},
};

inline constexpr ClubSpec kClubs[] = {
    {"human", "Your club"},
    {"aurora", "Aurora Athletic"},
    {"cinder", "Cinder City"},
    {"tidal", "Tidal Rovers"},
};

inline constexpr const char* kFormats[] = {"1v1", "2v2", "3v3", "4v4"};
inline constexpr const char* kCurves[] = {"flat", "gentle", "steep"};
inline constexpr double kBaselines[] = {0.25, 0.5, 0.75};

inline const Json* child(const Json& value, const char* key) {
    if (!value.is_object() || key == nullptr) return nullptr;
    const auto it = value.find(key);
    if (it == value.end()) return nullptr;
    return &(*it);
}

inline bool copyString(const Json* item, std::size_t max, std::string& out) {
    out.clear();
    if (!item || !item->is_string()) return false;
    const auto& raw = item->get_ref<const std::string&>();
    if (raw.empty() || raw.size() > max) return false;
    out = raw;
    return true;
}

inline bool whole(const Json& value, const char* key, int& out, int low, int high) {
    const Json* item = child(value, key);
    if (!item || !item->is_number_integer()) return false;
    std::int64_t number = 0;
    if (item->is_number_unsigned()) {
        const auto wide = item->get<std::uint64_t>();
        if (wide > static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)())) return false;
        number = static_cast<std::int64_t>(wide);
    } else {
        number = item->get<std::int64_t>();
    }
    if (number < low || number > high) return false;
    out = static_cast<int>(number);
    return true;
}

inline bool unitNumber(const Json& value, double& number) {
    if (!value.is_number()) return false;
    number = value.get<double>();
    return std::isfinite(number) && number >= 0.0 && number <= 1.0;
}

inline bool nearlyEqual(double value, double expected) {
    return std::isfinite(value) && std::fabs(value - expected) <= 1e-9;
}

inline std::size_t utf8Prefix(const std::string& value, std::size_t limit) {
    std::size_t count = (std::min)(limit, value.size());
    while (count > 0 && count < value.size() && (static_cast<unsigned char>(value[count]) & 0xc0) == 0x80) --count;
    return count;
}

inline std::string clip(std::string value, std::size_t limit) {
    if (value.size() > limit) value.resize(utf8Prefix(value, limit));
    return value;
}

inline void addLine(std::string& body, const std::string& line) {
    if (line.empty()) return;
    auto text = clip(line, 180);
    if (text.empty()) return;
    if (!body.empty()) {
        if (body.size() + 1 >= NativeCareerManagement::kMaxBody) return;
        body.push_back('\n');
    }
    if (body.size() >= NativeCareerManagement::kMaxBody) return;
    if (body.size() + text.size() > NativeCareerManagement::kMaxBody)
        text.resize(utf8Prefix(text, NativeCareerManagement::kMaxBody - body.size()));
    body += text;
}

inline void capText(std::string& value) {
    if (value.size() > NativeCareerManagement::kMaxBody)
        value.resize(utf8Prefix(value, NativeCareerManagement::kMaxBody));
}

inline bool decodeUtf8(const std::string& value, std::vector<char32_t>& out, std::size_t maxPoints) {
    out.clear();
    const auto* bytes = reinterpret_cast<const unsigned char*>(value.data());
    std::size_t index = 0;
    while (index < value.size()) {
        if (out.size() > maxPoints) return false;
        const unsigned char lead = bytes[index];
        char32_t code = 0;
        std::size_t need = 0;
        if (lead <= 0x7f) {
            code = lead;
            need = 1;
        } else if ((lead & 0xe0) == 0xc0) {
            if (lead < 0xc2) return false;
            code = lead & 0x1f;
            need = 2;
        } else if ((lead & 0xf0) == 0xe0) {
            code = lead & 0x0f;
            need = 3;
        } else if ((lead & 0xf8) == 0xf0 && lead <= 0xf4) {
            code = lead & 0x07;
            need = 4;
        } else {
            return false;
        }
        if (index + need > value.size()) return false;
        for (std::size_t extra = 1; extra < need; ++extra) {
            const unsigned char cont = bytes[index + extra];
            if ((cont & 0xc0) != 0x80) return false;
            code = (code << 6) | (cont & 0x3f);
        }
        if ((need == 3 && code < 0x800) || (need == 4 && code < 0x10000) || code > 0x10ffff) return false;
        if (code >= 0xd800 && code <= 0xdfff) return false;
        out.push_back(code);
        index += need;
    }
    return out.size() <= maxPoints;
}

inline void appendUtf8(std::string& out, char32_t code) {
    if (code < 0x80) {
        out.push_back(static_cast<char>(code));
    } else if (code < 0x800) {
        out.push_back(static_cast<char>(0xc0 | (code >> 6)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3f)));
    } else if (code < 0x10000) {
        out.push_back(static_cast<char>(0xe0 | (code >> 12)));
        out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3f)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3f)));
    } else {
        out.push_back(static_cast<char>(0xf0 | (code >> 18)));
        out.push_back(static_cast<char>(0x80 | ((code >> 12) & 0x3f)));
        out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3f)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3f)));
    }
}

inline bool isControl(char32_t code) {
    if (code < 32 || code == 127 || (code >= 0x80 && code <= 0x9f)) return true;
    if (code >= 0xd800 && code <= 0xdfff) return true;
    if (code == 0xfeff || code == 0xad) return true;
    if (code >= 0x200b && code <= 0x200f) return true;
    if (code >= 0x2028 && code <= 0x202e) return true;
    if (code >= 0x2060 && code <= 0x2064) return true;
    if (code >= 0x2066 && code <= 0x206f) return true;
    return false;
}

inline bool isTrimSpace(char32_t code) {
    if (code == 0x20 || code == 0xa0 || code == 0x1680) return true;
    if (code >= 0x2000 && code <= 0x200a) return true;
    return code == 0x202f || code == 0x205f || code == 0x3000;
}

inline bool hasUrlOrPath(const std::string& value) {
    if (value.find('\\') != std::string::npos || value.find('/') != std::string::npos) return true;
    if (value.find("://") != std::string::npos) return true;
    std::string lower;
    lower.reserve(value.size());
    for (unsigned char character : value)
        lower.push_back(static_cast<char>(character >= 'A' && character <= 'Z' ? character - 'A' + 'a' : character));
    return lower.find("www.") != std::string::npos || lower.find("%2f") != std::string::npos ||
        lower.find("%5c") != std::string::npos;
}

inline bool trimPoints(const std::vector<char32_t>& points, std::size_t& begin, std::size_t& end) {
    begin = 0;
    end = points.size();
    while (begin < end && isTrimSpace(points[begin])) ++begin;
    while (end > begin && isTrimSpace(points[end - 1])) --end;
    for (std::size_t index = begin; index < end; ++index)
        if (isControl(points[index])) return false;
    return end > begin;
}

inline std::string encodeRange(const std::vector<char32_t>& points, std::size_t begin, std::size_t end,
                               std::size_t maxChars) {
    std::string out;
    std::size_t count = 0;
    for (std::size_t index = begin; index < end && count < maxChars; ++index, ++count)
        appendUtf8(out, points[index]);
    return out;
}

inline std::string shownText(const std::string& raw, const std::string& fallback, std::size_t maxChars) {
    if (raw.empty() || raw.size() > 256 || hasUrlOrPath(raw)) return fallback;
    std::vector<char32_t> points;
    if (!decodeUtf8(raw, points, 64)) return fallback;
    std::size_t begin = 0, end = 0;
    if (!trimPoints(points, begin, end) || end - begin > 48) return fallback;
    auto text = encodeRange(points, begin, end, maxChars);
    return text.empty() ? fallback : text;
}

inline std::string validatedDraftName(const Json& state) {
    const Json* draft = child(state, "career_draft");
    std::string raw;
    if (!draft || !copyString(child(*draft, "team_name"), 160, raw) || hasUrlOrPath(raw))
        return NativeCareerManagement::kDefaultClub;
    std::vector<char32_t> points;
    if (!decodeUtf8(raw, points, 64)) return NativeCareerManagement::kDefaultClub;
    std::size_t begin = 0, end = 0;
    if (!trimPoints(points, begin, end) || end - begin > 40) return NativeCareerManagement::kDefaultClub;
    for (std::size_t index = begin; index < end; ++index) {
        const char32_t code = points[index];
        if (code == '/' || code == '\\') return NativeCareerManagement::kDefaultClub;
    }
    auto name = encodeRange(points, begin, end, 40);
    if (name.empty() || hasUrlOrPath(name)) return NativeCareerManagement::kDefaultClub;
    return name;
}

inline bool safeToken(const std::string& value, std::size_t max) {
    if (value.empty() || value.size() > max) return false;
    for (unsigned char character : value) {
        const bool ok = (character >= 'a' && character <= 'z') || (character >= 'A' && character <= 'Z') ||
            (character >= '0' && character <= '9') || character == '_' || character == '-';
        if (!ok) return false;
    }
    return true;
}

inline const Json* existingCareer(const Json& state) {
    const Json* career = child(state, "career");
    if (!career || !career->is_object() || career->empty()) return nullptr;
    return career;
}

inline const Json* identifiedCareer(const Json& state) {
    const Json* career = existingCareer(state);
    if (!career) return nullptr;
    std::string id;
    if (!copyString(child(*career, "id"), 128, id) || !safeToken(id, 128)) return nullptr;
    return career;
}

inline bool pendingSession(const Json& career) {
    const Json* pending = child(career, "pending_session");
    return pending && !pending->is_null();
}

inline Gate gateFor(const Json& state, const Json* career) {
    Gate gate;
    if (!state.is_object()) {
        gate.reason = "Career choices are not available yet.";
        return gate;
    }
    const Json* session = child(state, "session");
    const Json* busy = session && session->is_object() ? child(*session, "busy") : nullptr;
    if (!busy || !busy->is_boolean() || busy->get<bool>()) {
        gate.reason = NativeCareerManagement::kWait;
        return gate;
    }
    if (career && pendingSession(*career)) {
        gate.reason = NativeCareerManagement::kPending;
        return gate;
    }
    gate.enabled = true;
    return gate;
}

inline const RecruitSpec* recruitSpec(const std::string& id) {
    for (const auto& spec : kRecruits)
        if (id == spec.id) return &spec;
    return nullptr;
}

inline const ClubSpec* clubSpec(const std::string& id) {
    for (const auto& spec : kClubs)
        if (id == spec.id) return &spec;
    return nullptr;
}

inline bool knownClub(const std::string& id) { return clubSpec(id) != nullptr; }

inline bool validRecruit(const Json* record, const RecruitSpec& spec) {
    if (!record || !record->is_object()) return false;
    std::string id;
    std::string role;
    std::string name;
    if (!copyString(child(*record, "id"), 32, id) || id != spec.id) return false;
    if (!copyString(child(*record, "role"), 32, role) || role != spec.role) return false;
    if (!copyString(child(*record, "name"), 256, name)) return false;
    std::vector<char32_t> points;
    if (!decodeUtf8(name, points, 64)) return false;
    std::size_t begin = 0, end = 0;
    if (!trimPoints(points, begin, end) || end - begin > 48) return false;
    int level = 0;
    return whole(*record, "level", level, 1, 5);
}

inline std::string memberName(const Json& record, const RecruitSpec& spec, std::size_t maxChars) {
    std::string raw;
    if (!copyString(child(record, "name"), 256, raw)) return spec.name;
    return shownText(raw, spec.name, maxChars);
}

inline bool usableRoster(const Json& career, Roster& roster) {
    roster = {};
    if (!whole(career, "format", roster.format, 1, 4)) return false;
    const Json* squad = child(career, "squad");
    const Json* lineup = child(career, "lineup");
    const Json* recruits = child(career, "recruits");
    if (!squad || !squad->is_array() || squad->size() != 4) return false;
    if (!lineup || !lineup->is_array() || lineup->size() != static_cast<std::size_t>(roster.format - 1)) return false;
    if (!recruits || !recruits->is_object()) return false;
    for (const auto& spec : kRecruits)
        if (!validRecruit(child(*recruits, spec.id), spec)) return false;
    std::vector<std::string> squadIds;
    for (const auto& item : *squad) {
        if (!item.is_string()) return false;
        const auto& id = item.get_ref<const std::string&>();
        if (!recruitSpec(id) || std::find(squadIds.begin(), squadIds.end(), id) != squadIds.end()) return false;
        squadIds.push_back(id);
    }
    if (squadIds.size() != 4) return false;
    for (const auto& item : *lineup) {
        if (!item.is_string()) return false;
        const auto& id = item.get_ref<const std::string&>();
        if (std::find(squadIds.begin(), squadIds.end(), id) == squadIds.end()) return false;
        if (std::find(roster.lineup.begin(), roster.lineup.end(), id) != roster.lineup.end()) return false;
        roster.lineup.push_back(id);
    }
    int reserves = 0;
    for (const auto& spec : kRecruits) {
        if (std::find(squadIds.begin(), squadIds.end(), spec.id) != squadIds.end()) continue;
        roster.reserve.id = spec.id;
        roster.reserve.role = spec.role;
        roster.reserve.name = memberName(*child(*recruits, spec.id), spec, 40);
        roster.reserve.level = 1;
        whole(*child(*recruits, spec.id), "level", roster.reserve.level, 1, 5);
        ++reserves;
    }
    if (reserves != 1) return false;
    for (const auto& id : squadIds) {
        const auto* spec = recruitSpec(id);
        const auto* record = child(*recruits, id.c_str());
        Member member;
        member.id = id;
        member.role = spec->role;
        member.name = memberName(*record, *spec, 40);
        member.level = 1;
        whole(*record, "level", member.level, 1, 5);
        member.starter = std::find(roster.lineup.begin(), roster.lineup.end(), id) != roster.lineup.end();
        roster.squad.push_back(std::move(member));
    }
    return true;
}

inline std::uint64_t fnv(const std::string& value) {
    std::uint64_t hash = 14695981039346656037ull;
    for (unsigned char character : value) {
        hash ^= character;
        hash *= 1099511628211ull;
    }
    return hash;
}

inline std::string hex64(std::uint64_t value) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string out(16, '0');
    for (int index = 15; index >= 0; --index) {
        out[static_cast<std::size_t>(index)] = digits[value & 0xfull];
        value >>= 4;
    }
    return out;
}

inline std::string baselineToken(const Json& value) {
    double number = 0;
    if (!unitNumber(value, number)) return "invalid";
    if (nearlyEqual(number, 0.25)) return "0.25";
    if (nearlyEqual(number, 0.5)) return "0.50";
    if (nearlyEqual(number, 0.75)) return "0.75";
    if (nearlyEqual(number, std::round(number))) return std::to_string(static_cast<int>(std::lround(number)));
    std::uint64_t bits = 0;
    static_assert(sizeof(double) == 8, "baseline token expects a 64-bit double");
    std::memcpy(&bits, &number, sizeof(bits));
    return hex64(bits);
}

inline std::string baselineWords(const Json& value) {
    double number = 0;
    if (!unitNumber(value, number)) return {};
    if (nearlyEqual(number, 0.25)) return "0.25";
    if (nearlyEqual(number, 0.5)) return "0.50";
    if (nearlyEqual(number, 0.75)) return "0.75";
    if (nearlyEqual(number, std::round(number))) return std::to_string(static_cast<int>(std::lround(number)));
    const auto token = baselineToken(value);
    if (token.size() > 8) return "custom";
    return token;
}

inline const char* curveWord(const std::string& curve) {
    if (curve == "flat") return "Flat";
    if (curve == "gentle") return "Gentle";
    if (curve == "steep") return "Steep";
    return nullptr;
}

inline void addChoice(NativeManagementView& view, std::string id, std::string label, bool enabled,
                      const std::string& blocked, std::string action, Json payload) {
    if (view.choices.size() >= NativeCareerManagement::kMaxChoices) return;
    if (!NativeCareerManagement::allowedAction(action) || id.empty() || id.size() > 160) return;
    if (!payload.is_object()) return;
    for (const auto& existing : view.choices)
        if (existing.id == id) return;
    label = clip(std::move(label), NativeCareerManagement::kMaxLabel);
    if (label.empty()) return;
    NativeManagementChoice choice;
    choice.id = std::move(id);
    choice.label = std::move(label);
    choice.enabled = enabled;
    choice.reason = enabled ? std::string() : clip(blocked.empty() ? std::string("That choice is not available.") : blocked,
                                                    NativeCareerManagement::kMaxReason);
    choice.action = std::move(action);
    choice.payload = std::move(payload);
    view.choices.push_back(std::move(choice));
}

inline void combinations(const std::vector<Member>& squad, int count, std::vector<std::vector<std::string>>& out) {
    out.clear();
    if (count < 0 || count > static_cast<int>(squad.size())) return;
    if (count == 0) {
        out.push_back({});
        return;
    }
    std::vector<int> pick(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index) pick[static_cast<std::size_t>(index)] = index;
    while (true) {
        std::vector<std::string> row;
        for (int index : pick) row.push_back(squad[static_cast<std::size_t>(index)].id);
        out.push_back(std::move(row));
        int cursor = count - 1;
        while (cursor >= 0 && pick[static_cast<std::size_t>(cursor)] ==
               static_cast<int>(squad.size()) - count + cursor)
            --cursor;
        if (cursor < 0) break;
        ++pick[static_cast<std::size_t>(cursor)];
        for (int next = cursor + 1; next < count; ++next)
            pick[static_cast<std::size_t>(next)] = pick[static_cast<std::size_t>(next - 1)] + 1;
    }
}

inline bool sameSet(std::vector<std::string> left, std::vector<std::string> right) {
    if (left.size() != right.size()) return false;
    std::sort(left.begin(), left.end());
    std::sort(right.begin(), right.end());
    return left == right;
}

inline std::string memberLabel(const Roster& roster, const std::string& id, std::size_t maxChars) {
    for (const auto& member : roster.squad)
        if (member.id == id) return clip(member.name, maxChars);
    if (roster.reserve.id == id) return clip(roster.reserve.name, maxChars);
    const auto* spec = recruitSpec(id);
    return spec ? spec->name : "Bot";
}

inline const Json* currentSeason(const Json& career) {
    const Json* seasons = child(career, "seasons");
    if (!seasons || !seasons->is_array()) return nullptr;
    const Json* indexValue = child(career, "current_season");
    if (!indexValue || !indexValue->is_number_integer()) return nullptr;
    std::uint64_t index = 0;
    if (indexValue->is_number_unsigned()) index = indexValue->get<std::uint64_t>();
    else {
        const auto signedIndex = indexValue->get<std::int64_t>();
        if (signedIndex < 0) return nullptr;
        index = static_cast<std::uint64_t>(signedIndex);
    }
    if (index >= seasons->size()) return nullptr;
    const auto& season = (*seasons)[static_cast<std::size_t>(index)];
    if (!season.is_object()) return nullptr;
    return &season;
}

inline std::string clubName(const Json& career, const Json* season, const std::string& id) {
    const auto* spec = clubSpec(id);
    if (!spec) return "Club";
    if (id == "human") {
        std::string raw;
        if (copyString(child(career, "team_name"), 256, raw)) {
            auto shown = shownText(raw, "", 40);
            if (!shown.empty()) return shown;
        }
        return spec->name;
    }
    if (!season) return spec->name;
    const Json* clubs = child(*season, "clubs");
    if (!clubs || !clubs->is_array()) return spec->name;
    const auto stop = (std::min)(clubs->size(), NativeCareerManagement::kScanCap);
    for (std::size_t index = 0; index < stop; ++index) {
        const auto& club = (*clubs)[index];
        std::string clubId;
        if (!copyString(child(club, "id"), 32, clubId) || clubId != id) continue;
        std::string raw;
        if (!copyString(child(club, "name"), 256, raw)) return spec->name;
        return shownText(raw, spec->name, 40);
    }
    return spec->name;
}

inline std::string scoreLine(const std::string& prefix, const std::string& kind, const std::string& home,
                             int homeScore, const std::string& away, int awayScore) {
    return prefix + " " + kind + ": " + home + " " + std::to_string(homeScore) + ", " + away + " " +
        std::to_string(awayScore);
}

inline bool completedScore(const Json& fixture, int& homeScore, int& awayScore, bool& simulated,
                           std::string& home, std::string& away, std::string& phase, int& round) {
    std::string status;
    if (!copyString(child(fixture, "status"), 32, status) || status != "completed") return false;
    const Json* result = child(fixture, "result");
    if (!result || !result->is_object()) return false;
    if (!whole(*result, "home_score", homeScore, 0, 999) || !whole(*result, "away_score", awayScore, 0, 999))
        return false;
    if (homeScore == awayScore) return false;
    if (!copyString(child(fixture, "home"), 32, home) || !copyString(child(fixture, "away"), 32, away)) return false;
    if (!knownClub(home) || !knownClub(away) || home == away) return false;
    simulated = false;
    const Json* flag = child(*result, "simulated");
    if (flag && flag->is_boolean() && flag->get<bool>()) simulated = true;
    std::string provenance;
    if (copyString(child(*result, "provenance"), 32, provenance) && provenance == "simulated") simulated = true;
    phase.clear();
    copyString(child(fixture, "phase"), 32, phase);
    if (phase != "league" && phase != "semifinal" && phase != "final") phase = "league";
    round = 0;
    if (!whole(fixture, "round", round, 1, 8)) round = 0;
    return true;
}

inline void collectHistory(const Json& career, const Json* season, std::vector<std::string>& lines) {
    lines.clear();
    if (!season) return;
    const char* keys[] = {"fixtures", "playoffs"};
    for (const char* key : keys) {
        const Json* rows = child(*season, key);
        if (!rows || !rows->is_array()) continue;
        const auto size = rows->size();
        const auto scanned = (std::min)(size, NativeCareerManagement::kScanCap);
        const auto begin = size - scanned;
        for (std::size_t index = begin; index < size; ++index) {
            const auto& fixture = (*rows)[index];
            if (!fixture.is_object()) continue;
            int homeScore = 0, awayScore = 0, round = 0;
            bool simulated = false;
            std::string home, away, phase;
            if (!completedScore(fixture, homeScore, awayScore, simulated, home, away, phase, round)) continue;
            const bool played = !simulated && (home == "human" || away == "human");
            std::string prefix = "Match";
            if (phase == "final") prefix = "Final";
            else if (phase == "semifinal") prefix = "Semifinal";
            else if (round > 0) prefix = "Round " + std::to_string(round);
            lines.push_back(scoreLine(prefix, played ? "played" : "recorded",
                                      clubName(career, season, home), homeScore,
                                      clubName(career, season, away), awayScore));
        }
    }
    if (lines.size() > NativeCareerManagement::kShownRows)
        lines.erase(lines.begin(), lines.begin() + static_cast<std::ptrdiff_t>(lines.size() - NativeCareerManagement::kShownRows));
}

inline std::string rewardLine(const Json& reward) {
    if (!reward.is_object()) return {};
    std::string type;
    if (!copyString(child(reward, "type"), 32, type)) return {};
    if (type == "match_experience") return "Match experience";
    if (type == "season_trophy") return "League Champion";
    if (type == "season_badge") return "Season Complete";
    return {};
}

inline void collectRewards(const Json& career, std::vector<std::string>& lines) {
    lines.clear();
    const Json* rewards = child(career, "rewards");
    if (!rewards || !rewards->is_array()) return;
    const auto size = rewards->size();
    const auto scanned = (std::min)(size, NativeCareerManagement::kScanCap);
    const auto begin = size - scanned;
    for (std::size_t index = begin; index < size; ++index) {
        auto line = rewardLine((*rewards)[index]);
        if (!line.empty()) lines.push_back(std::move(line));
    }
    if (lines.size() > NativeCareerManagement::kShownRows)
        lines.erase(lines.begin(), lines.begin() + static_cast<std::ptrdiff_t>(lines.size() - NativeCareerManagement::kShownRows));
}

inline void appendStandings(std::string& body, const Json& state) {
    const Json* rows = child(state, "standings");
    if (!rows || !rows->is_array() || rows->empty()) {
        addLine(body, "No standings are published yet.");
        return;
    }
    const auto shown = (std::min)(rows->size(), NativeCareerManagement::kShownRows);
    const auto scanned = (std::min)(rows->size(), NativeCareerManagement::kScanCap);
    for (std::size_t index = 0; index < shown && index < scanned; ++index) {
        const auto& row = (*rows)[index];
        std::string name;
        std::string raw;
        if (copyString(child(row, "name"), 256, raw)) name = shownText(raw, "", 40);
        if (name.empty()) {
            std::string id;
            if (!copyString(child(row, "id"), 32, id)) copyString(child(row, "club_id"), 32, id);
            name = knownClub(id) ? clubSpec(id)->name : "Club";
        }
        int position = static_cast<int>(index + 1);
        int publishedPosition = 0;
        if (whole(row, "position", publishedPosition, 1, 10000)) position = publishedPosition;
        std::string line = std::to_string(position) + ". " + name;
        int points = 0;
        if (row.is_object() && whole(row, "points", points, 0, 1000000))
            line += " - " + std::to_string(points) + " points";
        addLine(body, line);
    }
}

inline std::string championId(const Json* season) {
    if (!season) return {};
    const Json* champion = child(*season, "champion");
    if (!champion || !champion->is_string()) return {};
    std::string id;
    if (!copyString(champion, 32, id) || !knownClub(id)) return {};
    return id;
}

inline int seasonNumber(const Json& career, const Json* season) {
    int number = 0;
    if (season && whole(*season, "number", number, 1, 10000)) return number;
    int index = 0;
    if (whole(career, "current_season", index, 0, 9999)) return index + 1;
    return 0;
}

inline bool lastPlayed(const Json& state, const Json& career, const Json* season, std::string& line) {
    (void)state; // Only saved fixtures in this career establish its played results.
    std::vector<std::string> history;
    collectHistory(career, season, history);
    for (auto it = history.rbegin(); it != history.rend(); ++it) {
        if (it->find(" played: ") != std::string::npos) {
            const auto split = it->find(": ");
            line = "Last played result: " + (split == std::string::npos ? *it : it->substr(split + 2));
            return true;
        }
    }
    return false;
}

inline Json difficultyBaseline(const Json& career, std::string& curve, bool& curveOk, bool& baselineOk) {
    curveOk = false;
    baselineOk = false;
    curve.clear();
    const Json* difficulty = child(career, "difficulty");
    if (!difficulty || !difficulty->is_object()) return Json();
    std::string rawCurve;
    if (copyString(child(*difficulty, "curve"), 16, rawCurve) && curveWord(rawCurve)) {
        curve = rawCurve;
        curveOk = true;
    }
    const Json* baseline = child(*difficulty, "baseline");
    double number = 0;
    if (baseline && unitNumber(*baseline, number)) {
        baselineOk = true;
        return *baseline;
    }
    return Json();
}

} // namespace career_management_detail

inline bool NativeCareerManagement::allowedAction(const std::string& action) {
    return action == "career_name_clipboard" || action == "new_career" || action == "lineup" ||
        action == "replace_recruit" || action == "rename_recruit_clipboard" || action == "next_season" ||
        action == "set_format" || action == "set_difficulty";
}

inline NativeManagementView NativeCareerManagement::create(const Json& state) {
    using namespace career_management_detail;
    NativeManagementView view;
    view.title = "New career";
    const Json* existing = existingCareer(state);
    const auto club = validatedDraftName(state);
    const auto gate = gateFor(state, existing);
    if (existing) {
        addLine(view.body, "Start a new career for this club. This replaces the current career.");
        addLine(view.body, "The current career is exported automatically before it is replaced.");
        std::string current;
        if (copyString(child(*existing, "team_name"), 256, current)) {
            auto shown = shownText(current, "", 40);
            if (!shown.empty()) addLine(view.body, "Current club: " + shown + ".");
        }
        addLine(view.body, "Choosing a format confirms the replacement.");
    } else {
        addLine(view.body, "Start a new career for this club.");
    }
    addLine(view.body, "Club name: " + club + ".");
    addLine(view.body, "Choose 1v1, 2v2, 3v3, or 4v4. The new career uses the standard recruits.");
    Json paste = Json::object();
    addChoice(view, "create.paste", "Paste club name", gate.enabled, gate.reason, "career_name_clipboard", paste);
    const auto stamp = hex64(fnv(club));
    for (int format = 1; format <= 4; ++format) {
        Json payload = Json::object();
        payload["team_name"] = club;
        payload["format"] = format;
        const std::string label = existing ? std::string("Replace career with new ") + kFormats[format - 1]
                                            : std::string("Start a new ") + kFormats[format - 1] + " career";
        addChoice(view, "create.new." + std::to_string(format) + "." + stamp, label, gate.enabled, gate.reason,
                  "new_career", payload);
    }
    capText(view.body);
    return view;
}

inline NativeManagementView NativeCareerManagement::squad(const Json& state) {
    using namespace career_management_detail;
    NativeManagementView view;
    view.title = "Squad";
    const Json* career = identifiedCareer(state);
    if (!career) {
        addLine(view.body, "No career exists yet. Squad changes are unavailable.");
        capText(view.body);
        return view;
    }
    Roster roster;
    if (!usableRoster(*career, roster)) {
        addLine(view.body, "This squad is not usable. Lineup and recruit changes are unavailable.");
        capText(view.body);
        return view;
    }
    const auto gate = gateFor(state, career);
    addLine(view.body, std::string(kFormats[roster.format - 1]) + " squad.");
    for (const auto& member : roster.squad)
        addLine(view.body, member.name + " - " + member.role + " - level " + std::to_string(member.level) +
            (member.starter ? " - starter" : " - bench"));
    addLine(view.body, roster.reserve.name + " - " + roster.reserve.role + " - level " +
        std::to_string(roster.reserve.level) + " - reserve");
    std::vector<std::vector<std::string>> rows;
    combinations(roster.squad, roster.format - 1, rows);
    for (auto& row : rows)
        if (sameSet(row, roster.lineup)) row = roster.lineup;
    for (const auto& row : rows) {
        const bool current = row == roster.lineup;
        std::string id = row.empty() ? "squad.lineup.empty" : "squad.lineup";
        std::string names;
        Json ids = Json::array();
        for (std::size_t index = 0; index < row.size(); ++index) {
            id += ".";
            id += row[index];
            ids.push_back(row[index]);
            if (index) names += ", ";
            names += memberLabel(roster, row[index], 18);
        }
        Json payload = Json::object();
        payload["ids"] = std::move(ids);
        const std::string label = row.empty()
            ? std::string(current ? "Current lineup: you only" : "Lineup: you only")
            : std::string(current ? "Current lineup: " : "Lineup: ") + names;
        addChoice(view, id, label, gate.enabled, gate.reason, "lineup", payload);
    }
    for (const auto& member : roster.squad) {
        Json payload = Json::object();
        payload["outgoing"] = member.id;
        payload["incoming"] = roster.reserve.id;
        addChoice(view, "squad.replace." + member.id + "." + roster.reserve.id,
                  "Replace " + memberLabel(roster, member.id, 24) + " with " + memberLabel(roster, roster.reserve.id, 24),
                  gate.enabled, gate.reason, "replace_recruit", payload);
    }
    for (const auto& member : roster.squad) {
        Json payload = Json::object();
        payload["id"] = member.id;
        addChoice(view, "squad.rename." + member.id,
                  "Paste a new name for " + memberLabel(roster, member.id, 24),
                  gate.enabled, gate.reason, "rename_recruit_clipboard", payload);
    }
    capText(view.body);
    return view;
}

inline NativeManagementView NativeCareerManagement::season(const Json& state) {
    using namespace career_management_detail;
    NativeManagementView view;
    view.title = "Season";
    const Json* career = identifiedCareer(state);
    if (!career) {
        addLine(view.body, "Season standings, results, and rewards are unavailable until a career exists.");
        capText(view.body);
        return view;
    }
    const Json* season = currentSeason(*career);
    const int number = seasonNumber(*career, season);
    const auto champion = championId(season);
    if (number > 0) addLine(view.body, "Season " + std::to_string(number) + ".");
    else addLine(view.body, "The current season is not available.");
    appendStandings(view.body, state);
    if (!champion.empty()) addLine(view.body, "Champion: " + clubName(*career, season, champion) + ".");
    else addLine(view.body, "No champion is published yet.");
    std::vector<std::string> history;
    collectHistory(*career, season, history);
    if (history.empty()) addLine(view.body, "No completed result is published yet.");
    else {
        addLine(view.body, "Recent results:");
        for (const auto& line : history) addLine(view.body, line);
    }
    addLine(view.body, "Career rewards:");
    std::vector<std::string> rewards;
    collectRewards(*career, rewards);
    if (rewards.empty()) addLine(view.body, "No career rewards are published yet.");
    else
        for (const auto& line : rewards) addLine(view.body, line);
    addLine(view.body, kLocalRewards);
    const auto gate = gateFor(state, career);
    const bool ready = gate.enabled && !champion.empty();
    std::string reason = gate.reason;
    if (gate.enabled && champion.empty()) reason = "Finish this season before starting the next one.";
    Json payload = Json::object();
    addChoice(view, champion.empty() ? "season.next.unavailable" : "season.next." + champion, "Start next season",
              ready, reason, "next_season", payload);
    capText(view.body);
    return view;
}

inline NativeManagementView NativeCareerManagement::rules(const Json& state) {
    using namespace career_management_detail;
    NativeManagementView view;
    view.title = "Career rules";
    const Json* career = identifiedCareer(state);
    if (!career) {
        addLine(view.body, "Career rules are unavailable until a career exists.");
        capText(view.body);
        return view;
    }
    const auto gate = gateFor(state, career);
    addLine(view.body, "Format and difficulty apply to future unstarted rounds.");
    addLine(view.body, "Previous results keep the rules they were played under.");
    addLine(view.body, "1v1, 2v2, 3v3, and 4v4 can be selected here.");
    int format = 0;
    const bool formatOk = whole(*career, "format", format, 1, 4);
    if (formatOk) addLine(view.body, std::string("Current format: ") + kFormats[format - 1] + ".");
    else addLine(view.body, "The current format is not available.");
    std::string curve;
    bool curveOk = false, baselineOk = false;
    const Json baseline = difficultyBaseline(*career, curve, curveOk, baselineOk);
    if (curveOk && baselineOk) {
        addLine(view.body, "Current difficulty: baseline " + baselineWords(baseline) + ", " + curve + " curve.");
        addLine(view.body, "A baseline choice keeps the " + curve + " curve. A curve choice keeps baseline " +
            baselineWords(baseline) + ".");
    } else {
        if (!curveOk) addLine(view.body, "The season curve is not available, so baseline choices are hidden.");
        if (!baselineOk) addLine(view.body, "The difficulty baseline is not available, so curve choices are hidden.");
    }
    for (int option = 1; option <= 4; ++option) {
        Json payload = Json::object();
        payload["format"] = option;
        const bool selected = formatOk && option == format;
        const std::string label = selected ? std::string("Selected: ") + kFormats[option - 1]
                                            : std::string("Set format to ") + kFormats[option - 1];
        addChoice(view, "rules.format." + std::to_string(option), label, gate.enabled, gate.reason, "set_format", payload);
    }
    if (curveOk) {
        for (double preset : kBaselines) {
            Json payload = Json::object();
            payload["baseline"] = preset;
            payload["curve"] = curve;
            const bool selected = baselineOk && nearlyEqual(baseline.get<double>(), preset);
            const std::string words = baselineWords(Json(preset));
            const std::string label = (selected ? "Selected: baseline " : "Baseline ") + words + " with " + curve + " curve";
            addChoice(view, "rules.baseline." + baselineToken(Json(preset)) + "." + curve, label, gate.enabled, gate.reason,
                      "set_difficulty", payload);
        }
    }
    if (baselineOk) {
        const auto token = baselineToken(baseline);
        for (const char* option : kCurves) {
            Json payload = Json::object();
            payload["baseline"] = baseline;
            payload["curve"] = option;
            const char* pretty = curveWord(option);
            const bool selected = curveOk && curve == option;
            const std::string label = selected ? std::string("Selected: ") + pretty + " curve"
                                                : std::string(pretty) + " curve";
            addChoice(view, std::string("rules.curve.") + option + "." + token, label, gate.enabled, gate.reason,
                      "set_difficulty", payload);
        }
    }
    capText(view.body);
    return view;
}

inline std::string NativeCareerManagement::careerSummary(const Json& state) {
    using namespace career_management_detail;
    const Json* career = identifiedCareer(state);
    if (!career) return "No career is published yet.";
    std::string body;
    const Json* season = currentSeason(*career);
    const int number = seasonNumber(*career, season);
    const auto champion = championId(season);
    if (!champion.empty()) {
        const std::string heading = (number > 0 ? "Season " + std::to_string(number) + " champion: "
                                                 : "Champion: ") +
            clubName(*career, season, champion) + ".";
        addLine(body, heading);
    } else if (number > 0) {
        addLine(body, "Season " + std::to_string(number) + " is in progress.");
    } else {
        addLine(body, "The current season is not available.");
    }
    const Json* rows = child(state, "standings");
    if (!rows || !rows->is_array() || rows->empty()) addLine(body, "No standings are published yet.");
    else appendStandings(body, state);
    std::string played;
    if (lastPlayed(state, *career, season, played)) addLine(body, played);
    else addLine(body, "No played result is published yet.");
    capText(body);
    return body;
}

inline std::string NativeCareerManagement::rewardSummary(const Json& state) {
    using namespace career_management_detail;
    const Json* career = identifiedCareer(state);
    std::string body = kLocalRewards;
    if (!career) {
        body = std::string("No career rewards are published yet. ") + kLocalRewards;
        capText(body);
        return body;
    }
    std::vector<std::string> rewards;
    collectRewards(*career, rewards);
    if (rewards.empty()) addLine(body, "No career rewards are published yet.");
    else
        for (const auto& line : rewards) addLine(body, line);
    capText(body);
    return body;
}

} // namespace mct
