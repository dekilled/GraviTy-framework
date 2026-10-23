"""Lê os tokens e monta a árvore do programa (gvt/syntax.py)."""

import re

from . import syntax as S
from .errors import GvtError
from .lexer import KEYWORDS, tokenize

ELEMENTS = {
    "row", "column", "box", "card", "text", "icon", "button", "round_button", "slider", "toggle",
    "separator", "spacer",
}

TYPE_NAMES = {"int", "float", "bool", "string", "color"}

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}

# precedência dos operadores binários (maior = mais forte)
BINARY = {
    "or": 1, "||": 1,
    "and": 2, "&&": 2,
    "==": 3, "!=": 3,
    "<": 4, ">": 4, "<=": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
}
NORMALIZE = {"||": "or", "&&": "and"}


def describe(tok):
    if tok.kind == "NEWLINE":
        return "o fim da linha"
    if tok.kind == "EOF":
        return "o fim do arquivo"
    if tok.kind == "STRING":
        return "um texto"
    if tok.kind in ("INT", "FLOAT"):
        return f"o número {tok.value}"
    if tok.kind == "NAME":
        return f"'{tok.value}'"
    return f"'{tok.kind}'"


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    # ---- utilidades ----

    @property
    def tok(self):
        return self.toks[self.i]

    def peek(self, k=1):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, *kinds):
        return self.tok.kind in kinds

    def next(self):
        t = self.toks[self.i]
        if self.i < len(self.toks) - 1:
            self.i += 1
        return t

    def accept(self, kind):
        if self.tok.kind == kind:
            return self.next()
        return None

    def expect(self, kind, what=None, hint=None):
        if self.tok.kind != kind:
            prev = self.toks[self.i - 1] if self.i else None
            if prev and self.tok.pos.line > prev.pos.line and kind in (")", "]", "}"):
                # o que falta é no fim da linha de cima, não onde o parser tropeçou
                raise GvtError(prev.end, f"falta o '{kind}' aqui", hint)
            raise GvtError(self.tok.pos, f"esperava {what or repr(kind)}, mas veio {describe(self.tok)}", hint)
        return self.next()

    def expect_name(self, what="um nome"):
        if self.tok.kind != "NAME":
            hint = None
            if self.tok.kind in ("app", "fn", "var", "let", "if", "else", "for", "in", "while", "return",
                                 "break", "continue", "true", "false", "and", "or", "not", "view"):
                hint = f"'{self.tok.kind}' é uma palavra reservada da linguagem; escolha outro nome"
            raise GvtError(self.tok.pos, f"esperava {what}, mas veio {describe(self.tok)}", hint)
        return self.next()

    def skip_newlines(self):
        while self.tok.kind in ("NEWLINE", ";"):
            self.next()

    def end_statement(self):
        if self.at("NEWLINE", ";"):
            self.skip_newlines()
        elif not self.at("}", "EOF"):
            raise GvtError(self.tok.pos, f"esperava o fim do comando, mas veio {describe(self.tok)}",
                           "cada comando fica na sua linha (ou separe com ;)")

    # ---- o arquivo ----

    def program(self):
        pos = self.tok.pos
        decls = []
        app = None
        self.skip_newlines()
        while not self.at("EOF"):
            if self.at("app"):
                if app:
                    raise GvtError(self.tok.pos, "só pode haver um app por arquivo")
                app = self.app(decls)
            elif self.at("fn"):
                decls.append(self.fn())
            elif self.at("var", "let"):
                decls.append(self.var_decl())
            else:
                raise GvtError(self.tok.pos, f"no topo do arquivo esperava app, fn, var ou let, mas veio {describe(self.tok)}")
            self.skip_newlines()
        return S.make(S.Program, pos, decls=decls, app=app)

    def app(self, decls):
        pos = self.next().pos
        name = self.expect_name("o nome do app").value
        self.expect("{", "'{' depois do nome do app")
        props, events, view = [], [], None
        self.skip_newlines()
        while not self.at("}"):
            if self.at("EOF"):
                raise GvtError(pos, "o app não tem o '}' que o fecha")
            if self.at("var", "let"):
                decls.append(self.var_decl())
            elif self.at("fn"):
                decls.append(self.fn())
            elif self.at("view"):
                if view:
                    raise GvtError(self.tok.pos, "o app já tem um view")
                vpos = self.next().pos
                args = self.args() if self.at("(") else []
                body, evs = self.element_body()
                view = S.make(S.Element, vpos, kind="view", id=None, args=args, body=body, events=evs)
            elif self.at("NAME") and self.tok.value.startswith("on_") and self.peek().kind == "{":
                epos = self.tok.pos
                ename = self.next().value
                events.append(S.make(S.Event, epos, name=ename, body=self.block()))
            elif self.at("NAME") and self.peek().kind == ":":
                ppos = self.tok.pos
                pname = self.next().value
                self.next()
                value = self.expr()
                value2 = None
                if pname == "size":
                    if not (self.at("NAME") and self.tok.value == "x"):
                        raise GvtError(self.tok.pos, "size é largura x altura", "exemplo: size: 360 x 520")
                    self.next()
                    value2 = self.expr()
                props.append(S.make(S.AppProp, ppos, name=pname, value=value, value2=value2))
            else:
                raise GvtError(self.tok.pos, f"dentro do app esperava uma propriedade (title: ...), var, let, fn, view ou on_..., mas veio {describe(self.tok)}")
            self.end_statement()
        self.next()
        if not view:
            raise GvtError(pos, f"o app {name} não tem view", "acrescente view { ... } com o que vai na tela")
        return S.make(S.App, pos, name=name, props=props, view=view, events=events)

    def type_ref(self):
        pos = self.tok.pos
        if self.accept("["):
            item = self.type_ref()
            self.expect("]", "']' no fim do tipo da lista")
            return S.make(S.TypeRef, pos, name="list", item=item)
        t = self.expect_name("um tipo (int, float, bool, string, color ou [tipo])")
        if t.value not in TYPE_NAMES:
            raise GvtError(t.pos, f"tipo desconhecido: '{t.value}'", "os tipos são int, float, bool, string, color e [tipo]")
        return S.make(S.TypeRef, pos, name=t.value, item=None)

    def fn(self):
        pos = self.next().pos
        name = self.expect_name("o nome da função").value
        self.expect("(", "'(' depois do nome da função")
        params = []
        while not self.at(")"):
            ppos = self.tok.pos
            pname = self.expect_name("o nome de um parâmetro").value
            self.expect(":", "':' e o tipo do parâmetro", f"exemplo: fn {name}({pname}: float)")
            params.append(S.make(S.Param, ppos, name=pname, type=self.type_ref()))
            if not self.accept(","):
                break
        self.expect(")", "')' no fim dos parâmetros")
        ret = None
        if self.accept("->"):
            ret = self.type_ref()
        body = self.block()
        return S.make(S.FnDecl, pos, name=name, params=params, ret=ret, body=body)

    # ---- comandos ----

    def block(self):
        self.expect("{", "'{'")
        self.skip_newlines()
        stmts = []
        while not self.at("}"):
            if self.at("EOF"):
                raise GvtError(self.tok.pos, "falta um '}' para fechar o bloco")
            stmts.append(self.statement())
            self.end_statement()
        self.next()
        return stmts

    def element_body(self):
        """O corpo de um elemento: filhos e eventos (on_tap { ... })."""
        if not self.at("{"):
            return [], []
        self.next()
        self.skip_newlines()
        body, events = [], []
        while not self.at("}"):
            if self.at("EOF"):
                raise GvtError(self.tok.pos, "falta um '}' para fechar o elemento")
            if self.at("NAME") and self.tok.value.startswith("on_") and self.peek().kind == "{":
                epos = self.tok.pos
                ename = self.next().value
                events.append(S.make(S.Event, epos, name=ename, body=self.block()))
            else:
                body.append(self.statement())
            self.end_statement()
        self.next()
        return body, events

    def statement(self):
        t = self.tok
        if t.kind in ("var", "let"):
            return self.var_decl()
        if t.kind == "if":
            return self.if_stmt()
        if t.kind == "for":
            return self.for_stmt()
        if t.kind == "while":
            pos = self.next().pos
            cond = self.expr()
            return S.make(S.While, pos, cond=cond, body=self.block())
        if t.kind == "return":
            pos = self.next().pos
            value = None if self.at("NEWLINE", ";", "}") else self.expr()
            return S.make(S.Return, pos, value=value)
        if t.kind == "break":
            return S.make(S.Break, self.next().pos)
        if t.kind == "continue":
            return S.make(S.Continue, self.next().pos)
        if t.kind == "NAME" and t.value in ELEMENTS and self.peek().kind in ("#", "(", "{", "NEWLINE", ";", "}"):
            return self.element()
        if t.kind == "NAME" and t.value.startswith("on_") and self.peek().kind == "{":
            raise GvtError(t.pos, f"{t.value} só pode ficar dentro de um elemento (ou no app)")
        pos = t.pos
        e = self.expr()
        if self.tok.kind in ASSIGN_OPS:
            op = self.next().kind
            if not isinstance(e, (S.Name, S.Member, S.Index)):
                raise GvtError(pos, "só dá para atribuir a uma variável, um campo ou um item de lista")
            return S.make(S.Assign, pos, target=e, op=op, value=self.expr())
        return S.make(S.ExprStmt, pos, expr=e)

    def var_decl(self):
        t = self.next()
        name = self.expect_name("o nome da variável").value
        type_ = None
        if self.accept(":"):
            type_ = self.type_ref()
        self.expect("=", "'=' e o valor inicial", f"exemplo: {t.kind} {name} = 0")
        return S.make(S.VarDecl, t.pos, mutable=t.kind == "var", name=name, type=type_, value=self.expr())

    def if_stmt(self):
        pos = self.next().pos
        cond = self.expr()
        then = self.block()
        other = None
        save = self.i
        while self.at("NEWLINE"):
            self.next()
        if self.at("else"):
            self.next()
            if self.at("if"):
                other = [self.if_stmt()]
            else:
                other = self.block()
        else:
            self.i = save
        return S.make(S.If, pos, cond=cond, then=then, other=other)

    def for_stmt(self):
        pos = self.next().pos
        first = self.expect_name("o nome da variável do for").value
        index, item = None, first
        if self.accept(","):
            index = first
            item = self.expect_name("o nome do item").value
        self.expect("in", "'in'", "exemplo: for item in lista { ... } ou for i in 0..10 { ... }")
        start = self.expr()
        if self.at("..", "..="):
            inclusive = self.next().kind == "..="
            end = self.expr()
            if index:
                raise GvtError(pos, "num intervalo só há uma variável", "exemplo: for i in 0..10 { ... }")
            iterable = S.make(S.Range, start.pos, start=start, end=end, inclusive=inclusive)
        else:
            iterable = start
        return S.make(S.For, pos, index=index, item=item, iterable=iterable, body=self.block())

    def element(self):
        t = self.next()
        id_ = None
        if self.at("#"):
            id_ = self.id_ref()
        args = self.args() if self.at("(") else []
        body, events = self.element_body()
        return S.make(S.Element, t.pos, kind=t.value, id=id_, args=args, body=body, events=events)

    def id_ref(self):
        pos = self.expect("#").pos
        # depois de # qualquer palavra serve de nome, mesmo as reservadas: #app, #view...
        if self.tok.kind in KEYWORDS:
            name = self.next().value
        else:
            name = self.expect_name("o nome do id depois de #").value
        index = None
        if self.accept("["):
            index = self.expr()
            self.expect("]", "']'")
        return S.make(S.IdRef, pos, name=name, index=index)

    def args(self):
        self.expect("(")
        out = []
        while not self.at(")"):
            pos = self.tok.pos
            if self.at("NAME") and self.peek().kind == ":":
                name = self.next().value
                self.next()
                out.append(S.make(S.Arg, pos, name=name, value=self.expr()))
            else:
                out.append(S.make(S.Arg, pos, name=None, value=self.expr()))
            if not self.accept(","):
                break
        self.expect(")", "')' ou ',' entre os argumentos")
        return out

    # ---- expressões ----

    def expr(self):
        cond = self.binary(1)
        if self.at("?"):
            pos = self.next().pos
            then = self.expr()
            self.expect(":", "':' na expressão condição ? sim : não")
            other = self.expr()
            return S.make(S.Ternary, pos, cond=cond, then=then, other=other)
        return cond

    def binary(self, level):
        left = self.unary()
        while self.tok.kind in BINARY and BINARY[self.tok.kind] >= level:
            t = self.next()
            prec = BINARY[t.kind]
            right = self.binary(prec + 1)
            left = S.make(S.Binary, t.pos, op=NORMALIZE.get(t.kind, t.kind), left=left, right=right)
        return left

    def unary(self):
        if self.at("!", "not"):
            pos = self.next().pos
            return S.make(S.Unary, pos, op="not", expr=self.unary())
        if self.at("-"):
            pos = self.next().pos
            return S.make(S.Unary, pos, op="-", expr=self.unary())
        return self.postfix(self.primary())

    def postfix(self, e):
        while True:
            if self.at("("):
                pos = self.tok.pos
                e = S.make(S.Call, pos, func=e, args=self.args())
            elif self.at("["):
                pos = self.next().pos
                idx = self.expr()
                self.expect("]", "']'")
                e = S.make(S.Index, pos, obj=e, index=idx)
            elif self.at("."):
                pos = self.next().pos
                field = self.expect_name("o nome do campo depois de '.'").value
                e = S.make(S.Member, pos, obj=e, field=field)
            else:
                return e

    def primary(self):
        t = self.tok
        if t.kind == "INT":
            self.next()
            return S.make(S.Num, t.pos, value=t.value, is_float=False)
        if t.kind == "FLOAT":
            self.next()
            return S.make(S.Num, t.pos, value=t.value, is_float=True)
        if t.kind == "STRING":
            self.next()
            parts = []
            for p in t.value:
                if isinstance(p, tuple):
                    code, cpos = p
                    # {valor:.1} mostra uma casa decimal
                    m = re.match(r"^(.*?):\s*\.(\d+)\s*$", code, re.S)
                    if m:
                        parts.append((parse_inner(m.group(1), cpos), int(m.group(2))))
                    else:
                        parts.append((parse_inner(code, cpos), None))
                else:
                    parts.append(p)
            return S.make(S.Str, t.pos, parts=parts)
        if t.kind in ("true", "false"):
            self.next()
            return S.make(S.Bool, t.pos, value=t.kind == "true")
        if t.kind == "NAME":
            self.next()
            return S.make(S.Name, t.pos, name=t.value)
        if t.kind == "#":
            return self.id_ref()
        if t.kind == "(":
            self.next()
            e = self.expr()
            self.expect(")", "')'")
            return e
        if t.kind == "[":
            self.next()
            items = []
            while not self.at("]"):
                items.append(self.expr())
                if not self.accept(","):
                    break
            self.expect("]", "']' ou ',' entre os itens")
            return S.make(S.ListLit, t.pos, items=items)
        if t.kind == "{":
            self.next()
            self.skip_newlines()
            fields = []
            while not self.at("}"):
                fname = self.expect_name("o nome de um campo").value
                self.expect(":", "':' depois do nome do campo")
                fields.append((fname, self.expr()))
                self.skip_newlines()
                if not self.accept(","):
                    self.skip_newlines()
                    break
                self.skip_newlines()
            self.expect("}", "'}' ou ',' entre os campos")
            return S.make(S.RecordLit, t.pos, fields=fields)
        raise GvtError(t.pos, f"esperava um valor, mas veio {describe(t)}")


def parse_inner(code, pos):
    """Uma expressão de dentro de um texto: "Volume {pct(v)}%"."""
    from .errors import Pos
    toks = tokenize(code)
    # corrige as posições: o código começa em pos, na mesma linha
    for tk in toks:
        tk.pos = Pos(pos.line, pos.col + tk.pos.col - 1)
    p = Parser(toks)
    p.skip_newlines()
    if p.at("EOF"):
        raise GvtError(pos, "interpolação vazia: { }", "para um { literal escreva {{ ou \\{")
    e = p.expr()
    p.skip_newlines()
    if not p.at("EOF"):
        raise GvtError(p.tok.pos, f"sobrou {describe(p.tok)} na interpolação")
    return e


def parse(text):
    return Parser(tokenize(text)).program()
