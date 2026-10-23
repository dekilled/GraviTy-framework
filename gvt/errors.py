"""Erros e avisos do compilador, sempre apontando a linha do .gvt."""


class Pos:
    __slots__ = ("line", "col")

    def __init__(self, line, col):
        self.line = line
        self.col = col

    def __repr__(self):
        return f"{self.line}:{self.col}"


class GvtError(Exception):
    """Um erro no código .gvt. A mensagem é em português e diz o que fazer."""

    def __init__(self, pos, message, hint=None):
        super().__init__(message)
        self.pos = pos
        self.message = message
        self.hint = hint


class Source:
    """O texto de um arquivo .gvt, para mostrar a linha do erro com o ^ embaixo."""

    def __init__(self, path, text):
        self.path = path
        self.text = text
        self.lines = text.split("\n")

    def format(self, pos, kind, message, hint=None):
        out = [f"{self.path}:{pos.line}:{pos.col}: {kind}: {message}"]
        if 1 <= pos.line <= len(self.lines):
            line = self.lines[pos.line - 1].replace("\t", "    ")
            raw = self.lines[pos.line - 1]
            col = len(raw[: pos.col - 1].replace("\t", "    ")) + 1
            out.append(f"  {pos.line:4} | {line}")
            out.append(f"       | {' ' * (col - 1)}^")
        if hint:
            out.append(f"  dica: {hint}")
        return "\n".join(out)
