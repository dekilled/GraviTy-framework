"""gvt: o compilador do GraviTy.

    gvt build app.gvt              escreve app.c ao lado
    gvt build app.gvt -o out/app.c
    gvt check app.gvt              só procura erros (para o editor e o CI)
    gvt version
"""

import argparse
import os
import sys

from . import __version__
from .compiler import compile_program, load_icons
from .errors import GvtError, Source
from .parser import parse


def compile_file(path, gravity_dir=None):
    """(código C, avisos, Source) de um .gvt; GvtError se houver erro."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    src = Source(path, text)
    try:
        program = parse(text)
        icons = load_icons(gravity_dir) if gravity_dir else None
        code, warnings = compile_program(program, path, icons)
    except GvtError as e:
        e.source = src
        raise
    return code, warnings, src


def report(src, warnings):
    for pos, message, hint in warnings:
        print(src.format(pos, "aviso", message, hint), file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gvt", description="GraviTy: UI em .gvt, compilada para C (Gravity).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="compila um .gvt para C")
    b.add_argument("file")
    b.add_argument("-o", "--output", help="o arquivo .c (se não disser, ao lado do .gvt)")
    c = sub.add_parser("check", help="só procura erros")
    c.add_argument("files", nargs="+")
    for p in (b, c):
        p.add_argument("--gravity", default=os.environ.get("GRAVITY_DIR"),
                       help="a pasta do Gravity, para conferir os nomes dos ícones (ou GRAVITY_DIR)")
    sub.add_parser("version", help="mostra a versão")
    args = ap.parse_args(argv)

    if args.cmd == "version":
        print(f"gvt {__version__}")
        return 0

    files = [args.file] if args.cmd == "build" else args.files
    status = 0
    for path in files:
        try:
            code, warnings, src = compile_file(path, args.gravity)
        except FileNotFoundError:
            print(f"gvt: não encontrei {path}", file=sys.stderr)
            status = 1
            continue
        except GvtError as e:
            print(e.source.format(e.pos, "erro", e.message, e.hint), file=sys.stderr)
            status = 1
            continue
        report(src, warnings)
        if args.cmd == "build":
            out = args.output or os.path.splitext(path)[0] + ".c"
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(code)
    return status


if __name__ == "__main__":
    sys.exit(main())
