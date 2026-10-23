"""Os testes do compilador gvt.

    python3 -m unittest discover -s tests -t .

Com GRAVITY_DIR=/caminho/LUMNA_OS/gravity, o C gerado dos exemplos passa também pelo gcc
(-Wall -Wextra -Werror), contra os cabeçalhos do Gravity.
"""

import glob
import os
import shutil
import subprocess
import tempfile
import unittest

from gvt.compiler import compile_program
from gvt.errors import GvtError
from gvt.lexer import tokenize
from gvt.parser import parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "*.gvt")) + glob.glob(os.path.join(ROOT, "tests", "programas", "*.gvt")))


def build(text):
    code, warnings = compile_program(parse(text), "teste.gvt")
    return code, warnings


def app(view, top=""):
    return f"app Teste {{\n{top}\n    view {{\n{view}\n    }}\n}}\n"


class Lexer(unittest.TestCase):
    def kinds(self, text):
        return [t.kind for t in tokenize(text)]

    def test_newline_ends_statement_only_after_a_value(self):
        self.assertEqual(self.kinds("a = 1 +\n2\n"), ["NAME", "=", "INT", "+", "INT", "NEWLINE", "EOF"])

    def test_no_newlines_inside_parens(self):
        self.assertEqual(self.kinds("f(1,\n2)\n"), ["NAME", "(", "INT", ",", "INT", ")", "NEWLINE", "EOF"])

    def test_newlines_count_inside_braces(self):
        self.assertIn("NEWLINE", self.kinds("(x {\na\nb\n})")[3:6])

    def test_range_is_not_a_float(self):
        self.assertEqual(self.kinds("0..3")[:3], ["INT", "..", "INT"])

    def test_interpolation_parts(self):
        tok = tokenize('"Volume {v}%"')[0]
        self.assertEqual(tok.value[0], "Volume ")
        self.assertEqual(tok.value[1][0], "v")
        self.assertEqual(tok.value[2], "%")

    def test_escaped_braces(self):
        self.assertEqual(tokenize('"{{x}}"')[0].value, ["{x}"])

    def test_comments(self):
        self.assertEqual(self.kinds("a // b\n/* c\nd */ e"), ["NAME", "NEWLINE", "NAME", "NEWLINE", "EOF"])


class Errors(unittest.TestCase):
    """Cada erro tem que apontar a linha e a coluna certas, com uma mensagem que ajude."""

    cases = [
        (app('        text("oi", colr: muted)'), 4, 20, "não tem a propriedade 'colr'", "color"),
        (app('        button #b ("+") { on_tap { n += 1 } }', "    let n = 0"), 4, 36, "é let", None),
        (app('        if nome { text("a") }', '    var nome = "x"'), 4, 12, "devia ser bool", "nome =="),
        (app('        for i in 0..3 {\n            row { if i == 1 { break } }\n        }'), 5, 31, "break não pode ficar dentro de um elemento", None),
        (app('        text("v = " + v)', "    var v = 0.5"), 4, 21, "não dá para usar + com textos", "interpolação"),
        (app('        texto("oi")'), 4, 9, "função desconhecida: 'texto'", "text"),
        (app('        row (gorw) { text("a") }'), 4, 14, "row não conhece 'gorw'", "grow"),
        (app('        button #x ("ok") { on_tap { text("clicou") } }'), 4, 37, "não pode ficar dentro de um evento", None),
        (app('        text("x", color: theme.acent)'), 4, 31, "o tema não tem 'acent'", "accent"),
        (app('        row (align: middle) { text("x") }'), 4, 21, "nome desconhecido: 'middle'", "center"),
        (app('        return'), 4, 9, "return só vale dentro de uma fn", None),
        ("fn f(x: float) -> int { return x }\n" + app('        text("{f(1)}")'), 1, 32, "devia ser int", "round"),
        (app('        text("x")', "    var a = 1\n    var a = 2"), 3, 5, "já foi declarado", None),
        (app('        text("x")', '    var k = "Escape"\n    on_key { if key == k { quit() } }'), 3, 24, "compare a tecla", None),
        (app('        text("x")', "    var xs = [{a: 1}, {b: 2}]"), 2, 23, "os campos a", None),
        (app('        text("x"', ""), 4, 17, "falta o ')' aqui", None),
        ('app A {\n    view { text("x") }\n', 1, 1, "não tem o '}'", None),
        ('app A {\n    var x = 1\n}\n', 1, 1, "não tem view", None),
        (app('        text("oi)'), 4, 14, "texto sem as aspas", None),
        (app('        slider #s (value: nome)', '    var nome = "x"'), 4, 27, "devia ser float", None),
        (app('        while i < 3 {\n            button #b ("x")\n            i += 1\n        }', "    var i = 0"), 4, 9, "while", "#nome[i]"),
    ]

    def test_errors(self):
        for text, line, col, message, hint in self.cases:
            with self.subTest(message=message):
                with self.assertRaises(GvtError) as ctx:
                    build(text)
                err = ctx.exception
                self.assertIn(message, err.message)
                self.assertEqual((err.pos.line, err.pos.col), (line, col), err.message)
                if hint:
                    self.assertIn(hint, err.hint or "")

    def test_slider_without_on_change_warns(self):
        _, warnings = build(app("        slider #s (value: 3)"))
        self.assertEqual(len(warnings), 1)
        self.assertIn("on_change", warnings[0][1])


