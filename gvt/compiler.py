"""Compila a árvore de um .gvt em C para o Gravity.

O C gerado é o mesmo que se escreveria à mão: CLAY(...) { ... } com os componentes gv_*, o estado
numa struct estática e uma função de desenho. Não há interpretador nem nada rodando por baixo:
o gcc/clang compila direto para código de máquina.

Checagem de tipos e geração andam juntas: cada expressão compilada retorna (código C, tipo).
"""

import difflib
import os

from . import syntax as S
from .errors import GvtError
from .parser import ELEMENTS


# ---- tipos ----

class Type:
    __slots__ = ("kind", "item", "size", "rec", "enum")

    def __init__(self, kind, item=None, size=None, rec=None, enum=None):
        self.kind = kind    # int float bool string color key id void list record enum
        self.item = item    # list: o tipo dos itens
        self.size = size    # list: quantos itens
        self.rec = rec      # record: a RecordDef
        self.enum = enum    # enum: (nome, {palavra: código C})

    def __eq__(self, other):
        if not isinstance(other, Type) or self.kind != other.kind:
            return False
        if self.kind == "list":
            return self.item == other.item and self.size == other.size
        if self.kind == "record":
            return self.rec is other.rec
        if self.kind == "enum":
            return self.enum[0] == other.enum[0]
        return True

    def __hash__(self):
        return hash(self.kind)

    @property
    def numeric(self):
        return self.kind in ("int", "float", "number")

    def describe(self):
        if self.kind == "list":
            return f"[{self.item.describe()}] com {self.size} itens"
        if self.kind == "record":
            return f"registro {{{', '.join(n for n, _ in self.rec.fields)}}}"
        if self.kind == "enum":
            return f"uma destas palavras: {', '.join(self.enum[1])}"
        return {"key": "tecla", "id": "#id", "void": "nada", "number": "um número"}.get(self.kind, self.kind)


INT, FLOAT, BOOL, STRING, COLOR = Type("int"), Type("float"), Type("bool"), Type("string"), Type("color")
KEY, ID, VOID = Type("key"), Type("id"), Type("void")
NUMBER = Type("number")  # int ou float, como vier: as medidas do layout (gap: 16, width: 40.5)

C_TYPES = {"int": "int", "float": "float", "bool": "bool", "color": "Clay_Color", "key": "uint32_t", "id": "Clay_ElementId"}


class RecordDef:
    def __init__(self, cname, fields):
        self.cname = cname    # struct apps_item
        self.fields = fields  # [(nome, Type)]

    def field(self, name):
        for n, t in self.fields:
            if n == name:
                return t
        return None


def c_decl(t, name):
    """A declaração C de uma variável do tipo t: float x, const char *nome, struct a b[3]..."""
    if t.kind == "list":
        return c_decl(t.item, f"{name}[{t.size}]")
    if t.kind == "string":
        return f"const char *{name}"
    if t.kind == "record":
        return f"struct {t.rec.cname} {name}"
    return f"{C_TYPES[t.kind]} {name}"


def enum(name, mapping):
    return Type("enum", enum=(name, mapping))


WEIGHT = enum("peso", {"normal": "GV_PESO_NORMAL", "medium": "GV_PESO_MEDIO", "semibold": "GV_PESO_SEMINEGRITO", "bold": "GV_PESO_NEGRITO"})
TEXT_STYLE = enum("estilo do texto", {"caption": "gv_t.tamanho_legenda", "body": "gv_t.tamanho_corpo",
                                      "highlight": "gv_t.tamanho_destaque", "title": "gv_t.tamanho_titulo"})
BUTTON_STYLE = enum("estilo do botão", {"filled": "GV_BOTAO_CHEIO", "outline": "GV_BOTAO_CONTORNO", "plain": "GV_BOTAO_SIMPLES"})
CURVE = enum("curva", {"smooth": "GV_CURVA_SUAVE", "spring": "GV_CURVA_MOLA", "linear": "GV_CURVA_LINEAR"})
KIND = enum("tipo de app", {"window": "GV_JANELA", "layer": "GV_CAMADA"})
LEVEL = enum("nível da camada", {"background": "GV_NIVEL_FUNDO", "bottom": "GV_NIVEL_BAIXO", "top": "GV_NIVEL_CIMA", "overlay": "GV_NIVEL_OVERLAY"})
DURATION = enum("duração", {"fast": "gv_t.duracao_rapida", "normal": "gv_t.duracao_normal", "slow": "gv_t.duracao_lenta"})
ALIGN_X = enum("alinhamento", {"start": "CLAY_ALIGN_X_LEFT", "left": "CLAY_ALIGN_X_LEFT", "center": "CLAY_ALIGN_X_CENTER",
                               "end": "CLAY_ALIGN_X_RIGHT", "right": "CLAY_ALIGN_X_RIGHT"})
ALIGN_Y = enum("alinhamento", {"start": "CLAY_ALIGN_Y_TOP", "top": "CLAY_ALIGN_Y_TOP", "center": "CLAY_ALIGN_Y_CENTER",
                               "end": "CLAY_ALIGN_Y_BOTTOM", "bottom": "CLAY_ALIGN_Y_BOTTOM"})

# onde um elemento flutuante se prende ao pai: (ponto do elemento, ponto do pai)
FLOAT_POINTS = {
    "below": ("CENTER_TOP", "CENTER_BOTTOM"), "below_left": ("LEFT_TOP", "LEFT_BOTTOM"),
    "below_right": ("RIGHT_TOP", "RIGHT_BOTTOM"), "above": ("CENTER_BOTTOM", "CENTER_TOP"),
    "above_left": ("LEFT_BOTTOM", "LEFT_TOP"), "above_right": ("RIGHT_BOTTOM", "RIGHT_TOP"),
    "left": ("RIGHT_CENTER", "LEFT_CENTER"), "right": ("LEFT_CENTER", "RIGHT_CENTER"),
    "center": ("CENTER_CENTER", "CENTER_CENTER"),
    "top_left": ("LEFT_TOP", "LEFT_TOP"), "top_right": ("RIGHT_TOP", "RIGHT_TOP"),
    "bottom_left": ("LEFT_BOTTOM", "LEFT_BOTTOM"), "bottom_right": ("RIGHT_BOTTOM", "RIGHT_BOTTOM"),
}

# o tema: nome em inglês -> (campo do gv_tema, tipo)
THEME = {
    "background": ("fundo", COLOR), "surface": ("superficie", COLOR), "surface_high": ("superficie_alta", COLOR),
    "text": ("texto", COLOR), "muted": ("texto_suave", COLOR), "faint": ("texto_fraco", COLOR),
    "accent": ("acento", COLOR), "accent_strong": ("acento_forte", COLOR), "icon": ("icone", COLOR),
    "line": ("linha", COLOR), "danger": ("perigo", COLOR), "knob": ("puxador", COLOR),
    "radius_small": ("raio_pequeno", FLOAT), "radius_medium": ("raio_medio", FLOAT), "radius_large": ("raio_grande", FLOAT),
    "spacing": ("espaco", FLOAT), "icon_stroke": ("traco_icone", FLOAT),
    "size_caption": ("tamanho_legenda", FLOAT), "size_body": ("tamanho_corpo", FLOAT),
    "size_highlight": ("tamanho_destaque", FLOAT), "size_title": ("tamanho_titulo", FLOAT),
    "duration_fast": ("duracao_rapida", INT), "duration_normal": ("duracao_normal", INT), "duration_slow": ("duracao_lenta", INT),
    "curve": ("curva", CURVE), "animations": ("animacoes", BOOL), "font": ("fonte", STRING),
}
NAMED_COLORS = {"white": "((Clay_Color){ 255, 255, 255, 255 })", "black": "((Clay_Color){ 0, 0, 0, 255 })",
                "transparent": "((Clay_Color){ 0, 0, 0, 0 })"}

C_KEYWORDS = {
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern",
    "float", "for", "goto", "if", "inline", "int", "long", "register", "restrict", "return", "short", "signed",
    "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while", "bool",
    "true", "false", "NULL", "main", "s", "app", "dados", "key", "value",
}

BUILTINS = {
    "round", "floor", "ceil", "abs", "min", "max", "clamp", "sqrt", "sin", "cos", "pow", "int", "float",
    "len", "alpha", "rgb", "animate", "hovered", "pressed", "tapped", "now", "width", "height", "has_arg",
    "print", "quit", "redraw", "load_theme", "grow", "fit", "percent",
}

CONTAINER_PROPS = {
    "width", "height", "padding", "padding_x", "padding_y", "padding_top", "padding_right", "padding_bottom",
    "padding_left", "gap", "align", "justify", "bg", "background", "radius", "border", "border_color", "border_top",
    "border_right", "border_bottom", "border_left", "float", "offset", "z", "shadow", "scroll", "direction",
}
CONTAINER_FLAGS = {"grow", "fill", "center", "clip"}


def spec(pos=(), flags=(), props=(), events=(), children=False):
    return {"pos": list(pos), "flags": set(flags), "props": set(props) | set(pos), "events": set(events), "children": children}


# as propriedades do button que viram gv_botao_opcoes: nome -> (campo, tipo)
BUTTON_OPTIONS = {
    "icon_size": ("tamanho_icone", "number"), "text_size": ("tamanho_texto", "number"), "weight": ("peso", "weight"),
    "width": ("largura", "sizing"), "height": ("altura", "number"), "padding_x": ("margem", "number"),
    "gap": ("espaco", "number"), "radius": ("raio", "number"), "bg": ("fundo", "color"),
    "color": ("conteudo", "color"), "border_color": ("borda", "color"),
}

# entrar/sair e apertar/soltar: o GraviTy lembra o estado do quadro anterior e avisa quando muda
POINTER_EVENTS = {"on_hover", "on_leave", "on_press", "on_release"}
TAP_EVENTS = {"on_tap"} | POINTER_EVENTS
CHANGE_EVENTS = {"on_change"} | POINTER_EVENTS

# nomes de outros lugares (o DOM, outros frameworks) e o que usar no GraviTy
EVENT_HINTS = {
    "on_mouseover": "on_hover", "on_mouseenter": "on_hover", "on_enter": "on_hover",
    "on_mouseout": "on_leave", "on_mouseleave": "on_leave", "on_exit": "on_leave",
    "on_click": "on_tap", "on_touch": "on_tap",
    "on_mousedown": "on_press", "on_down": "on_press", "on_touchstart": "on_press",
    "on_mouseup": "on_release", "on_up": "on_release", "on_touchend": "on_release",
}

SPECS = {
    "view": spec(flags=CONTAINER_FLAGS, props=CONTAINER_PROPS, events=TAP_EVENTS, children=True),
    "row": spec(flags=CONTAINER_FLAGS, props=CONTAINER_PROPS, events=TAP_EVENTS, children=True),
    "column": spec(flags=CONTAINER_FLAGS, props=CONTAINER_PROPS, events=TAP_EVENTS, children=True),
    "box": spec(flags=CONTAINER_FLAGS, props=CONTAINER_PROPS, events=TAP_EVENTS, children=True),
    "card": spec(flags=CONTAINER_FLAGS, props=CONTAINER_PROPS, events=TAP_EVENTS, children=True),
    "text": spec(pos=["text"], flags=CONTAINER_FLAGS, props={"size", "style", "color", "weight"} | CONTAINER_PROPS, events=TAP_EVENTS),
    "icon": spec(pos=["name", "size"], props={"color"}),
    "button": spec(pos=["text"], props={"icon", "style"} | set(BUTTON_OPTIONS), events=TAP_EVENTS),
    "round_button": spec(pos=["icon"], props={"size", "on", "danger"}, events=TAP_EVENTS),
    "slider": spec(pos=["value"], props={"track", "knob"}, events=CHANGE_EVENTS),
    "toggle": spec(pos=["value"], events=CHANGE_EVENTS),
    "separator": spec(pos=["length"], flags={"vertical", "horizontal"}),
    "spacer": spec(pos=["size"]),
}

