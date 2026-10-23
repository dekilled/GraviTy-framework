"""gvt: o compilador do GraviTy.

    gvt run app.gvt                compila e abre o app (o jeito mais fácil)
    gvt run app.gvt -- --camada    passa argumentos para o app
    gvt build app.gvt --exe        gera o executável app ao lado
    gvt build app.gvt              só gera app.c ao lado
    gvt build app.gvt -o out/app.c
    gvt check app.gvt              só procura erros (para o editor e o CI)
    gvt version

O Gravity é o que vem com o framework (gravity/). Para usar outro: --gravity ou GRAVITY_DIR.
"""

import argparse
import os
import sys
import tempfile

from . import __version__
from .compiler import compile_program, load_icons
from .errors import GvtError, Source
from .native import NativeError, build_exe, check_session, find_gravity
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


def fail(message, hint=None):
    print(f"gvt: erro: {message}", file=sys.stderr)
    if hint:
        print(f"  dica: {hint}", file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gvt", description="GraviTy: UI em .gvt, compilada para C (Gravity).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="compila e abre o app")
    r.add_argument("file")
    r.add_argument("args", nargs="*", help="argumentos para o app, depois de --: gvt run app.gvt -- --camada")
    b = sub.add_parser("build", help="compila um .gvt para C (ou, com --exe, para um executável)")
    b.add_argument("file")
    b.add_argument("-o", "--output", help="o arquivo de saída (se não disser, ao lado do .gvt)")
    b.add_argument("--exe", action="store_true", help="gera o executável, não só o C")
    c = sub.add_parser("check", help="só procura erros")
    c.add_argument("files", nargs="+")
    for p in (r, b, c):
        p.add_argument("--gravity", default=os.environ.get("GRAVITY_DIR"),
                       help="outra pasta do Gravity (por padrão, a gravity/ do framework)")
    sub.add_parser("version", help="mostra a versão")
    args = ap.parse_args(argv)

    if args.cmd == "version":
        print(f"gvt {__version__}")
        return 0

    native = args.cmd == "run" or (args.cmd == "build" and args.exe)
    files = args.files if args.cmd == "check" else [args.file]
    status = 0
    try:
        gdir = find_gravity(args.gravity)
    except NativeError as e:
        if native:
            return fail(e.message, e.hint)
        gdir = None  # para só gerar o C não precisa do Gravity (perde-se só a conferência dos ícones)
    for path in files:
        try:
            code, warnings, src = compile_file(path, gdir)
        except FileNotFoundError:
            print(f"gvt: não encontrei {path}", file=sys.stderr)
            status = 1
            continue
        except GvtError as e:
            print(e.source.format(e.pos, "erro", e.message, e.hint), file=sys.stderr)
            status = 1
            continue
        report(src, warnings)
        base = os.path.splitext(path)[0]

        if args.cmd == "build" and not args.exe:
            out = args.output or base + ".c"
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(code)
            continue

        if native:
            exe = os.path.abspath(args.output if args.cmd == "build" and args.output else base)
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    c_file = os.path.join(tmp, os.path.basename(base) + ".c")
                    with open(c_file, "w", encoding="utf-8") as f:
                        f.write(code)
                    build_exe(c_file, exe, gdir)
                if args.cmd == "run":
                    check_session()
            except NativeError as e:
                return fail(e.message, e.hint)
            if args.cmd == "build":
                print(f"gvt: pronto: {os.path.relpath(exe)}")
                continue
            sys.stdout.flush()
            os.execv(exe, [exe] + args.args)
    return status


if __name__ == "__main__":
    sys.exit(main())
