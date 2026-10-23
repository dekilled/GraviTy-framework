"""Transforma o texto .gvt numa lista de tokens.

As quebras de linha terminam um comando (como no Go e no Swift), mas só quando a linha acaba
num nome, num número, num texto ou num fecho: `a +` no fim da linha continua na próxima.
Dentro de ( ) e [ ] as quebras de linha não contam.
"""

from .errors import GvtError, Pos

KEYWORDS = {
    "app", "fn", "var", "let", "if", "else", "for", "in", "while", "return", "break", "continue",
    "true", "false", "and", "or", "not", "view",
}

# tokens depois dos quais uma quebra de linha termina o comando
ENDS_STATEMENT = {"NAME", "INT", "FLOAT", "STRING", ")", "]", "}", "true", "false", "return", "break", "continue"}

SYMBOLS = [
    "..=", "...", "->", "==", "!=", "<=", ">=", "&&", "||", "+=", "-=", "*=", "/=", "..",
    "(", ")", "{", "}", "[", "]", ",", ":", ";", ".", "+", "-", "*", "/", "%", "<", ">", "=", "!", "?", "#",
]


class Token:
    __slots__ = ("kind", "value", "pos", "end")

    def __init__(self, kind, value, pos):
        self.kind = kind    # NAME, INT, FLOAT, STRING, NEWLINE, EOF, uma palavra-chave ou um símbolo
        self.value = value  # o texto do nome, o número, ou as partes do texto (ver lex_string)
        self.pos = pos
        self.end = pos      # logo depois do token: para dizer "falta um ) aqui"

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.pos})"


def tokenize(text):
    tokens = []
    depth = []  # pilha de ( [ { abertos: as linhas só contam fora de ( ) e [ ]
    i = 0
    line, col = 1, 1
    n = len(text)

    def add(kind, value, pos):
        tokens.append(Token(kind, value, pos))

    while i < n:
        c = text[i]
        pos = Pos(line, col)
        if tokens and tokens[-1].end is tokens[-1].pos and tokens[-1].kind != "NEWLINE":
            tokens[-1].end = pos

        if c == "\n":
            if (not depth or depth[-1] == "{") and tokens and tokens[-1].kind in ENDS_STATEMENT:
                add("NEWLINE", None, pos)
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
                col += 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise GvtError(pos, "comentário /* sem o */ que o fecha")
            chunk = text[i : end + 2]
            nl = chunk.count("\n")
            if nl:
                line += nl
                col = len(chunk) - chunk.rfind("\n")
            else:
                col += len(chunk)
            i = end + 2
            continue

        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            add(word if word in KEYWORDS else "NAME", word, pos)
            col += j - i
            i = j
            continue

        if c.isdigit():
            j = i
            if text.startswith(("0x", "0X"), i):
                j += 2
                while j < n and (text[j] in "0123456789abcdefABCDEF_"):
                    j += 1
                add("INT", int(text[i + 2 : j].replace("_", ""), 16), pos)
            else:
                while j < n and (text[j].isdigit() or text[j] == "_"):
                    j += 1
                is_float = False
                # 1.5 é um número; 0..3 é um intervalo
                if j + 1 < n and text[j] == "." and text[j + 1].isdigit():
                    is_float = True
                    j += 1
                    while j < n and (text[j].isdigit() or text[j] == "_"):
                        j += 1
                raw = text[i:j].replace("_", "")
                add("FLOAT" if is_float else "INT", float(raw) if is_float else int(raw), pos)
            if j < n and (text[j].isalpha() or text[j] == "_"):
                raise GvtError(Pos(line, col + j - i), f"letra colada no número: '{text[i:j + 1]}'")
            col += j - i
            i = j
            continue

        if c == '"':
            parts, j, line2, col2 = lex_string(text, i, line, col)
            add("STRING", parts, pos)
            i, line, col = j, line2, col2
            continue

        for sym in SYMBOLS:
            if text.startswith(sym, i):
                if sym in ("(", "[", "{"):
                    depth.append(sym)
                elif sym in (")", "]", "}"):
                    if depth:
                        depth.pop()
                add(sym, sym, pos)
                i += len(sym)
                col += len(sym)
                break
        else:
            raise GvtError(pos, f"caractere inesperado: '{c}'")

    if not tokens or tokens[-1].kind != "NEWLINE":
        add("NEWLINE", None, Pos(line, col))
    add("EOF", None, Pos(line, col))
    return tokens


def lex_string(text, i, line, col):
    """Lê um texto "..." com interpolação: "Volume {v}%" vira ["Volume ", (código, pos), "%"].

    Devolve (partes, índice depois do texto, linha, coluna). Cada pedaço de código interpolado
    guarda o texto e a posição dele, e o parser lê-o depois como uma expressão.
    """
    start = Pos(line, col)
    parts = []
    buf = []
    i += 1
    col += 1
    n = len(text)
    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "{": "{", "}": "}", "0": "\0"}
    while True:
        if i >= n or text[i] == "\n":
            raise GvtError(start, "texto sem as aspas que o fecham", 'feche o texto com " na mesma linha')
        c = text[i]
        if c == '"':
            i += 1
            col += 1
            break
        if c == "\\":
            if i + 1 < n and text[i + 1] in escapes:
                buf.append(escapes[text[i + 1]])
                i += 2
                col += 2
                continue
            raise GvtError(Pos(line, col), f"escape desconhecido: '\\{text[i + 1] if i + 1 < n else ''}'",
                           "os escapes são \\n, \\t, \\\", \\\\, \\{ e \\}")
        if c == "{":
            if text.startswith("{{", i):
                buf.append("{")
                i += 2
                col += 2
                continue
            if buf:
                parts.append("".join(buf))
                buf = []
            code_pos = Pos(line, col + 1)
            depth = 1
            j = i + 1
            while j < n and depth:
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                elif text[j] == "\n":
                    raise GvtError(code_pos, "interpolação { } sem fecho")
                j += 1
            if depth:
                raise GvtError(code_pos, "interpolação { } sem fecho")
            parts.append((text[i + 1 : j - 1], code_pos))
            col += j - i
            i = j
            continue
        if c == "}" and text.startswith("}}", i):
            buf.append("}")
            i += 2
            col += 2
            continue
        buf.append(c)
        i += 1
        col += 1
    if buf or not parts:
        parts.append("".join(buf))
    return parts, i, line, col