class Codegen(unittest.TestCase):
    def test_division_is_always_float(self):
        code, _ = build(app('        text("{a / b}")', "    var a = 1\n    var b = 2"))
        self.assertIn("(float)s.a / s.b", code)

    def test_string_equality_uses_strcmp(self):
        code, _ = build(app('        if n == "x" { text("a") }', '    var n = "x"'))
        self.assertIn('strcmp(s.n, "x") == 0', code)

    def test_ids_inside_loops_get_the_index(self):
        code, _ = build(app('        for i in 0..3 {\n            button #b ("x")\n        }'))
        self.assertIn('GVT_ID("b", i, 0)', code)

    def test_nested_loops_chain_the_ids(self):
        code, _ = build(app('        for i in 0..3 {\n            for j in 0..2 {\n                button #b ("x")\n            }\n        }'))
        self.assertIn('GVT_ID("b", j, GVT_ID("b", i, 0).id)', code)

    def test_functions_get_a_seed_per_call(self):
        code, _ = build("fn linha() {\n    button #b (\"x\")\n}\n" + app("        linha()\n        linha()"))
        self.assertIn("static void fn_linha(uint32_t _seed)", code)
        self.assertIn('GVT_ID("b", 0, _seed)', code)
        self.assertEqual(code.count("fn_linha(GVT_ID(\"call_"), 2)

    def test_keys(self):
        code, _ = build(app('        text("x")', '    on_key {\n        if key == "Escape" { quit() }\n    }'))
        self.assertIn("#include <xkbcommon/xkbcommon-keysyms.h>", code)
        self.assertIn("key == XKB_KEY_Escape", code)

    def test_theme_fields(self):
        code, _ = build(app('        text("x")', '    on_frame {\n        theme.accent = "#ff0000"\n        theme.curve = spring\n    }'))
        self.assertIn("gv_t.acento = ((Clay_Color){ 255, 0, 0, 255 });", code)
        self.assertIn("gv_t.curva = GV_CURVA_MOLA;", code)

    def test_constant_state_goes_in_the_static_struct(self):
        code, _ = build(app('        text("x")', '    var v = 0.5\n    var c = "#102030"'))
        self.assertIn(".v = 0.5f,", code)
        self.assertIn(".c = { 16, 32, 48, 255 },", code)

    def test_computed_state_starts_in_main(self):
        code, _ = build(app('        text("x")', '    let camada = has_arg("--camada")'))
        self.assertIn('s.camada = gvt_has_arg("--camada");', code)

    def test_records_in_lists(self):
        code, _ = build(app('        for a in apps {\n            text(a.nome)\n        }',
                            '    var apps = [{nome: "a", v: 1}, {nome: "b", v: 0.5}]'))
        self.assertIn("struct apps_item {", code)
        self.assertIn("float v;", code)
        self.assertIn("struct apps_item *a = &s.apps[", code)
        self.assertIn("gv_str(a->nome)", code)

    def test_text_with_box(self):
        code, _ = build(app('        text("62%", width: 44, align: end)'))
        self.assertIn("CLAY_SIZING_FIXED(44)", code)
        self.assertIn("CLAY_ALIGN_X_RIGHT", code)
        self.assertIn('CLAY_STRING("62%")', code)

    def test_c_keywords_are_renamed(self):
        code, _ = build(app('        text("x")', "    var default = 1\n    var int = 2"))
        self.assertIn("int default_;", code)
        self.assertIn("int int_;", code)