APP_PROPS = {"title", "id", "size", "kind", "layer", "anchors", "exclusive", "keyboard", "theme"}
APP_EVENTS = {"on_start", "on_key", "on_frame"}


def suggest(name, options):
    close = difflib.get_close_matches(name, sorted(options), n=1, cutoff=0.6)
    return f"você quis dizer '{close[0]}'?" if close else None


def c_string(text):
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\0":
            out.append("\\0")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def c_float(v):
    r = repr(float(v))
    if "e" not in r and "." not in r:
        r += ".0"
    return r + "f"


def hex_color(text):
    """'#a78bfa' ou '#a78bfa80' -> (r, g, b, a), ou None se não for uma cor."""
    if len(text) in (7, 9) and text[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in text[1:]):
        v = [int(text[i : i + 2], 16) for i in range(1, len(text), 2)]
        return tuple(v) if len(v) == 4 else (*v, 255)
    return None


def literal_text(e):
    """O texto de um "literal" sem interpolação, ou None."""
    if isinstance(e, S.Str) and all(isinstance(p, str) for p in e.parts):
        return "".join(e.parts)
    return None


# ---- contexto ----

class Symbol:
    __slots__ = ("cname", "type", "mutable", "ptr", "used", "pos", "name")

    def __init__(self, cname, type_, mutable, ptr=False):
        self.cname = cname
        self.type = type_
        self.mutable = mutable
        self.ptr = ptr     # um item de lista por ponteiro: campos com ->
        self.used = False  # para avisar de variáveis que ninguém usa
        self.pos = None
        self.name = None


class FnInfo:
    def __init__(self, decl, cname, params, ret):
        self.decl = decl
        self.cname = cname
        self.params = params  # [(nome, Type)]
        self.ret = ret        # Type (VOID se não retorna nada)

    @property
    def draws(self):
        return self.ret.kind == "void"


class Elem:
    """O elemento a ser compilado: para hovered e pressed saberem de quem falam."""

    def __init__(self, idvar, direction):
        self.idvar = idvar
        self.direction = direction  # "row", "column" ou None
        self.used = False


def load_icons(gravity_dir):
    """Os nomes dos ícones do Gravity (src/gv_icones.c), ou None se não achar."""
    import re
    try:
        with open(os.path.join(gravity_dir, "src", "gv_icones.c"), encoding="utf-8") as f:
            return set(re.findall(r'\{\s*"([a-z0-9-]+)"', f.read()))
    except OSError:
        return None


