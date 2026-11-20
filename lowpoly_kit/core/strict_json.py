"""Strict JSON parser with source positions.

Differences from ``json.loads``:
- duplicate object keys are an error;
- NaN / Infinity are rejected;
- every value gets a position, available as ``{json_pointer: (line, col)}``
  so validation errors can move the Text Editor cursor to the field.

Lines and columns are 1-based.
"""


class JsonError(ValueError):
    def __init__(self, message, line, col, code="json_syntax"):
        super().__init__(f"{message} (line {line}, col {col})")
        self.reason = message
        self.line = line
        self.col = col
        self.code = code


def escape_pointer_token(token):
    return str(token).replace("~", "~0").replace("/", "~1")


def join_pointer(base, token):
    return f"{base}/{escape_pointer_token(token)}"


_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_WS = " \t\n\r"


class _Parser:
    def __init__(self, text):
        self.text = text
        self.i = 0
        self.positions = {}
        # Precompute line starts for position lookup.
        self.line_starts = [0]
        for idx, ch in enumerate(text):
            if ch == "\n":
                self.line_starts.append(idx + 1)

    def pos(self, index=None):
        index = self.i if index is None else index
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= index:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, index - self.line_starts[lo] + 1

    def error(self, message, index=None, code="json_syntax"):
        line, col = self.pos(index)
        raise JsonError(message, line, col, code)

    def skip_ws(self):
        while self.i < len(self.text) and self.text[self.i] in _WS:
            self.i += 1

    def peek(self):
        return self.text[self.i] if self.i < len(self.text) else ""

    def parse(self):
        self.skip_ws()
        value = self.value("")
        self.skip_ws()
        if self.i != len(self.text):
            self.error("unexpected data after the JSON value")
        return value

    def value(self, pointer):
        self.skip_ws()
        self.positions[pointer] = self.pos()
        ch = self.peek()
        if ch == "{":
            return self.obj(pointer)
        if ch == "[":
            return self.arr(pointer)
        if ch == '"':
            return self.string()
        if ch == "-" or ch.isdigit():
            return self.number()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(word, self.i):
                self.i += len(word)
                return val
        for word in ("NaN", "Infinity"):
            if self.text.startswith(word, self.i):
                self.error(f"{word} is not allowed", code="json_nan")
        if not ch:
            self.error("unexpected end of input")
        self.error(f"unexpected character {ch!r}")

    def obj(self, pointer):
        self.i += 1
        result = {}
        self.skip_ws()
        if self.peek() == "}":
            self.i += 1
            return result
        while True:
            self.skip_ws()
            if self.peek() != '"':
                self.error("expected a string key")
            key_index = self.i
            key = self.string()
            if key in result:
                self.error(f"duplicate key {key!r}", key_index, code="json_duplicate_key")
            self.skip_ws()
            if self.peek() != ":":
                self.error("expected ':'")
            self.i += 1
            result[key] = self.value(join_pointer(pointer, key))
            self.skip_ws()
            ch = self.peek()
            if ch == ",":
                self.i += 1
                continue
            if ch == "}":
                self.i += 1
                return result
            self.error("expected ',' or '}'")

    def arr(self, pointer):
        self.i += 1
        result = []
        self.skip_ws()
        if self.peek() == "]":
            self.i += 1
            return result
        while True:
            result.append(self.value(join_pointer(pointer, len(result))))
            self.skip_ws()
            ch = self.peek()
            if ch == ",":
                self.i += 1
                continue
            if ch == "]":
                self.i += 1
                return result
            self.error("expected ',' or ']'")

    def string(self):
        self.i += 1
        out = []
        while True:
            if self.i >= len(self.text):
                self.error("unterminated string")
            ch = self.text[self.i]
            if ch == '"':
                self.i += 1
                return "".join(out)
            if ch == "\\":
                self.i += 1
                esc = self.peek()
                if esc in _ESCAPES:
                    out.append(_ESCAPES[esc])
                    self.i += 1
                elif esc == "u":
                    hexpart = self.text[self.i + 1:self.i + 5]
                    if len(hexpart) != 4 or any(c not in "0123456789abcdefABCDEF" for c in hexpart):
                        self.error("invalid \\u escape")
                    code = int(hexpart, 16)
                    self.i += 5
                    if 0xD800 <= code < 0xDC00 and self.text.startswith("\\u", self.i):
                        low = int(self.text[self.i + 2:self.i + 6], 16)
                        if 0xDC00 <= low < 0xE000:
                            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                            self.i += 6
                    out.append(chr(code))
                else:
                    self.error("invalid escape")
            elif ord(ch) < 0x20:
                self.error("control character in string")
            else:
                out.append(ch)
                self.i += 1

    def number(self):
        start = self.i
        t = self.text
        if self.peek() == "-":
            self.i += 1
        if self.peek() == "0":
            self.i += 1
        elif self.peek().isdigit():
            while self.peek().isdigit():
                self.i += 1
        else:
            self.error("invalid number")
        is_float = False
        if self.peek() == ".":
            is_float = True
            self.i += 1
            if not self.peek().isdigit():
                self.error("invalid number")
            while self.peek().isdigit():
                self.i += 1
        if self.peek() in ("e", "E"):
            is_float = True
            self.i += 1
            if self.peek() in ("+", "-"):
                self.i += 1
            if not self.peek().isdigit():
                self.error("invalid number")
            while self.peek().isdigit():
                self.i += 1
        if t[start:self.i] == "-" or t[start:self.i].startswith("-I"):
            self.error("invalid number", start)
        literal = t[start:self.i]
        return float(literal) if is_float else int(literal)


def loads_with_positions(text):
    """Parse ``text``; return ``(value, positions)``. Raise JsonError on failure."""
    parser = _Parser(text)
    value = parser.parse()
    return value, parser.positions


def loads(text):
    return loads_with_positions(text)[0]


def position_for(positions, pointer):
    """Best position for a pointer: the pointer itself or its nearest parent."""
    while True:
        if pointer in positions:
            return positions[pointer]
        if not pointer:
            return (1, 1)
        pointer = pointer.rsplit("/", 1)[0]
