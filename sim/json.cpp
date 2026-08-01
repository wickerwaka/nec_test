// json.cpp -- see json.h.

#include "json.h"

#include <cstdlib>

namespace json {

const Value* Value::get(const char* key) const {
    if (type != kObj) return nullptr;
    for (const auto& kv : obj)
        if (kv.first == key) return &kv.second;
    return nullptr;
}

void skip_ws(const std::string& s, size_t& p) {
    while (p < s.size() && (s[p] == ' ' || s[p] == '\t' || s[p] == '\n' ||
                            s[p] == '\r'))
        ++p;
}

static bool parse_string(const std::string& s, size_t& p, std::string& out,
                         std::string& err) {
    if (p >= s.size() || s[p] != '"') {
        err = "expected string";
        return false;
    }
    ++p;
    out.clear();
    while (p < s.size() && s[p] != '"') {
        char c = s[p++];
        if (c == '\\' && p < s.size()) {
            char e = s[p++];
            switch (e) {
                case 'n': out.push_back('\n'); break;
                case 't': out.push_back('\t'); break;
                case 'r': out.push_back('\r'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'u': {
                    if (p + 4 > s.size()) { err = "bad \\u"; return false; }
                    unsigned cp = unsigned(strtoul(s.substr(p, 4).c_str(),
                                                   nullptr, 16));
                    p += 4;
                    if (cp < 0x80) {
                        out.push_back(char(cp));
                    } else if (cp < 0x800) {
                        out.push_back(char(0xC0 | (cp >> 6)));
                        out.push_back(char(0x80 | (cp & 0x3F)));
                    } else {
                        out.push_back(char(0xE0 | (cp >> 12)));
                        out.push_back(char(0x80 | ((cp >> 6) & 0x3F)));
                        out.push_back(char(0x80 | (cp & 0x3F)));
                    }
                    break;
                }
                default: out.push_back(e); break;
            }
        } else {
            out.push_back(c);
        }
    }
    if (p >= s.size()) {
        err = "unterminated string";
        return false;
    }
    ++p;
    return true;
}

bool parse(const std::string& s, size_t& p, Value& out, std::string& err) {
    skip_ws(s, p);
    if (p >= s.size()) {
        err = "eof";
        return false;
    }
    char c = s[p];
    if (c == '{') {
        out.type = Value::kObj;
        out.obj.clear();
        ++p;
        skip_ws(s, p);
        if (p < s.size() && s[p] == '}') { ++p; return true; }
        for (;;) {
            skip_ws(s, p);
            std::string k;
            if (!parse_string(s, p, k, err)) return false;
            skip_ws(s, p);
            if (p >= s.size() || s[p] != ':') { err = "expected :"; return false; }
            ++p;
            Value v;
            if (!parse(s, p, v, err)) return false;
            out.obj.emplace_back(std::move(k), std::move(v));
            skip_ws(s, p);
            if (p < s.size() && s[p] == ',') { ++p; continue; }
            if (p < s.size() && s[p] == '}') { ++p; return true; }
            err = "expected , or }";
            return false;
        }
    }
    if (c == '[') {
        out.type = Value::kArr;
        out.arr.clear();
        ++p;
        skip_ws(s, p);
        if (p < s.size() && s[p] == ']') { ++p; return true; }
        for (;;) {
            Value v;
            if (!parse(s, p, v, err)) return false;
            out.arr.push_back(std::move(v));
            skip_ws(s, p);
            if (p < s.size() && s[p] == ',') { ++p; continue; }
            if (p < s.size() && s[p] == ']') { ++p; return true; }
            err = "expected , or ]";
            return false;
        }
    }
    if (c == '"') {
        out.type = Value::kStr;
        return parse_string(s, p, out.str, err);
    }
    if (s.compare(p, 4, "true") == 0) {
        out.type = Value::kBool; out.b = true; p += 4; return true;
    }
    if (s.compare(p, 5, "false") == 0) {
        out.type = Value::kBool; out.b = false; p += 5; return true;
    }
    if (s.compare(p, 4, "null") == 0) {
        out.type = Value::kNull; p += 4; return true;
    }
    char* end = nullptr;
    out.num = std::strtod(s.c_str() + p, &end);
    if (end == s.c_str() + p) { err = "bad value"; return false; }
    out.type = Value::kNum;
    p = size_t(end - s.c_str());
    return true;
}

}  // namespace json
