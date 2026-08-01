// json.h -- minimal JSON reader (no dependencies).  Enough for the
// SingleStepTests case format; numbers are IEEE doubles read as int64.

#ifndef JSON_H
#define JSON_H

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace json {

struct Value;
using Array = std::vector<Value>;
using Object = std::vector<std::pair<std::string, Value>>;

struct Value {
    enum Type : uint8_t { kNull, kBool, kNum, kStr, kArr, kObj };
    Type type = kNull;
    bool b = false;
    double num = 0;
    std::string str;
    Array arr;
    Object obj;

    const Value* get(const char* key) const;
    int64_t i() const { return int64_t(num); }
    uint32_t u() const { return uint32_t(int64_t(num)); }
};

// Parses one JSON value starting at `pos` (skipping leading whitespace).
// Returns false and sets `err` on failure.
bool parse(const std::string& s, size_t& pos, Value& out, std::string& err);
void skip_ws(const std::string& s, size_t& pos);

}  // namespace json

#endif  // JSON_H