class Compiler:
    def __init__(self, program, source_name="app.gvt", icons=None):
        self.program = program
        self.source_name = source_name
        self.icons = icons  # os ícones que existem, para avisar de nomes errados (None: não confere)
        self.warnings = []
        self.globals = {}       # nome -> Symbol
        self.state_fields = []  # declarações C da struct de estado
        self.state_init = []    # ".x = valor" para o que é constante
        self.late_init = []     # o que só dá para iniciar depois de criar o app (usa o tema, funções...)
        self.records = []       # definições de struct
        self.fns = {}           # nome -> FnInfo
        self.scopes = []
        self.frames = []        # "loop", "element", "event", "fn"
        self.loops = []         # o índice C de cada for aberto (para os ids dentro de listas)
        self.elems = []         # pilha de Elem
        self.fn = None          # a FnInfo a ser compilada, ou None no view/eventos
        self.event_depth = 0
        self.counter = 0
        self.helpers = set()
        self.needs_xkb = False
        self.record_names = set()

    # ---- utilidades ----

    def tmp(self, prefix):
        self.counter += 1
        return f"_{prefix}{self.counter}"

    def warn(self, pos, message, hint=None):
        self.warnings.append((pos, message, hint))

    def lookup(self, name, use=True):
        for scope in reversed(self.scopes):
            if name in scope:
                if use:
                    scope[name].used = True
                return scope[name]
        return self.globals.get(name)

    def declare(self, pos, name, type_, mutable, ptr=False):
        if name in self.scopes[-1]:
            raise GvtError(pos, f"'{name}' já foi declarado aqui")
        if name in ("theme", "hovered", "pressed") or name in ELEMENTS:
            raise GvtError(pos, f"'{name}' é um nome da linguagem; escolha outro")
        cname = name + "_" if name in C_KEYWORDS or name.startswith(("gv", "_", "CLAY", "Clay", "fn_")) else name
        sym = Symbol(cname, type_, mutable, ptr)
        sym.pos = pos
        sym.name = name
        self.scopes[-1][name] = sym
        return sym

    def seed(self):
        return "_seed" if self.fn else "0"

    def id_code(self, label, index=None):
        """O Clay_ElementId de um elemento: o rótulo, o índice nas listas abertas e a semente da fn."""
        lit = c_string(label)
        if index is not None:
            return f"GVT_ID({lit}, {index}, {self.seed()})"
        if not self.loops:
            return f"GVT_ID({lit}, 0, {self.seed()})"
        chain = self.seed()
        for idx in self.loops[:-1]:
            chain = f"GVT_ID({lit}, {idx}, {chain}).id"
        return f"GVT_ID({lit}, {self.loops[-1]}, {chain})"

    def check_not_in_element(self, pos, what):
        for f in reversed(self.frames):
            if f == "element":
                raise GvtError(pos, f"{what} não pode ficar dentro de um elemento",
                               "o Clay precisa de fechar cada elemento; mova a lógica para fora ou use if")
            if what == "return" and f == "fn":
                return
            if what != "return" and f == "loop":
                return

    # ---- coerção ----

    def coerce(self, code, have, want, pos, what="o valor"):
        if want is None or have == want:
            return code
        if want.kind == "float" and have.kind == "int":
            return code
        if want.kind == "number" and have.kind in ("int", "float"):
            return code
        hint = None
        if want.kind == "int" and have.kind == "float":
            hint = "arredonde com round(x), ou corte as casas com int(x)"
        elif want.kind == "bool" and have.numeric:
            hint = "compare: x > 0, x == 1..."
        elif want.kind == "bool" and have.kind == "string":
            hint = 'compare: nome == "algo"'
        elif want.kind == "string" and have.numeric:
            hint = 'use interpolação: "{x}"'
        raise GvtError(pos, f"{what} devia ser {want.describe()}, mas é {have.describe()}", hint)

    def unify(self, a, b, pos):
        if a == b:
            return a
        if a.numeric and b.numeric:
            return FLOAT
        if a.kind == "record" and b.kind == "record":
            return a
        raise GvtError(pos, f"os dois lados deviam ter o mesmo tipo, mas um é {a.describe()} e o outro {b.describe()}")

    # ---- expressões ----

    def expr(self, e, want=None, what="o valor"):
        code, t = self._expr(e, want)
        if want is not None and want.kind == "enum":
            if t != want:
                raise GvtError(e.pos, f"{what} devia ser {want.describe()}")
            return code, t
        code = self.coerce(code, t, want, e.pos, what)
        if want is not None and want.kind == "float" and t.kind == "int":
            t = FLOAT
        return code, t

    def _expr(self, e, want):
        m = getattr(self, "x_" + type(e).__name__)
        return m(e, want)

    def x_Num(self, e, want):
        if e.is_float or (want is not None and want.kind == "float"):
            return c_float(e.value), FLOAT
        return str(e.value), INT

    def x_Bool(self, e, want):
        return ("true" if e.value else "false"), BOOL

    def x_Str(self, e, want):
        text = literal_text(e)
        if text is not None:
            rgba = hex_color(text)
            if rgba and (want is None or want.kind == "color"):
                return "((Clay_Color){ %d, %d, %d, %d })" % rgba, COLOR
            return c_string(text), STRING
        fmt, args = self.format(e)
        return f"gv_fmt({', '.join([fmt] + args)}).chars", STRING

    def format(self, e, suffix=""):
        """Um texto com interpolação -> (formato do printf, argumentos)."""
        fmt, args = [], []
        for p in e.parts:
            if isinstance(p, str):
                fmt.append(p.replace("%", "%%"))
                continue
            sub, decimals = p
            code, t = self.expr(sub)
            if t.kind == "int":
                fmt.append("%d")
                args.append(code)
            elif t.kind == "float":
                fmt.append(f"%.{decimals}f" if decimals is not None else "%g")
                args.append(code)
            elif t.kind == "bool":
                fmt.append("%s")
                args.append(f'({code} ? "true" : "false")')
            elif t.kind == "string":
                fmt.append("%s")
                args.append(code)
            else:
                raise GvtError(sub.pos, f"não dá para pôr {t.describe()} num texto")
            if decimals is not None and t.kind != "float":
                raise GvtError(sub.pos, "as casas decimais (:.1) são só para float")
        return c_string("".join(fmt) + suffix), args

    def clay_string(self, e):
        """Um texto para o Clay (gv_texto): literal, formatado ou copiado para o quadro."""
        text = literal_text(e)
        if text is not None:
            return f"CLAY_STRING({c_string(text)})"
        if isinstance(e, S.Str):
            fmt, args = self.format(e)
            return f"gv_fmt({', '.join([fmt] + args)})"
        if isinstance(e, S.Ternary):
            cond, _ = self.expr(e.cond, BOOL, "a condição antes do ?")
            return f"{wrap(cond)} ? {self.clay_string(e.then)} : {self.clay_string(e.other)}"
        code, _ = self.expr(e, STRING, "o texto")
        return f"gv_str({code})"

    def x_Name(self, e, want):
        sym = self.lookup(e.name)
        if sym:
            code = f"(*{sym.cname})" if sym.ptr and sym.type.kind != "record" else sym.cname
            return code, sym.type
        if want is not None and want.kind == "enum" and e.name in want.enum[1]:
            return want.enum[1][e.name], want
        if want is not None and want.kind == "color":
            if e.name in THEME and THEME[e.name][1] == COLOR:
                return f"gv_t.{THEME[e.name][0]}", COLOR
            if e.name in NAMED_COLORS:
                return NAMED_COLORS[e.name], COLOR
        if e.name in ("hovered", "pressed"):
            el = self.current_elem(e.pos, e.name)
            return f"{'gv_por_cima' if e.name == 'hovered' else 'gv_premido'}({el.idvar})", BOOL
        if e.name == "theme":
            raise GvtError(e.pos, "use um campo do tema: theme.accent, theme.radius_large...")
        if e.name in self.fns:
            raise GvtError(e.pos, f"{e.name} é uma função: chame com ()", f"{e.name}()")
        options = set(self.globals) | {n for s in self.scopes for n in s}
        hint = suggest(e.name, options)
        if want is not None and want.kind == "enum":
            hint = f"aqui vale {', '.join(want.enum[1])}"
        elif want is not None and want.kind == "color":
            hint = hint or "uma cor é \"#rrggbb\", um nome do tema (accent, text, muted...) ou alpha(cor, 0.5)"
        raise GvtError(e.pos, f"nome desconhecido: '{e.name}'", hint)

    def current_elem(self, pos, what):
        if not self.elems:
            raise GvtError(pos, f"{what} sozinho só funciona dentro de um elemento", f"use {what}(#id) para outro elemento")
        el = self.elems[-1]
        el.used = True
        return el

    def x_IdRef(self, e, want):
        if e.index is not None:
            idx, _ = self.expr(e.index, INT, "o índice do id")
            return self.id_code(e.name, idx), ID
        return self.id_code(e.name), ID

    def x_Member(self, e, want):
        if isinstance(e.obj, S.Name) and e.obj.name == "theme" and not self.lookup("theme", use=False):
            if e.field not in THEME:
                raise GvtError(e.pos, f"o tema não tem '{e.field}'", suggest(e.field, THEME))
            field, t = THEME[e.field]
            return f"gv_t.{field}", t
        obj, t = self.expr(e.obj)
        if t.kind == "color":
            if e.field not in ("r", "g", "b", "a"):
                raise GvtError(e.pos, f"uma cor tem r, g, b e a (de 0 a 255), não '{e.field}'")
            return f"{obj}.{e.field}", FLOAT
        if t.kind != "record":
            raise GvtError(e.pos, f"só registros têm campos, e isto é {t.describe()}")
        ft = t.rec.field(e.field)
        if ft is None:
            raise GvtError(e.pos, f"o registro não tem o campo '{e.field}'", suggest(e.field, [n for n, _ in t.rec.fields]))
        arrow = isinstance(e.obj, S.Name) and self.lookup(e.obj.name, use=False) and self.lookup(e.obj.name, use=False).ptr
        return f"{obj}{'->' if arrow else '.'}{field_name(e.field)}", ft

    def x_Index(self, e, want):
        obj, t = self.expr(e.obj)
        if t.kind != "list":
            raise GvtError(e.pos, f"só listas têm itens [ ], e isto é {t.describe()}")
        idx, _ = self.expr(e.index, INT, "o índice")
        return f"{obj}[{idx}]", t.item

    def x_Unary(self, e, want):
        if e.op == "not":
            code, t = self.expr(e.expr, BOOL, "o valor do not")
            return f"!{wrap(code)}", BOOL
        code, t = self.expr(e.expr, want if want is not None and want.numeric else None)
        if not t.numeric:
            raise GvtError(e.pos, f"o sinal - é para números, e isto é {t.describe()}")
        return f"-{wrap(code)}", t

    def x_Binary(self, e, want):
        op = e.op
        if op in ("and", "or"):
            l, _ = self.expr(e.left, BOOL, f"o lado esquerdo do {op}")
            r, _ = self.expr(e.right, BOOL, f"o lado direito do {op}")
            return f"{wrap(l)} {'&&' if op == 'and' else '||'} {wrap(r)}", BOOL
        if op in ("==", "!="):
            return self.equality(e)
        sub_want = want if want is not None and want.numeric else None
        lc, lt = self.expr(e.left, sub_want)
        rc, rt = self.expr(e.right, sub_want)
        if lt.kind == "string" or rt.kind == "string":
            raise GvtError(e.pos, f"não dá para usar {op} com textos", 'para juntar textos use interpolação: "{a} {b}"')
        if not (lt.numeric and rt.numeric):
            raise GvtError(e.pos, f"{op} é para números, mas aqui há {lt.describe()} e {rt.describe()}")
        if op in ("<", ">", "<=", ">="):
            return f"{wrap(lc)} {op} {wrap(rc)}", BOOL
        t = FLOAT if FLOAT in (lt, rt) else INT
        if op == "/":
            # / divide sempre como números com vírgula (1 / 2 = 0.5); int(a / b) arredonda para baixo
            if t == INT:
                return f"(float){wrap(lc)} / {wrap(rc)}", FLOAT
            return f"{wrap(lc)} / {wrap(rc)}", FLOAT
        if op == "%" and t == FLOAT:
            return f"fmodf({lc}, {rc})", FLOAT
        return f"{wrap(lc)} {op} {wrap(rc)}", t

    def equality(self, e):
        op = e.op
        lc, lt = self.expr(e.left)
        if lt.kind == "key":
            text = literal_text(e.right)
            if text is None:
                raise GvtError(e.right.pos, 'compare a tecla com o nome dela: key == "Escape"')
            if not text or not all(c.isalnum() or c == "_" for c in text):
                raise GvtError(e.right.pos, f"nome de tecla estranho: '{text}'", 'exemplos: "Escape", "Return", "a", "space", "Up"')
            self.needs_xkb = True
            return f"{lc} {op} XKB_KEY_{text}", BOOL
        rc, rt = self.expr(e.right, lt if lt.kind == "enum" else None)
        if lt.kind == "string" and rt.kind == "string":
            return f"strcmp({lc}, {rc}) {op} 0", BOOL
        if lt.numeric and rt.numeric or lt == rt and lt.kind in ("bool", "enum"):
            return f"{wrap(lc)} {op} {wrap(rc)}", BOOL
        raise GvtError(e.pos, f"não dá para comparar {lt.describe()} com {rt.describe()}")

    def x_Ternary(self, e, want):
        c, _ = self.expr(e.cond, BOOL, "a condição antes do ?")
        a, at = self._expr(e.then, want)
        b, bt = self._expr(e.other, want)
        if want is not None:
            a = self.coerce(a, at, want, e.then.pos) if want.kind != "enum" else a
            b = self.coerce(b, bt, want, e.other.pos) if want.kind != "enum" else b
            t = want if want.kind in ("float", "enum") else self.unify(at, bt, e.pos)
            if t.kind == "number":
                t = self.unify(at, bt, e.pos)
        else:
            t = self.unify(at, bt, e.pos)
        return f"{wrap(c)} ? {a} : {b}", t

    def x_ListLit(self, e, want):
        raise GvtError(e.pos, "uma lista [ ] só pode ser o valor inicial de um var ou let",
                       "declare a lista fora: let nomes = [\"a\", \"b\"]")

    def x_RecordLit(self, e, want):
        if want is None or want.kind != "record":
            raise GvtError(e.pos, "um registro { } só pode ser o valor inicial de um var ou let, ou ir para um campo que já é registro")
        return f"(struct {want.rec.cname}){self.record_init(e, want)}", want

    def x_Call(self, e, want):
        if not isinstance(e.func, S.Name):
            raise GvtError(e.pos, "só dá para chamar funções pelo nome")
        name = e.func.name
        if name in self.fns:
            return self.call_fn(e, self.fns[name])
        if name in BUILTINS:
            return self.builtin(e, name, want)
        hint = suggest(name, set(self.fns) | BUILTINS | ELEMENTS)
        if name in ELEMENTS:
            hint = f"{name} é um elemento: escreva-o sozinho na linha, não dentro de uma conta"
        raise GvtError(e.func.pos, f"função desconhecida: '{name}'", hint)

    def call_fn(self, e, fn):
        if fn.draws and (self.event_depth or (self.fn and not self.fn.draws)):
            if self.event_depth:
                raise GvtError(e.pos, f"{fn.decl.name} desenha na tela e não pode ser chamada num evento",
                               "num evento, mude o estado; o desenho vem no próximo quadro")
            raise GvtError(e.pos, f"{fn.decl.name} desenha na tela e não pode ser chamada numa função que retorna valor")
        args = self.bind_args(e, fn.decl.name, fn.params)
        if fn.draws:
            args.insert(0, self.id_code(f"call_{e.pos.line}_{e.pos.col}") + ".id")
        return f"{fn.cname}({', '.join(args)})", fn.ret

    def bind_args(self, e, fname, params):
        given = {}
        for k, a in enumerate(e.args):
            if a.name is None:
                if given and any(isinstance(n, str) for n in given):
                    raise GvtError(a.pos, "os argumentos com nome vêm depois dos sem nome")
                if k >= len(params):
                    raise GvtError(a.pos, f"{fname} recebe {len(params)} argumento(s)")
                key = params[k][0]
            else:
                if a.name not in {p for p, _ in params}:
                    raise GvtError(a.pos, f"{fname} não tem o parâmetro '{a.name}'", suggest(a.name, [p for p, _ in params]))
                key = a.name
            if key in given:
                raise GvtError(a.pos, f"o parâmetro '{key}' foi dado duas vezes")
            given[key] = a
        out = []
        for p, t in params:
            if p not in given:
                raise GvtError(e.pos, f"falta o argumento '{p}' de {fname}")
            code, _ = self.expr(given[p].value, t, f"o argumento '{p}'")
            out.append(code)
        return out

    def builtin(self, e, name, want):
        args = e.args
        pos = e.pos

        def n_args(lo, hi=None):
            hi = lo if hi is None else hi
            if not lo <= len(args) <= hi:
                expect = f"{lo}" if lo == hi else f"de {lo} a {hi}"
                raise GvtError(pos, f"{name}() recebe {expect} argumento(s), mas recebeu {len(args)}")
            for a in args:
                if a.name is not None and name not in ("grow", "fit"):
                    raise GvtError(a.pos, f"{name}() não recebe argumentos com nome")

        def num(k, t=None):
            code, ty = self.expr(args[k].value, t)
            if not ty.numeric:
                raise GvtError(args[k].pos, f"{name}() é para números, e isto é {ty.describe()}")
            return code, ty

        if name == "round":
            n_args(1)
            c, _ = num(0, FLOAT)
            return f"(int)lroundf({c})", INT
        if name in ("floor", "ceil", "sqrt", "sin", "cos"):
            n_args(1)
            c, _ = num(0, FLOAT)
            return f"{name}f({c})", FLOAT
        if name == "pow":
            n_args(2)
            a, _ = num(0, FLOAT)
            b, _ = num(1, FLOAT)
            return f"powf({a}, {b})", FLOAT
        if name == "int":
            n_args(1)
            c, _ = num(0)
            return f"(int)({c})", INT
        if name == "float":
            n_args(1)
            c, _ = num(0)
            return f"(float)({c})", FLOAT
        if name in ("abs", "min", "max", "clamp"):
            n_args(1 if name == "abs" else 3 if name == "clamp" else 2)
            codes = [num(k) for k in range(len(args))]
            t = FLOAT if any(ty == FLOAT for _, ty in codes) else INT
            suffix = "f" if t == FLOAT else "i"
            self.helpers.add(f"{name}{suffix}")
            return f"gvt_{name}{suffix}({', '.join(c for c, _ in codes)})", t
        if name == "len":
            n_args(1)
            _, t = self.expr(args[0].value)
            if t.kind != "list":
                raise GvtError(args[0].pos, f"len() é para listas, e isto é {t.describe()}")
            return str(t.size), INT
        if name == "alpha":
            n_args(2)
            c, _ = self.expr(args[0].value, COLOR, "a cor")
            a, _ = self.expr(args[1].value, FLOAT, "a transparência")
            return f"gv_alfa({c}, {a})", COLOR
        if name == "rgb":
            n_args(1)
            c, _ = self.expr(args[0].value, INT, "a cor 0xRRGGBBAA")
            return f"gv_cor({c})", COLOR
        if name == "animate":
            n_args(1, 2)
            target, t = self.expr(args[0].value, want if want is not None and want.kind in ("color", "float") else None)
            ms = "gv_t.duracao_normal"
            if len(args) == 2:
                d = args[1].value
                if isinstance(d, S.Name) and d.name in DURATION.enum[1] and not self.lookup(d.name, use=False):
                    ms = DURATION.enum[1][d.name]  # fast, normal, slow: as durações do tema
                else:
                    ms, _ = self.expr(d, INT, "a duração em ms")
            # a chave da animação: o lugar da chamada, o índice nas listas abertas e a semente da fn,
            # para cada volta de um for (e cada chamada de uma fn) ter a sua
            key = self.id_code(f"anim_{pos.line}_{pos.col}") + ".id"
            if t.kind == "color":
                return f"gv_anim_cor({key}, {target}, {ms})", COLOR
            if not t.numeric:
                raise GvtError(args[0].pos, f"animate() anima números e cores, e isto é {t.describe()}")
            return f"gv_anim({key}, {target}, {ms})", FLOAT
        if name in ("hovered", "pressed", "tapped"):
            n_args(0, 1)
            fname = {"hovered": "gv_por_cima", "pressed": "gv_premido", "tapped": "gv_tocado"}[name]
            if not args:
                if name == "tapped":
                    raise GvtError(pos, "tapped() precisa de um id: tapped(#botao)", "dentro do elemento use on_tap { }")
                return f"{fname}({self.current_elem(pos, name).idvar})", BOOL
            c, _ = self.expr(args[0].value, ID, "o id")
            return f"{fname}({c})", BOOL
        if name == "now":
            n_args(0)
            return "(float)gv_agora()", FLOAT
        if name in ("width", "height"):
            n_args(0)
            return f"gv_app_{'largura' if name == 'width' else 'altura'}(gvt_app)", FLOAT
        if name == "has_arg":
            n_args(1)
            c, _ = self.expr(args[0].value, STRING, "o argumento")
            self.helpers.add("has_arg")
            return f"gvt_has_arg({c})", BOOL
        if name == "print":
            n_args(1)
            a = args[0].value
            if isinstance(a, S.Str):
                fmt, fargs = self.format(a, "\n")
            else:
                fmt, fargs = self.format(S.make(S.Str, a.pos, parts=[(a, None)]), "\n")
            return f"printf({', '.join([fmt] + fargs)}), fflush(stdout)", VOID
        if name == "quit":
            n_args(0)
            return "gv_app_sair(gvt_app)", VOID
        if name == "redraw":
            n_args(0)
            return "gv_app_redesenhar(gvt_app)", VOID
        if name == "load_theme":
            n_args(1)
            c, _ = self.expr(args[0].value, STRING, "o caminho do tema")
            return f"gv_tema_carregar({c})", BOOL
        if name in ("grow", "fit", "percent"):
            raise GvtError(pos, f"{name}() só vale em width: e height:", f"exemplo: width: {name}(0, 420)" if name != "percent" else "exemplo: width: percent(0.5)")
        raise GvtError(pos, f"função desconhecida: '{name}'")

    # ---- valores iniciais (constantes vão direto para a struct estática) ----

    def infer(self, e, declared, pos, name):
        """O tipo de um var/let pelo valor inicial (ou pelo tipo escrito)."""
        if declared is not None:
            return self.type_of(declared, e, name)
        if isinstance(e, S.ListLit):
            if not e.items:
                raise GvtError(e.pos, "uma lista vazia precisa do tipo", f"exemplo: var {name}: [int] = []")
            if all(isinstance(it, S.RecordLit) for it in e.items):
                return Type("list", item=self.record_type(e.items, f"{name}_item"), size=len(e.items))
            item = None
            for it in e.items:
                t = self.infer(it, None, it.pos, name)
                item = t if item is None else self.unify(item, t, it.pos)
            if item.kind == "list":
                raise GvtError(e.pos, "listas de listas ainda não existem", "use uma lista de registros: [{a: 1}, {a: 2}]")
            return Type("list", item=item, size=len(e.items))
        if isinstance(e, S.RecordLit):
            return self.record_type([e], f"{name}_t")
        _, t = self.expr(e)
        if t.kind in ("void", "enum", "id"):
            raise GvtError(e.pos, f"não dá para guardar {t.describe()} numa variável")
        return t

    def type_of(self, ref, value, name):
        if ref.name == "list":
            item = self.type_of(ref.item, None, name)
            if not isinstance(value, S.ListLit):
                raise GvtError(ref.pos, "uma variável lista começa com uma lista [ ]")
            return Type("list", item=item, size=len(value.items))
        return {"int": INT, "float": FLOAT, "bool": BOOL, "string": STRING, "color": COLOR}[ref.name]

    def record_type(self, literals, base):
        fields = []
        for lit in literals:
            if not isinstance(lit, S.RecordLit):
                raise GvtError(lit.pos, "todos os itens da lista deviam ser registros { }")
            names = [n for n, _ in lit.fields]
            if len(set(names)) != len(names):
                raise GvtError(lit.pos, "um campo repete-se no registro")
            if not fields:
                for fname, fv in lit.fields:
                    t = self.infer(fv, None, fv.pos, fname)
                    if t.kind in ("list", "record"):
                        raise GvtError(fv.pos, "um campo de registro ainda não pode ser lista nem registro")
                    fields.append([fname, t])
                continue
            if sorted(names) != sorted(n for n, _ in fields):
                raise GvtError(lit.pos, f"todos os registros da lista deviam ter os campos {', '.join(n for n, _ in fields)}")
            for fname, fv in lit.fields:
                for f in fields:
                    if f[0] == fname:
                        f[1] = self.unify(f[1], self.infer(fv, None, fv.pos, fname), fv.pos)
        cname = base
        k = 2
        while cname in self.record_names:
            cname = f"{base}{k}"
            k += 1
        self.record_names.add(cname)
        rec = RecordDef(cname, [(n, t) for n, t in fields])
        lines = [f"struct {cname} {{"] + [f"\t{c_decl(t, field_name(n))};" for n, t in rec.fields] + ["};"]
        self.records.append("\n".join(lines))
        return Type("record", rec=rec)

    def init_value(self, e, t):
        """O valor inicial de uma variável em C: {a, b} para listas, { .x = 1 } para registros."""
        if t.kind == "list":
            if not isinstance(e, S.ListLit):
                raise GvtError(e.pos, "esperava uma lista [ ]")
            if len(e.items) != t.size:
                raise GvtError(e.pos, f"a lista devia ter {t.size} itens")
            return "{ " + ", ".join(self.init_value(it, t.item) for it in e.items) + " }"
        if t.kind == "record":
            return self.record_init(e, t)
        text = literal_text(e)
        if t.kind == "color" and text is not None and hex_color(text):
            return "{ %d, %d, %d, %d }" % hex_color(text)  # sem (Clay_Color): vale numa struct estática
        code, _ = self.expr(e, t)
        return code

    def record_init(self, e, t):
        if not isinstance(e, S.RecordLit):
            raise GvtError(e.pos, "esperava um registro { }")
        given = {n: v for n, v in e.fields}
        for n in given:
            if t.rec.field(n) is None:
                raise GvtError(e.pos, f"o registro não tem o campo '{n}'", suggest(n, [f for f, _ in t.rec.fields]))
        parts = []
        for n, ft in t.rec.fields:
            if n not in given:
                raise GvtError(e.pos, f"falta o campo '{n}' no registro")
            parts.append(f".{field_name(n)} = {self.init_value(given[n], ft)}")
        return "{ " + ", ".join(parts) + " }"

    def is_const(self, e):
        if isinstance(e, (S.Num, S.Bool)):
            return True
        if isinstance(e, S.Str):
            return literal_text(e) is not None
        if isinstance(e, S.Unary):
            return self.is_const(e.expr)
        if isinstance(e, S.Binary):
            return e.op not in ("==", "!=") and self.is_const(e.left) and self.is_const(e.right)
        if isinstance(e, S.ListLit):
            return all(self.is_const(i) for i in e.items)
        if isinstance(e, S.RecordLit):
            return all(self.is_const(v) for _, v in e.fields)
        return False

    # ---- comandos ----

    def block(self, stmts, scope=None):
        self.scopes.append(scope or {})
        out = []
        decls = []  # (símbolo, linha logo depois da declaração)
        for st in stmts:
            out.extend(self.stmt(st))
            if isinstance(st, S.VarDecl):
                decls.append((self.scopes[-1][st.name], len(out)))
        self.scopes.pop()
        for sym, at in reversed(decls):
            if not sym.used:
                self.warn(sym.pos, f"'{sym.name}' é declarado e nunca usado")
                out.insert(at, f"(void){sym.cname};")
        return out

    def stmt(self, st):
        return getattr(self, "s_" + type(st).__name__)(st)

    def s_VarDecl(self, st):
        t = self.infer(st.value, st.type, st.pos, st.name)
        init = self.init_value(st.value, t)
        sym = self.declare(st.pos, st.name, t, st.mutable)
        const = "" if st.mutable or t.kind == "list" else "const "
        return [f"{const}{c_decl(t, sym.cname)} = {init};"]

    def s_Assign(self, st):
        code, t, mutable, why = self.lvalue(st.target)
        if not mutable:
            raise GvtError(st.pos, why)
        if t.kind == "list":
            raise GvtError(st.pos, "não dá para trocar uma lista inteira de uma vez", "mude item a item: lista[i] = ...")
        if st.op == "=":
            value, _ = self.expr(st.value, t, "o novo valor")
            if self.in_state(st.target):
                # um texto montado ({ }) vive só um quadro: o estado do app guarda uma cópia dele
                if t.kind == "string":
                    self.helpers.add("keep")
                    return [f"gvt_guardar(&{code}, {value});"]
                if t.kind == "record" and any(ft.kind == "string" for _, ft in t.rec.fields):
                    self.helpers.add("keep")
                    return [f"{code} = {value};"] + [f"gvt_guardar(&{code}.{field_name(n)}, {code}.{field_name(n)});"
                                                     for n, ft in t.rec.fields if ft.kind == "string"]
            return [f"{code} = {value};"]
        if not t.numeric:
            raise GvtError(st.pos, f"{st.op} é para números, e isto é {t.describe()}")
        value, vt = self.expr(st.value, t, "o valor")
        if t == INT and st.op == "/=":
            raise GvtError(st.pos, "/= num int perderia as casas decimais", f"use {code} = int({code} / ...)")
        return [f"{code} {st.op} {value};"]

    def in_state(self, e):
        """Se o alvo de uma atribuição mora no estado do app (que dura mais do que o quadro)."""
        if isinstance(e, S.Name):
            sym = self.lookup(e.name, use=False)
            return sym is not None and (sym.ptr or self.globals.get(e.name) is sym)
        if isinstance(e, S.Member):
            if isinstance(e.obj, S.Name) and e.obj.name == "theme" and not self.lookup("theme", use=False):
                return False
            return self.in_state(e.obj)
        if isinstance(e, S.Index):
            return self.in_state(e.obj)
        return False

    def lvalue(self, e):
        """(código, tipo, se dá para mudar, porque não)"""
        if isinstance(e, S.Name):
            sym = self.lookup(e.name)
            if not sym:
                code, t = self.expr(e)
                return code, t, False, f"'{e.name}' não é uma variável"
            code, t = self.expr(e)
            return code, t, sym.mutable, f"'{e.name}' é let (não muda); declare com var para poder mudar"
        if isinstance(e, S.Member):
            code, t = self.expr(e)
            if isinstance(e.obj, S.Name) and e.obj.name == "theme" and not self.lookup("theme", use=False):
                return code, t, e.field != "font", "a fonte do tema muda-se no tema.ini"
            _, _, mutable, why = self.lvalue(e.obj)
            return code, t, mutable, why
        if isinstance(e, S.Index):
            code, t = self.expr(e)
            _, _, mutable, why = self.lvalue(e.obj)
            return code, t, mutable, why
        code, t = self.expr(e)
        return code, t, False, "só dá para mudar uma variável, um campo ou um item de lista"

    def s_If(self, st):
        cond, _ = self.expr(st.cond, BOOL, "a condição do if")
        out = [f"if ({cond}) {{"] + indent(self.block(st.then))
        other = st.other
        while other:
            if len(other) == 1 and isinstance(other[0], S.If):
                nested = other[0]
                c2, _ = self.expr(nested.cond, BOOL, "a condição do else if")
                out.append(f"}} else if ({c2}) {{")
                out += indent(self.block(nested.then))
                other = nested.other
            else:
                out.append("} else {")
                out += indent(self.block(other))
                other = None
        out.append("}")
        return out

    def s_For(self, st):
        it = st.iterable
        scope = {}
        self.scopes.append(scope)
        if isinstance(it, S.Range):
            start, _ = self.expr(it.start, INT, "o começo do intervalo")
            end, _ = self.expr(it.end, INT, "o fim do intervalo")
            sym = self.declare(st.pos, st.item, INT, False)
            head = f"for (int {sym.cname} = {start}; {sym.cname} {'<=' if it.inclusive else '<'} {end}; {sym.cname}++) {{"
            idx = sym.cname
            pre = []
        else:
            lst, t = self.expr(it)
            if t.kind != "list":
                raise GvtError(it.pos, f"o for percorre listas ou intervalos (0..10), e isto é {t.describe()}")
            _, _, mutable, _ = self.lvalue(it)
            if st.index:
                isym = self.declare(st.pos, st.index, INT, False)
                idx = isym.cname
            else:
                idx = self.tmp("i")
            head = f"for (int {idx} = 0; {idx} < {t.size}; {idx}++) {{"
            if t.item.kind == "record":
                sym = self.declare(st.pos, st.item, t.item, mutable, ptr=True)
                const = "" if mutable else "const "
                pre = [f"{const}struct {t.item.rec.cname} *{sym.cname} = &{lst}[{idx}];"]
            else:
                sym = self.declare(st.pos, st.item, t.item, False)
                pre = [f"{c_decl(t.item, sym.cname)} = {lst}[{idx}];"]
        self.frames.append("loop")
        self.loops.append(idx)
        body = self.block(st.body)
        self.loops.pop()
        self.frames.pop()
        self.scopes.pop()
        if not isinstance(it, S.Range) and not sym.used:
            pre = []
            if st.index:
                self.warn(st.pos, f"'{st.item}' nunca é usado", f"para só o índice: for {st.index} in 0..len(...)")
            else:
                self.warn(st.pos, f"'{st.item}' nunca é usado")
        if isinstance(it, S.Range) and not sym.used:
            self.warn(st.pos, f"'{st.item}' nunca é usado")
        return [head] + indent(pre + body) + ["}"]

    def s_While(self, st):
        cond, _ = self.expr(st.cond, BOOL, "a condição do while")
        self.frames.append("loop")
        self.loops.append(self.tmp("w"))  # um índice que não existe: ids dentro de while precisam de #id[i]
        idx = self.loops[-1]
        body = self.block(st.body)
        self.loops.pop()
        self.frames.pop()
        if any(idx in line for line in body):
            raise GvtError(st.pos, "elementos sem #id[índice] dentro de um while", "use for, ou dê a cada elemento um #nome[i]")
        return [f"while ({cond}) {{"] + indent(body) + ["}"]

    def s_Return(self, st):
        if not self.fn:
            raise GvtError(st.pos, "return só vale dentro de uma fn")
        self.check_not_in_element(st.pos, "return")
        if st.value is None:
            if self.fn.ret != VOID:
                raise GvtError(st.pos, f"esta função retorna {self.fn.ret.describe()}: o return precisa de um valor")
            return ["return;"]
        if self.fn.ret == VOID:
            raise GvtError(st.pos, "esta função não retorna nada", f"declare o tipo: fn {self.fn.decl.name}(...) -> float")
        code, _ = self.expr(st.value, self.fn.ret, "o valor do return")
        return [f"return {code};"]

    def s_Break(self, st):
        self.loop_jump(st.pos, "break")
        return ["break;"]

    def s_Continue(self, st):
        self.loop_jump(st.pos, "continue")
        return ["continue;"]

    def loop_jump(self, pos, what):
        if "loop" not in self.frames:
            raise GvtError(pos, f"{what} só vale dentro de um for ou while")
        self.check_not_in_element(pos, what)

    def s_ExprStmt(self, st):
        if not isinstance(st.expr, S.Call):
            raise GvtError(st.pos, "esta linha calcula um valor e não faz nada com ele",
                           "para mudar uma variável use =; para chamar uma função use nome()")
        code, _ = self.expr(st.expr)
        return [f"{code};"]

    def s_Element(self, el):
        if self.event_depth:
            raise GvtError(el.pos, f"{el.kind} não pode ficar dentro de um evento",
                           "eventos mudam o estado; o que se vê fica no corpo do elemento (ou num if)")
        if self.fn and not self.fn.draws:
            raise GvtError(el.pos, "uma função que retorna valor não desenha elementos")
        return self.element(el)

    # ---- elementos ----

    def parse_args(self, el):
        sp = SPECS[el.kind]
        named, flags = {}, set()
        k = 0
        for a in el.args:
            if a.name is not None:
                if a.name not in sp["props"]:
                    raise GvtError(a.pos, f"{el.kind} não tem a propriedade '{a.name}'", self.prop_hint(el.kind, a.name))
                if a.name in named:
                    raise GvtError(a.pos, f"'{a.name}' aparece duas vezes")
                named[a.name] = a.value
            elif isinstance(a.value, S.Name) and a.value.name in sp["flags"] and not self.lookup(a.value.name, use=False):
                flags.add(a.value.name)
            else:
                if k >= len(sp["pos"]):
                    if isinstance(a.value, S.Name) and not self.lookup(a.value.name, use=False):
                        hint = suggest(a.value.name, sp["flags"] | sp["props"])
                        if not hint and sp["flags"]:
                            hint = f"as palavras soltas de {el.kind} são: {', '.join(sorted(sp['flags']))}"
                        raise GvtError(a.pos, f"{el.kind} não conhece '{a.value.name}'", hint)
                    raise GvtError(a.pos, f"argumento a mais em {el.kind}", "dê nome ao valor: propriedade: valor")
                key = sp["pos"][k]
                if key in named:
                    raise GvtError(a.pos, f"'{key}' aparece duas vezes")
                named[key] = a.value
                k += 1
        events = {}
        for ev in el.events:
            if ev.name not in sp["events"]:
                raise GvtError(ev.pos, f"{el.kind} não tem o evento {ev.name}", self.event_hint(el.kind, ev.name))
            if ev.name in events:
                raise GvtError(ev.pos, f"{ev.name} aparece duas vezes")
            events[ev.name] = ev
        if el.body and not sp["children"]:
            raise GvtError(el.body[0].pos, f"{el.kind} não tem filhos",
                           "para um botão com conteúdo próprio use row #id (...) { ... on_tap { } }" if el.kind == "button" else None)
        return named, flags, events

    def event_hint(self, kind, name):
        events = SPECS[kind]["events"]
        ok = ", ".join(sorted(events)) or "nenhum"
        if name in EVENT_HINTS and EVENT_HINTS[name] in events:
            return f"no GraviTy, {name} se chama {EVENT_HINTS[name]}"
        if name == "on_change":
            return f"{kind} não muda de valor: on_change é do slider e do toggle. Eventos de {kind}: {ok}"
        if name == "on_select":
            return "selecionar é um estado seu: var selected = 0 e on_tap { selected = i }; depois, if selected == i"
        close = suggest(name, events)
        return close or f"eventos de {kind}: {ok}"

    def prop_hint(self, kind, name):
        """A dica de uma propriedade que não existe: um nome parecido, ou o elemento que a tem."""
        sp = SPECS[kind]
        # os nomes do button usados noutro elemento
        same = {("text", "text_size"): "size", ("text", "font_size"): "size", ("icon", "icon_size"): "size",
                ("round_button", "icon_size"): "size", ("text", "bg"): "bg"}
        if (kind, name) in same and same[(kind, name)] in sp["props"]:
            return f"no {kind}, isso é '{same[(kind, name)]}'"
        close = suggest(name, sp["props"] | sp["flags"])
        if close:
            return close
        if kind == "button" and name == "size":
            return "no button, use icon_size, text_size, width ou height; size é do round_button, o botão redondo"
        owners = [k for k, s in SPECS.items() if k != "view" and name in s["props"]]
        if owners:
            shown = ", ".join(owners[:4]) + ("..." if len(owners) > 4 else "")
            return f"'{name}' existe em {shown}, mas não em {kind}"
        return None

    def parent_direction(self):
        return self.elems[-1].direction if self.elems else None

    def element(self, el):
        named, flags, events = self.parse_args(el)
        kind = el.kind
        if kind in ("view", "row", "column", "box", "card"):
            return self.container(el, named, flags, events)
        if kind == "text":
            return self.text(el, named, flags, events)
        return getattr(self, "e_" + kind)(el, named, flags, events)

    def open_elem(self, direction):
        el = Elem(self.tmp("e"), direction)
        self.elems.append(el)
        return el

    def element_id(self, el, ctx):
        if el.kind == "view":
            return f"Clay_ElementId {ctx.idvar} = GVT_ID(\"view\", 0, 0);"
        if el.id is not None:
            code, _ = self.x_IdRef(el.id, None)
        else:
            code = self.id_code(f"{el.kind}_{el.pos.line}_{el.pos.col}")
        return f"Clay_ElementId {ctx.idvar} = {code};"

    def events_code(self, events, name, ctx, prefix):
        """if (gv_tocado(id)) { ... }: o evento corre fora do CLAY, mas sabe de que elemento é."""
        ev = events.get(name)
        if not ev:
            return []
        self.event_depth += 1
        self.frames.append("event")
        body = self.block(ev.body)
        self.frames.pop()
        self.event_depth -= 1
        return [f"if ({prefix}) {{"] + indent(body) + ["}"]

    def pointer_events(self, events, ctx, container=False):
        """on_hover/on_leave e on_press/on_release: comparam o estado de agora com o do quadro anterior.

        Devolve (antes, depois): o código que vai antes do elemento e o que vai depois dele. Num
        contêiner, o apertar só se confere depois dos filhos: o toque é do último elemento declarado
        debaixo do dedo, e um botão lá dentro fica com ele.
        """
        before, after = [], []
        for bit, (on, off, test) in enumerate((("on_hover", "on_leave", "gv_por_cima"), ("on_press", "on_release", "gv_premido"))):
            if on not in events and off not in events:
                continue
            self.helpers.add("edges")
            var = self.tmp("m")
            if bit == 1 and container:
                before.append(f"(void)gv_premido({ctx.idvar}); /* candidata-se ao toque antes dos filhos */")
                target = after
                test = "gv_segurado"
            else:
                target = before
            target.append(f"int {var} = gvt_mudou({ctx.idvar}.id, {bit}, {test}({ctx.idvar}));")
            target += self.events_code(events, on, ctx, f"{var} > 0")
            target += self.events_code(events, off, ctx, f"{var} < 0")
        return before, after

    def container(self, el, named, flags, events, inner=None):
        kind = el.kind
        direction = "column" if kind in ("column", "card", "view") else "row"
        if "direction" in named:
            d = named["direction"]
            if not (isinstance(d, S.Name) and d.name in ("row", "column")):
                raise GvtError(d.pos, "direction é row ou column")
            direction = d.name
        ctx = self.open_elem(direction)
        decl = self.layout(el, named, flags, direction, ctx, kind)
        pointer_before, pointer_after = self.pointer_events(events, ctx, container=True)
        tap = pointer_before + self.events_code(events, "on_tap", ctx, f"gv_tocado({ctx.idvar})")
        if inner is not None:
            body = inner()
        else:
            self.frames.append("element")
            body = self.block(el.body)
            self.frames.pop()
        self.elems.pop()
        needs_id = el.id is not None or events or ctx.used or kind == "view" or "scroll" in named
        out = []
        if needs_id:
            out.append(self.element_id(el, ctx))
        out += tap
        if kind == "card":
            dvar = self.tmp("d")
            out.append(f"Clay_ElementDeclaration {dvar} = gv_cartao();")
            scroll = decl.pop("clip.childOffset", None)
            for path, code in decl.items():
                if path == "layout.layoutDirection" and direction == "column":
                    continue
                out.append(f"{dvar}.{path} = {code};")
            # a rolagem tem que ser lida com o elemento já aberto: o CLAY() abre e só depois avalia isto
            config = f"({dvar}.clip.childOffset = {scroll}, {dvar})" if scroll else dvar
            open_ = f"CLAY({ctx.idvar}, {config}) {{" if needs_id else f"CLAY_AUTO_ID({config}) {{"
            out.append(open_)
        else:
            if direction == "row":
                decl.pop("layout.layoutDirection", None)
            lines = designated(decl)
            head = f"CLAY({ctx.idvar}, " if needs_id else "CLAY_AUTO_ID("
            if len(lines) == 1:
                out.append(f"{head}{lines[0]}) {{")
            else:
                out.append(head + "{")
                out += indent(lines[1:-1])
                out.append("}) {")
        out += indent(body)
        out.append("}")
        return out + pointer_after

    def layout(self, el, named, flags, direction, ctx, kind):
        """As propriedades de um contêiner -> {caminho na Clay_ElementDeclaration: código C}."""
        d = {}
        d["layout.layoutDirection"] = "CLAY_TOP_TO_BOTTOM" if direction == "column" else "CLAY_LEFT_TO_RIGHT"
        if kind == "view" or "fill" in flags:
            d["layout.sizing.width"] = "CLAY_SIZING_GROW(0)"
            d["layout.sizing.height"] = "CLAY_SIZING_GROW(0)"
        if "grow" in flags:
            d["layout.sizing.width"] = "CLAY_SIZING_GROW(0)"
        for axis in ("width", "height"):
            if axis in named:
                d[f"layout.sizing.{axis}"] = self.sizing(named[axis], axis)
        # espaço por dentro: padding: 16 | [vertical, horizontal] | [cima, direita, baixo, esquerda]
        pad = {}
        if "padding" in named:
            p = named["padding"]
            if isinstance(p, S.ListLit):
                vals = [self.expr(i, NUMBER, "o padding")[0] for i in p.items]
                if len(vals) == 2:
                    pad = {"top": vals[0], "bottom": vals[0], "left": vals[1], "right": vals[1]}
                elif len(vals) == 4:
                    pad = {"top": vals[0], "right": vals[1], "bottom": vals[2], "left": vals[3]}
                else:
                    raise GvtError(p.pos, "padding é um número, [vertical, horizontal] ou [cima, direita, baixo, esquerda]")
            else:
                v, _ = self.expr(p, NUMBER, "o padding")
                pad = {"top": v, "right": v, "bottom": v, "left": v}
        if "padding_x" in named:
            v, _ = self.expr(named["padding_x"], NUMBER, "o padding_x")
            pad.update(left=v, right=v)
        if "padding_y" in named:
            v, _ = self.expr(named["padding_y"], NUMBER, "o padding_y")
            pad.update(top=v, bottom=v)
        for side in ("top", "right", "bottom", "left"):
            if f"padding_{side}" in named:
                pad[side], _ = self.expr(named[f"padding_{side}"], NUMBER, f"o padding_{side}")
        for side in ("left", "right", "top", "bottom"):
            if side in pad:
                d[f"layout.padding.{side}"] = pad[side]
        if "gap" in named:
            d["layout.childGap"], _ = self.expr(named["gap"], NUMBER, "o gap")
        # align: o eixo cruzado (como o align-items do CSS); justify: o eixo principal
        main, cross = ("x", "y") if direction == "row" else ("y", "x")
        if "center" in flags:
            d["layout.childAlignment.x"] = "CLAY_ALIGN_X_CENTER"
            d["layout.childAlignment.y"] = "CLAY_ALIGN_Y_CENTER"
        for prop, axis in (("align", cross), ("justify", main)):
            if prop in named:
                d[f"layout.childAlignment.{axis}"] = self.align(named[prop], axis, prop)
        bg = named.get("bg") or named.get("background")
        if bg is not None:
            d["backgroundColor"], _ = self.expr(bg, COLOR, "a cor de fundo")
        if "radius" in named:
            r, _ = self.expr(named["radius"], NUMBER, "o radius")
            d["cornerRadius"] = f"CLAY_CORNER_RADIUS({r})"
        border = {}
        if "border" in named:
            w, _ = self.expr(named["border"], NUMBER, "a grossura da borda")
            border = {s: w for s in ("left", "right", "top", "bottom")}
        for side in ("top", "right", "bottom", "left"):
            if f"border_{side}" in named:
                border[side], _ = self.expr(named[f"border_{side}"], NUMBER, f"o border_{side}")
        if border or "border_color" in named:
            if "border_color" in named:
                d["border.color"], _ = self.expr(named["border_color"], COLOR, "a cor da borda")
            elif kind != "card":
                d["border.color"] = "gv_t.linha"
            for side in ("left", "right", "top", "bottom"):
                if side in border:
                    d[f"border.width.{side}"] = border[side]
        if "float" in named:
            f = named["float"]
            if not (isinstance(f, S.Name) and f.name in FLOAT_POINTS):
                raise GvtError(f.pos, "float diz onde o elemento flutua em relação ao pai", f"vale: {', '.join(FLOAT_POINTS)}")
            elem_pt, parent_pt = FLOAT_POINTS[f.name]
            d["floating.attachTo"] = "CLAY_ATTACH_TO_PARENT"
            d["floating.attachPoints.element"] = f"CLAY_ATTACH_POINT_{elem_pt}"
            d["floating.attachPoints.parent"] = f"CLAY_ATTACH_POINT_{parent_pt}"
            d["floating.zIndex"] = "10"
        if "offset" in named:
            o = named["offset"]
            if not (isinstance(o, S.ListLit) and len(o.items) == 2):
                raise GvtError(o.pos, "offset é [x, y]")
            x, _ = self.expr(o.items[0], NUMBER, "o x do offset")
            y, _ = self.expr(o.items[1], NUMBER, "o y do offset")
            d["floating.offset"] = f"(Clay_Vector2){{ {x}, {y} }}"
        if "z" in named:
            d["floating.zIndex"], _ = self.expr(named["z"], INT, "o z")
        if "shadow" in named:
            sh = named["shadow"]
            if isinstance(sh, S.Bool):
                if sh.value:
                    d["userData"] = "gv_sombra(24, 14, 0.5f)"
            elif isinstance(sh, S.ListLit) and len(sh.items) == 3:
                vals = [self.expr(i, NUMBER, "a sombra")[0] for i in sh.items]
                d["userData"] = f"gv_sombra({', '.join(vals)})"
            else:
                raise GvtError(sh.pos, "shadow é true ou [desfoque, deslocamento_y, opacidade]", "exemplo: shadow: [24, 14, 0.5]")
        if "scroll" in named:
            sc = named["scroll"]
            if not (isinstance(sc, S.Name) and sc.name in ("vertical", "horizontal", "both")):
                raise GvtError(sc.pos, "scroll é vertical, horizontal ou both")
            if sc.name in ("vertical", "both"):
                d["clip.vertical"] = "true"
            if sc.name in ("horizontal", "both"):
                d["clip.horizontal"] = "true"
            d["clip.childOffset"] = "Clay_GetScrollOffset()"
        if "clip" in flags:
            d["clip.vertical"] = "true"
            d["clip.horizontal"] = "true"
        return d

    def sizing(self, e, axis):
        if isinstance(e, S.Name) and not self.lookup(e.name, use=False):
            if e.name == "grow":
                return "CLAY_SIZING_GROW(0)"
            if e.name == "fit":
                return "CLAY_SIZING_FIT(0)"
        if isinstance(e, S.Call) and isinstance(e.func, S.Name) and e.func.name in ("grow", "fit", "percent") and e.func.name not in self.fns:
            name = e.func.name
            if name == "percent":
                if len(e.args) != 1:
                    raise GvtError(e.pos, "percent() recebe um número de 0 a 1", "exemplo: percent(0.5)")
                v, _ = self.expr(e.args[0].value, FLOAT, "a porcentagem")
                return f"CLAY_SIZING_PERCENT({v})"
            lo, hi = "0", None
            for k, a in enumerate(e.args):
                key = a.name or ("min" if k == 0 else "max" if k == 1 else None)
                if key not in ("min", "max"):
                    raise GvtError(a.pos, f"{name}() recebe min e max", f"exemplo: {name}(0, 420) ou {name}(max: 420)")
                v, _ = self.expr(a.value, NUMBER, f"o {key}")
                if key == "min":
                    lo = v
                else:
                    hi = v
            return f"CLAY_SIZING_{name.upper()}({lo}{', ' + hi if hi else ''})"
        lit = literal_text(e)
        if lit is not None and lit.endswith("%"):
            try:
                return f"CLAY_SIZING_PERCENT({c_float(float(lit[:-1]) / 100)})"
            except ValueError:
                raise GvtError(e.pos, f"porcentagem estranha: '{lit}'")
        v, _ = self.expr(e, NUMBER, f"o {axis}")
        return f"CLAY_SIZING_FIXED({v})"

    def align(self, e, axis, prop):
        code, _ = self.expr(e, ALIGN_X if axis == "x" else ALIGN_Y, f"o {prop}")
        return code

    # ---- os componentes ----

    def text(self, el, named, flags, events):
        if "text" not in named:
            raise GvtError(el.pos, "text precisa do texto", 'exemplo: text("Olá")')
        s = self.clay_string(named["text"])
        if "size" in named:
            size, _ = self.expr(named["size"], NUMBER, "o tamanho do texto")
        elif "style" in named:
            size, _ = self.expr(named["style"], TEXT_STYLE, "o style")
        else:
            size = "gv_t.tamanho_corpo"
        color = self.expr(named["color"], COLOR, "a cor do texto")[0] if "color" in named else "gv_t.texto"
        weight = self.expr(named["weight"], WEIGHT, "o peso")[0] if "weight" in named else "GV_PESO_NORMAL"
        call = f"gv_texto({s}, {size}, {color}, {weight});"
        box_props = {k: v for k, v in named.items() if k in CONTAINER_PROPS}
        if not (box_props or flags or events or el.id is not None):
            return [call]
        # um texto com caixa: largura, alinhamento, fundo... vira um contêiner com o texto dentro
        if "align" in box_props:
            box_props["justify"] = box_props.pop("align")
        wrapper = S.make(S.Element, el.pos, kind="box", id=el.id, args=[], body=[], events=el.events)
        return self.container(wrapper, box_props, flags, events, inner=lambda: [call])

    def check_icon(self, e):
        """Avisa de um ícone que não existe (os literais, e os dois lados de um ? :)."""
        if self.icons is None:
            return
        if isinstance(e, S.Ternary):
            self.check_icon(e.then)
            self.check_icon(e.other)
            return
        name = literal_text(e)
        if name is not None and name not in self.icons:
            self.warn(e.pos, f"o Gravity não tem o ícone '{name}'", suggest(name, self.icons))

    def e_icon(self, el, named, flags, events):
        if "name" not in named:
            raise GvtError(el.pos, "icon precisa do nome do ícone", 'exemplo: icon("volume", 24)')
        name, _ = self.expr(named["name"], STRING, "o nome do ícone")
        self.check_icon(named["name"])
        size = self.expr(named["size"], NUMBER, "o tamanho do ícone")[0] if "size" in named else "24"
        color = self.expr(named["color"], COLOR, "a cor do ícone")[0] if "color" in named else "gv_t.icone"
        return [f"gv_icone({name}, {size}, {color});"]

    def component(self, el, call, events, event_name, scope=None):
        ctx = self.open_elem(None)
        try:
            code = call(ctx)
        finally:
            self.elems.pop()
        out = [self.element_id(el, ctx)]
        self.elems.append(ctx)
        out += self.pointer_events(events, ctx)[0]
        self.elems.pop()
        ev = events.get(event_name)
        if not ev:
            return out + [f"{code};"]
        self.elems.append(ctx)
        self.event_depth += 1
        self.frames.append("event")
        body = self.block(ev.body, scope)
        self.frames.pop()
        self.event_depth -= 1
        self.elems.pop()
        return out + [f"if ({code}) {{"] + indent(body) + ["}"]

    def e_button(self, el, named, flags, events):
        if "text" not in named and "icon" not in named:
            raise GvtError(el.pos, "button precisa de texto, de ícone ou dos dois", 'exemplo: button #ok ("Ok", icon: "check")')

        def call(ctx):
            text = self.expr(named["text"], STRING, "o texto do botão")[0] if "text" in named else "NULL"
            icon = self.expr(named["icon"], STRING, "o ícone do botão")[0] if "icon" in named else "NULL"
            if "icon" in named:
                self.check_icon(named["icon"])
            style = self.expr(named["style"], BUTTON_STYLE, "o style")[0] if "style" in named else "GV_BOTAO_CHEIO"
            custom = [k for k in BUTTON_OPTIONS if k in named]
            if not custom:
                return f"gv_botao({ctx.idvar}, {icon}, {text}, {style})"
            # com tamanhos ou cores próprios: parte do padrão do estilo e muda só o que foi dado
            ovar = self.tmp("o")
            pre.append(f"gv_botao_opcoes {ovar} = gv_botao_padrao({style});")
            for k in custom:
                field, kind = BUTTON_OPTIONS[k]
                if kind == "sizing":
                    value = self.sizing(named[k], "width")
                elif kind == "weight":
                    value = self.expr(named[k], WEIGHT, "o peso")[0]
                elif kind == "color":
                    value = self.expr(named[k], COLOR, f"o {k}")[0]
                else:
                    value = self.expr(named[k], NUMBER, f"o {k}")[0]
                pre.append(f"{ovar}.{field} = {value};")
            return f"gv_botao_ex({ctx.idvar}, {icon}, {text}, &{ovar})"
        pre = []
        out = self.component(el, call, events, "on_tap")
        return pre + out

    def e_round_button(self, el, named, flags, events):
        if "icon" not in named:
            raise GvtError(el.pos, "round_button precisa de um ícone", 'exemplo: round_button #wifi (icon: "wifi")')

        def call(ctx):
            icon, _ = self.expr(named["icon"], STRING, "o ícone")
            self.check_icon(named["icon"])
            size = self.expr(named["size"], NUMBER, "o tamanho")[0] if "size" in named else "44"
            on = self.expr(named["on"], BOOL, "o on")[0] if "on" in named else "false"
            danger = self.expr(named["danger"], BOOL, "o danger")[0] if "danger" in named else "false"
            return f"gv_botao_redondo({ctx.idvar}, {icon}, {size}, {on}, {danger})"
        return self.component(el, call, events, "on_tap")

    def value_ref(self, el, named, t, events):
        """O valor de um slider/toggle: uma variável (muda sozinha) ou uma conta (muda só no on_change)."""
        if "value" not in named:
            raise GvtError(el.pos, f"{el.kind} precisa do value", f"exemplo: {el.kind} #x (value: {'volume' if t == FLOAT else 'ligado'})")
        v = named["value"]
        pre = []
        if isinstance(v, (S.Name, S.Member, S.Index)):
            code, vt, mutable, why = self.lvalue(v)
            if vt != t:
                raise GvtError(v.pos, f"o value de {el.kind} devia ser {t.describe()}, mas é {vt.describe()}")
            if mutable:
                return pre, f"&{code}", code
            if "on_change" not in events:
                raise GvtError(v.pos, why, "ou trate a mudança num on_change { value ... }")
        code, _ = self.expr(v, t, "o value")
        tmp = self.tmp("v")
        pre.append(f"{c_decl(t, tmp)} = {code};")
        if "on_change" not in events:
            self.warn(v.pos, f"este {el.kind} mostra uma conta e não tem on_change: mexer nele não muda nada")
        return pre, f"&{tmp}", tmp

    def e_slider(self, el, named, flags, events):
        pre, ptr, value = self.value_ref(el, named, FLOAT, events)
        track = self.expr(named["track"], NUMBER, "o track")[0] if "track" in named else "12"
        knob = self.expr(named["knob"], NUMBER, "o knob")[0] if "knob" in named else "28"
        scope = {"value": Symbol(value, FLOAT, False)}
        return pre + self.component(el, lambda ctx: f"gv_deslizante({ctx.idvar}, {ptr}, {track}, {knob})", events, "on_change", scope)

    def e_toggle(self, el, named, flags, events):
        pre, ptr, value = self.value_ref(el, named, BOOL, events)
        scope = {"value": Symbol(value, BOOL, False)}
        return pre + self.component(el, lambda ctx: f"gv_interruptor({ctx.idvar}, {ptr})", events, "on_change", scope)

    def e_separator(self, el, named, flags, events):
        if "vertical" in flags:
            vertical = True
        elif "horizontal" in flags:
            vertical = False
        else:
            vertical = self.parent_direction() == "row"
        length = self.expr(named["length"], NUMBER, "o comprimento")[0] if "length" in named else "0"
        return [f"gv_separador({'true' if vertical else 'false'}, {length});"]

    def e_spacer(self, el, named, flags, events):
        direction = self.parent_direction()
        if "size" in named:
            v, _ = self.expr(named["size"], NUMBER, "o tamanho do spacer")
            axis = "CLAY_SIZING_FIXED(%s)" % v
        else:
            axis = "CLAY_SIZING_GROW(0)"
        if direction == "row":
            sizing = f".width = {axis}"
        elif direction == "column":
            sizing = f".height = {axis}"
        else:
            sizing = f".width = {axis}, .height = {axis}"
        return [f"CLAY_AUTO_ID({{ .layout = {{ .sizing = {{ {sizing} }} }} }}) {{}}"]

    # ---- o programa ----

    def compile(self):
        prog = self.program
        if prog.app is None:
            raise GvtError(prog.pos, "o arquivo não tem app", "comece com: app Nome { view { ... } }")
        app = prog.app

        # 1. as assinaturas das funções (podem ser chamadas antes de aparecerem)
        for d in prog.decls:
            if isinstance(d, S.FnDecl):
                if d.name in self.fns:
                    raise GvtError(d.pos, f"já existe uma função {d.name}")
                if d.name in BUILTINS or d.name in ELEMENTS:
                    raise GvtError(d.pos, f"'{d.name}' já é um nome da linguagem; escolha outro")
                params = []
                for p in d.params:
                    if p.type.name == "list":
                        raise GvtError(p.pos, "parâmetros ainda não podem ser listas", "use o índice: fn linha(i: int)")
                    params.append((p.name, self.type_of(p.type, None, p.name)))
                ret = self.type_of(d.ret, None, d.name) if d.ret else VOID
                self.fns[d.name] = FnInfo(d, f"fn_{d.name}", params, ret)

        # 2. as variáveis globais: o estado do app
        self.scopes.append({})
        for d in prog.decls:
            if isinstance(d, S.VarDecl):
                if d.name in self.globals:
                    raise GvtError(d.pos, f"'{d.name}' já foi declarado")
                if d.name in self.fns:
                    raise GvtError(d.pos, f"já existe uma função {d.name}")
                if d.name in ("theme", "hovered", "pressed") or d.name in ELEMENTS:
                    raise GvtError(d.pos, f"'{d.name}' é um nome da linguagem; escolha outro")
                t = self.infer(d.value, d.type, d.pos, d.name)
                cname = field_name(d.name)
                self.state_fields.append(f"{c_decl(t, cname)};")
                if self.is_const(d.value):
                    self.state_init.append(f".{cname} = {self.init_value(d.value, t)},")
                else:
                    if t.kind in ("list", "record"):
                        raise GvtError(d.value.pos, "o valor inicial de uma lista ou registro global tem que ser constante")
                    if t.kind == "string":
                        self.helpers.add("keep")
                        self.late_init.append(f"gvt_guardar(&s.{cname}, {self.init_value(d.value, t)});")
                    else:
                        self.late_init.append(f"s.{cname} = {self.init_value(d.value, t)};")
                self.globals[d.name] = Symbol(f"s.{cname}", t, d.mutable)
        self.scopes.pop()

        # 3. o corpo das funções
        fn_code = []
        for d in prog.decls:
            if isinstance(d, S.FnDecl):
                fn_code.append(self.compile_fn(self.fns[d.name]))

        # 4. o app: eventos e view
        props = {}
        for p in app.props:
            if p.name not in APP_PROPS:
                raise GvtError(p.pos, f"o app não tem a propriedade '{p.name}'", suggest(p.name, APP_PROPS))
            if p.name in props:
                raise GvtError(p.pos, f"'{p.name}' aparece duas vezes")
            props[p.name] = p
        events = {}
        for ev in app.events:
            if ev.name not in APP_EVENTS:
                raise GvtError(ev.pos, f"o app não tem o evento {ev.name}", f"eventos do app: {', '.join(sorted(APP_EVENTS))}")
            if ev.name in events:
                raise GvtError(ev.pos, f"{ev.name} aparece duas vezes")
            events[ev.name] = ev

        draw = []
        if "on_key" in events:
            self.event_depth += 1
            body = self.block(events["on_key"].body, {"key": Symbol("key", KEY, False)})
            self.event_depth -= 1
            draw += ["{", "\tuint32_t key = gv_tecla();", "\tif (key) {"] + indent(body, 2) + ["\t}", "}"]
        if "on_frame" in events:
            self.event_depth += 1
            draw += self.block(events["on_frame"].body)
            self.event_depth -= 1
        self.scopes.append({})
        draw += self.element(app.view)
        self.scopes.pop()

        start = []
        if "on_start" in events:
            self.event_depth += 1
            start = self.block(events["on_start"].body)
            self.event_depth -= 1

        options = self.app_options(app, props)
        return self.assemble(app, fn_code, draw, start, options, props)

    def compile_fn(self, fn):
        d = fn.decl
        self.fn = fn
        self.frames = ["fn"]
        scope = {}
        self.scopes.append(scope)
        params = []
        for (pname, t), p in zip(fn.params, d.params):
            sym = self.declare(p.pos, pname, t, False)
            params.append(c_decl(t, sym.cname))
        if fn.draws:
            params.insert(0, "uint32_t _seed")
        body = self.block(d.body)
        unused = [scope[p.name] for p in d.params if not scope[p.name].used]
        for sym in unused:
            self.warn(sym.pos, f"o parâmetro '{sym.name}' nunca é usado")
        body = [f"(void){sym.cname};" for sym in unused] + body
        self.scopes.pop()
        self.fn = None
        self.frames = []
        ret = "void" if fn.ret == VOID else c_decl(fn.ret, "").strip()
        sig = f"static {ret} {fn.cname}({', '.join(params) or 'void'})".replace("const char * ", "const char *")
        pre = ["\t(void)_seed;"] if fn.draws else []
        return sig, [sig + " {"] + pre + indent(body) + ["}"]

    def app_options(self, app, props):
        self.event_depth += 1
        self.scopes.append({})
        opts = []
        title = props.get("title")
        if title:
            opts.append(f".titulo = {self.expr(title.value, STRING, 'o title')[0]},")
        else:
            opts.append(f".titulo = {c_string(app.name)},")
        if "id" in props:
            opts.append(f".app_id = {self.expr(props['id'].value, STRING, 'o id')[0]},")
        if "kind" in props:
            opts.append(f".tipo = {self.expr(props['kind'].value, KIND, 'o kind')[0]},")
        if "size" in props:
            w, _ = self.expr(props["size"].value, INT, "a largura")
            h, _ = self.expr(props["size"].value2, INT, "a altura")
            opts += [f".largura = {w},", f".altura = {h},"]
        if "layer" in props:
            opts.append(f".nivel = {self.expr(props['layer'].value, LEVEL, 'o layer')[0]},")
        if "anchors" in props:
            a = props["anchors"].value
            names = {"top": "GV_ANCORA_CIMA", "bottom": "GV_ANCORA_BAIXO", "left": "GV_ANCORA_ESQUERDA", "right": "GV_ANCORA_DIREITA"}
            if isinstance(a, S.Name) and a.name == "all":
                opts.append(".ancoras = GV_ANCORA_TUDO,")
            elif isinstance(a, S.ListLit) and all(isinstance(i, S.Name) and i.name in names for i in a.items):
                opts.append(f".ancoras = {' | '.join(names[i.name] for i in a.items) or '0'},")
            else:
                raise GvtError(a.pos, "anchors é all ou uma lista: [top, left, right, bottom]")
        if "exclusive" in props:
            opts.append(f".zona_exclusiva = {self.expr(props['exclusive'].value, INT, 'o exclusive')[0]},")
        if "keyboard" in props:
            opts.append(f".teclado = {self.expr(props['keyboard'].value, BOOL, 'o keyboard')[0]},")
        self.scopes.pop()
        self.event_depth -= 1
        return opts

    def assemble(self, app, fn_code, draw, start, options, props):
        out = [f"/* Gerado pelo GraviTy a partir de {os.path.basename(self.source_name)}: não edite à mão,"
               " mude o .gvt e compile de novo. */",
               "#include <math.h>", "#include <stdbool.h>", "#include <stdint.h>", "#include <stdio.h>",
               "#include <stdlib.h>", "#include <string.h>"]
        if self.needs_xkb:
            out.append("#include <xkbcommon/xkbcommon-keysyms.h>")
        out += ['', '#include "gravity.h"', "",
                "/* o id de um elemento: o nome, o índice nas listas e a semente da função que o desenha */",
                "#define GVT_ID(nome, indice, semente) Clay__HashStringWithOffset(CLAY_STRING(nome), (uint32_t)(indice), (semente))",
                "", "static gv_app *gvt_app;", "static int gvt_argc;", "static char **gvt_argv;"]
        if self.records:
            out.append("")
            out += "\n\n".join(self.records).split("\n")
        if self.state_fields:
            out += ["", "static struct {"] + indent(self.state_fields) + ["} s = {"] + indent(self.state_init) + ["};"]
        helpers = helper_code(self.helpers)
        if helpers:
            out += [""] + helpers
        if fn_code:
            out.append("")
            out += [sig + ";" for sig, _ in fn_code]
            for _, body in fn_code:
                out += [""] + body
        out += ["", "static void gvt_draw(gv_app *app, void *dados) {", "\t(void)app;", "\t(void)dados;"] + indent(draw) + ["}"]
        out += ["", "int main(int argc, char **argv) {", "\tgvt_argc = argc;", "\tgvt_argv = argv;", "\t(void)gvt_argc;",
                "\t(void)gvt_argv;"]
        if self.late_init:
            # o que não é constante começa aqui, já com o tema carregado (o app pode usar isso no size:, no kind:...)
            out += ["\tgv_tema_padrao(&gv_t);", "\tgv_tema_carregar(NULL);"] + indent(self.late_init)
        out += ["\tgvt_app = gv_app_criar(&(gv_opcoes){"] + indent(options, 2) + ["\t});",
                "\tif (!gvt_app) {", "\t\treturn 1;", "\t}"]
        if "theme" in props:
            path, _ = self.expr(props["theme"].value, STRING, "o theme")
            out.append(f"\tgv_tema_carregar({path});")
        out += indent(start)
        out += ["\treturn gv_app_correr(gvt_app, gvt_draw, NULL);", "}", ""]
        return "\n".join(out)


