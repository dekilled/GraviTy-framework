"""A árvore do programa: o que o parser lê e o compilador percorre."""


class Node:
    __slots__ = ("pos",)

    def __repr__(self):
        fields = ", ".join(f"{k}={getattr(self, k)!r}" for k in self.__slots__ if k != "pos")
        return f"{type(self).__name__}({fields})"


# ---- expressões ----

class Num(Node):
    __slots__ = ("value", "is_float")


class Str(Node):
    __slots__ = ("parts",)  # textos e (expressão, casas decimais ou None) da interpolação


class Bool(Node):
    __slots__ = ("value",)


class Name(Node):
    __slots__ = ("name",)


class IdRef(Node):
    """#nome ou #nome[índice]: o id de um elemento."""
    __slots__ = ("name", "index")


class Member(Node):
    __slots__ = ("obj", "field")


class Index(Node):
    __slots__ = ("obj", "index")


class Arg(Node):
    __slots__ = ("name", "value")  # name é None num argumento posicional


class Call(Node):
    __slots__ = ("func", "args")


class Unary(Node):
    __slots__ = ("op", "expr")


class Binary(Node):
    __slots__ = ("op", "left", "right")


class Ternary(Node):
    __slots__ = ("cond", "then", "other")


class ListLit(Node):
    __slots__ = ("items",)


class RecordLit(Node):
    __slots__ = ("fields",)  # [(nome, expr)]


# ---- tipos escritos à mão: var x: float = 1 ----

class TypeRef(Node):
    __slots__ = ("name", "item")  # name: int/float/bool/string/color/list; item: o TypeRef da lista


# ---- comandos ----

class VarDecl(Node):
    __slots__ = ("mutable", "name", "type", "value")


class Assign(Node):
    __slots__ = ("target", "op", "value")


class If(Node):
    __slots__ = ("cond", "then", "other")  # other: lista de comandos, ou None


class Range(Node):
    __slots__ = ("start", "end", "inclusive")


class For(Node):
    __slots__ = ("index", "item", "iterable", "body")


class While(Node):
    __slots__ = ("cond", "body")


class Return(Node):
    __slots__ = ("value",)


class Break(Node):
    __slots__ = ()


class Continue(Node):
    __slots__ = ()


class ExprStmt(Node):
    __slots__ = ("expr",)


class Event(Node):
    """on_tap { ... }, on_change { ... }: o que corre quando algo acontece."""
    __slots__ = ("name", "body")


class Element(Node):
    """row #id (props) { filhos }"""
    __slots__ = ("kind", "id", "args", "body", "events")


# ---- o arquivo ----

class Param(Node):
    __slots__ = ("name", "type")


class FnDecl(Node):
    __slots__ = ("name", "params", "ret", "body")


class AppProp(Node):
    __slots__ = ("name", "value", "value2")  # value2: a altura em size: L x A


class App(Node):
    __slots__ = ("name", "props", "view", "events")  # view é um Element; events: on_start, on_key


class Program(Node):
    __slots__ = ("decls", "app")  # decls: VarDecl e FnDecl, na ordem do arquivo


def make(cls, pos, **kw):
    node = cls.__new__(cls)
    node.pos = pos
    for slot in cls.__slots__:
        setattr(node, slot, kw.get(slot))
    return node