class Lint(unittest.TestCase):
    def test_unused_variables_warn_and_c_stays_quiet(self):
        code, warnings = build("fn f(x: int) {\n    text(\"a\")\n}\n" + app("        let y = 3\n        for i, v in xs { f(i) }", "    var xs = [1, 2]"))
        messages = [w[1] for w in warnings]
        self.assertIn("o parâmetro 'x' nunca é usado", messages)
        self.assertIn("'v' nunca é usado", messages)
        self.assertIn("'y' é declarado e nunca usado", messages)
        self.assertIn("(void)x;", code)
        self.assertIn("(void)y;", code)
        self.assertNotIn(" v = ", code)

    def test_unknown_icons_warn(self):
        code, warnings = compile_program(parse(app('        icon("wiif")')), "teste.gvt", icons={"wifi"})
        self.assertEqual(len(warnings), 1)
        self.assertIn("wifi", warnings[0][2])


class Scroll(unittest.TestCase):
    def test_scroll_offset_is_read_with_the_element_open(self):
        code, _ = build(app("        card #c (height: 100, scroll: vertical) { text(\"a\") }\n        column #d (height: 100, scroll: vertical) { text(\"b\") }"))
        self.assertRegex(code, r"CLAY\(_e\d+, \(_d\d+\.clip\.childOffset = Clay_GetScrollOffset\(\), _d\d+\)\)")
        self.assertIn(".childOffset = Clay_GetScrollOffset() }", code)


class Docs(unittest.TestCase):
    """Os programas ```gvt da documentação têm que compilar (os trechos soltos usam ``` sem nome)."""

    def test_doc_programs_compile(self):
        import re
        files = [os.path.join(ROOT, "README.md")] + sorted(glob.glob(os.path.join(ROOT, "docs", "*.md")))
        found = 0
        for path in files:
            with open(path, encoding="utf-8") as f:
                blocks = re.findall(r"```gvt\n(.*?)```", f.read(), re.S)
            for k, block in enumerate(blocks):
                found += 1
                with self.subTest(doc=os.path.basename(path), block=k):
                    build(block)
        self.assertGreater(found, 3)


class Examples(unittest.TestCase):
    def test_examples_compile_without_warnings(self):
        self.assertTrue(EXAMPLES)
        for path in EXAMPLES:
            with self.subTest(path=os.path.basename(path)):
                with open(path, encoding="utf-8") as f:
                    _, warnings = compile_program(parse(f.read()), path)
                self.assertEqual(warnings, [])

    @unittest.skipUnless(os.environ.get("GRAVITY_DIR") and shutil.which("gcc") and shutil.which("pkg-config"),
                         "defina GRAVITY_DIR (e tenha gcc e pkg-config) para compilar de verdade")
    def test_build_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "teste.gvt")
            with open(src, "w", encoding="utf-8") as f:
                f.write(app('        text("View 1", style: title)'))
            r = subprocess.run([os.path.join(ROOT, "bin", "gvt"), "build", src, "--exe"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.access(os.path.join(tmp, "teste"), os.X_OK))

    def test_missing_gravity_is_explained(self):
        env = dict(os.environ, GRAVITY_DIR="/nao/existe")
        r = subprocess.run([os.path.join(ROOT, "bin", "gvt"), "run", os.path.join(ROOT, "examples", "ola.gvt")],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("não achei o Gravity", r.stderr)
        self.assertIn("lumna-mobile", r.stderr)

    @unittest.skipUnless(os.environ.get("GRAVITY_DIR") and shutil.which("gcc") and shutil.which("pkg-config"),
                         "defina GRAVITY_DIR (e tenha gcc e pkg-config) para passar o C pelo gcc")
    def test_generated_c_passes_gcc(self):
        gdir = os.environ["GRAVITY_DIR"]
        pkgs = ["wayland-client", "wayland-cursor", "xkbcommon", "cairo", "pangocairo"]
        cflags = subprocess.run(["pkg-config", "--cflags"] + pkgs, capture_output=True, text=True, check=True).stdout.split()
        with tempfile.TemporaryDirectory() as tmp:
            for path in EXAMPLES:
                with self.subTest(path=os.path.basename(path)):
                    with open(path, encoding="utf-8") as f:
                        code, _ = compile_program(parse(f.read()), path)
                    out = os.path.join(tmp, os.path.basename(path) + ".c")
                    with open(out, "w", encoding="utf-8") as f:
                        f.write(code)
                    r = subprocess.run(["gcc", "-fsyntax-only", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-Wall", "-Wextra",
                                        "-Wno-missing-field-initializers", "-Werror", f"-I{gdir}/src", f"-I{gdir}/vendor/clay",
                                        *cflags, out], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