# ---- pedaços de C ----

def field_name(name):
    return name + "_" if name in C_KEYWORDS else name


def wrap(code):
    """Põe parênteses quando o código tem operadores soltos (para não misturar precedências)."""
    if code.startswith("(") and matching_paren(code) == len(code) - 1:
        return code
    simple = all(c.isalnum() or c in "_.[]>-" for c in code.replace("->", "")) and not code.startswith("-")
    if simple or code.replace(".", "", 1).rstrip("f").isdigit():
        return code
    if code.endswith(")") and "(" in code and code.index("(") > 0 and matching_paren(code, code.index("(")) == len(code) - 1 \
            and all(c.isalnum() or c in "_." for c in code[: code.index("(")]):
        return code
    return f"({code})"


def matching_paren(code, start=0):
    depth = 0
    in_str = False
    for i in range(start, len(code)):
        c = code[i]
        if in_str:
            if c == "\\":
                continue
            if c == '"' and code[i - 1] != "\\":
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def indent(lines, n=1):
    return ["\t" * n + line if line else line for line in lines]


def designated(d):
    """{caminho: código} -> as linhas de um inicializador C: { .layout = { ... }, ... }"""
    tree = {}
    for path, code in d.items():
        node = tree
        parts = path.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = code

    def render(node):
        return "{ " + ", ".join(f".{k} = {render(v) if isinstance(v, dict) else v}" for k, v in node.items()) + " }"

    if not tree:
        return ["{ 0 }"]
    one = render(tree)
    if len(one) <= 90:
        return [one]
    return ["{"] + [f".{k} = {render(v) if isinstance(v, dict) else v}," for k, v in tree.items()] + ["}"]


