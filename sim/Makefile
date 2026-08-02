# v30sim -- NEC V30 simulator. Plain make, C++20, no external dependencies.

CXX      ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra
LDFLAGS  ?=

BIN  := v30sim
SRCS := main.cpp ucrom.cpp disasm.cpp json.cpp biu.cpp ea.cpp alu.cpp \
        loader.cpp exec.cpp case_runner.cpp \
        image_runner.cpp
OBJS := $(SRCS:.cpp=.o)
DEPS := $(OBJS:.o=.d)

ROM    := ../docs/V20BITS.TXT
GOLDEN := ../docs/V20UC.TXT

.PHONY: all clean test

all: $(BIN)

$(BIN): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS) $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -MMD -MP -c -o $@ $<

# Gate: disassembly must reproduce V20UC.TXT byte-for-byte.
test: $(BIN)
	./$(BIN) disasm $(ROM) | diff - $(GOLDEN) && echo "disasm gate: PASS"

clean:
	rm -f $(BIN) $(OBJS) $(DEPS)

-include $(DEPS)