def helper_code(names):
    defs = {
        "absf": "static inline float gvt_absf(float a) { return a < 0 ? -a : a; }",
        "absi": "static inline int gvt_absi(int a) { return a < 0 ? -a : a; }",
        "minf": "static inline float gvt_minf(float a, float b) { return a < b ? a : b; }",
        "mini": "static inline int gvt_mini(int a, int b) { return a < b ? a : b; }",
        "maxf": "static inline float gvt_maxf(float a, float b) { return a > b ? a : b; }",
        "maxi": "static inline int gvt_maxi(int a, int b) { return a > b ? a : b; }",
        "clampf": "static inline float gvt_clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }",
        "clampi": "static inline int gvt_clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }",
        "edges": "/* o estado de cada elemento no quadro anterior (dentro, apertado), para on_hover, on_leave,\n"
                 " * on_press e on_release: +1 quando liga, -1 quando desliga, 0 quando não mudou */\n"
                 "static struct {\n\tuint32_t id;\n\tuint8_t bits;\n} gvt_estados[512];\n\n"
                 "static int gvt_mudou(uint32_t id, int bit, bool agora) {\n"
                 "\tuint32_t i = id % 512;\n"
                 "\tfor (int n = 0; n < 512 && gvt_estados[i].id != id && gvt_estados[i].id != 0; n++) {\n"
                 "\t\ti = (i + 1) % 512;\n\t}\n"
                 "\tgvt_estados[i].id = id;\n"
                 "\tbool antes = gvt_estados[i].bits & (1u << bit);\n"
                 "\tif (agora) {\n\t\tgvt_estados[i].bits |= (uint8_t)(1u << bit);\n\t} else {\n"
                 "\t\tgvt_estados[i].bits &= (uint8_t)~(1u << bit);\n\t}\n"
                 "\treturn agora == antes ? 0 : agora ? 1 : -1;\n}",
        "keep": "/* os textos guardados no estado do app: cada lugar (uma var, um campo) tem a sua cópia, que dura\n"
                " * até o próximo valor (um texto com { } é montado no quadro e some no fim dele) */\n"
                "static struct {\n\tconst char **lugar;\n\tchar *texto;\n\tsize_t tamanho;\n} gvt_textos[256];\n\n"
                "static void gvt_guardar(const char **lugar, const char *valor) {\n"
                "\tint k = -1;\n"
                "\tfor (int i = 0; i < 256; i++) {\n"
                "\t\tif (gvt_textos[i].lugar == lugar) {\n\t\t\tk = i;\n\t\t\tbreak;\n\t\t}\n"
                "\t\tif (k < 0 && !gvt_textos[i].lugar) {\n\t\t\tk = i;\n\t\t}\n\t}\n"
                "\tif (!valor) {\n\t\tvalor = \"\";\n\t}\n"
                "\tsize_t n = strlen(valor) + 1;\n"
                "\tif (k < 0) {\n\t\tchar *copia = malloc(n);\n\t\tif (copia) {\n\t\t\tmemcpy(copia, valor, n);\n\t\t\t*lugar = copia;\n\t\t}\n\t\treturn;\n\t}\n"
                "\tif (valor == gvt_textos[k].texto) {\n\t\t*lugar = valor;\n\t\treturn;\n\t}\n"
                "\tif (gvt_textos[k].tamanho < n) {\n"
                "\t\tchar *maior = realloc(gvt_textos[k].texto, n);\n"
                "\t\tif (!maior) {\n\t\t\treturn;\n\t\t}\n"
                "\t\tgvt_textos[k].texto = maior;\n\t\tgvt_textos[k].tamanho = n;\n\t}\n"
                "\tmemmove(gvt_textos[k].texto, valor, n);\n"
                "\tgvt_textos[k].lugar = lugar;\n"
                "\t*lugar = gvt_textos[k].texto;\n}",
        "has_arg": "static bool gvt_has_arg(const char *arg) {\n\tfor (int i = 1; i < gvt_argc; i++) {\n"
                   "\t\tif (strcmp(gvt_argv[i], arg) == 0) {\n\t\t\treturn true;\n\t\t}\n\t}\n\treturn false;\n}",
    }
    out = []
    for n in sorted(names):
        out += defs[n].split("\n")
    return out


def compile_program(program, source_name, icons=None):
    c = Compiler(program, source_name, icons)
    return c.compile(), c.warnings
