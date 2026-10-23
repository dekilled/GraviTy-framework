"""Do C gerado ao executável: compila a libgravity se precisar e chama o cc.

É o que o `gvt run` e o `gvt build --exe` usam, para ninguém ter que montar a linha do gcc à mão.
"""

import os
import shutil
import subprocess

PKGS = ["wayland-client", "wayland-cursor", "xkbcommon", "cairo", "pangocairo"]

# o nome do pacote de cada biblioteca, para dizer o que instalar
INSTALL = {
    "arch": "sudo pacman -S --needed wayland wayland-protocols libxkbcommon cairo pango pkgconf",
    "debian": "sudo apt install libwayland-dev wayland-protocols libxkbcommon-dev libcairo2-dev libpango1.0-dev pkg-config",
    "fedora": "sudo dnf install wayland-devel wayland-protocols-devel libxkbcommon-devel cairo-devel pango-devel pkgconf",
}


class NativeError(Exception):
    """Um problema fora do .gvt (falta o Gravity, uma biblioteca, o compilador...), com o que fazer."""

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint


def distro():
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            text = f.read().lower()
    except OSError:
        return None
    for name, keys in (("arch", ("arch", "manjaro", "endeavour", "cachy")), ("debian", ("debian", "ubuntu", "mint", "pop")),
                       ("fedora", ("fedora",))):
        if any(f"id={k}" in text or f"id_like={k}" in text or f"id_like=\"{k}" in text for k in keys):
            return name
    return None


def install_hint():
    d = distro()
    if d:
        return INSTALL[d]
    return "instale wayland, wayland-protocols, libxkbcommon, cairo e pango (os pacotes -dev/-devel) e o pkg-config"


BUNDLED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gravity")


def find_gravity(given=None):
    """A pasta do Gravity: a que vem com o GraviTy-framework, ou outra em --gravity / GRAVITY_DIR."""
    path = given or BUNDLED
    if os.path.isfile(os.path.join(path, "src", "gravity.h")):
        return os.path.abspath(path)
    if given:
        raise NativeError(f"não achei o Gravity em '{given}' (falta src/gravity.h)",
                          "sem --gravity nem GRAVITY_DIR, o gvt usa o Gravity que vem com o framework (a pasta gravity/)")
    raise NativeError("não achei a pasta gravity/ do framework",
                      "ela vem junto no repositório GraviTy-framework: clone de novo, ou rode git checkout -- gravity")


def check_tools():
    cc = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise NativeError("não achei um compilador de C (cc, gcc ou clang)", install_hint().replace(" pkgconf", " gcc pkgconf"))
    if not shutil.which("pkg-config") and not shutil.which("pkgconf"):
        raise NativeError("não achei o pkg-config", install_hint())
    if not shutil.which("make"):
        raise NativeError("não achei o make (para compilar a libgravity)", "instale o make (no Arch: sudo pacman -S make)")
    missing = [p for p in PKGS if subprocess.run(["pkg-config", "--exists", p]).returncode != 0]
    if missing:
        raise NativeError(f"faltam bibliotecas do Gravity: {', '.join(missing)}", install_hint())
    return cc


def pkg(flag):
    r = subprocess.run(["pkg-config", flag] + PKGS, capture_output=True, text=True, check=True)
    return r.stdout.split()


def ensure_libgravity(gdir, quiet=False):
    """Compila a libgravity.a (com o Makefile do Gravity) se ela não existe ou ficou velha."""
    lib = os.path.join(gdir, "libgravity.a")
    srcdir = os.path.join(gdir, "src")
    newest = max(os.path.getmtime(os.path.join(srcdir, f)) for f in os.listdir(srcdir))
    if os.path.exists(lib) and os.path.getmtime(lib) >= newest:
        return lib
    if not quiet:
        print("gvt: compilando a libgravity (só na primeira vez)...", flush=True)
    r = subprocess.run(["make", "-C", gdir, "libgravity.a"], capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
        raise NativeError(f"a libgravity não compilou:\n{tail}", install_hint())
    return lib


def build_exe(c_file, exe, gdir, quiet=False):
    cc = check_tools()
    lib = ensure_libgravity(gdir, quiet)
    cmd = [cc, "-O2", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-Wall", "-Wextra", "-Wno-missing-field-initializers",
           f"-I{gdir}/src", f"-I{gdir}/vendor/clay", *pkg("--cflags"), "-o", exe, c_file, lib, *pkg("--libs"), "-lm"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise NativeError(f"o C gerado não compilou (isto é bug do GraviTy, não seu):\n{r.stderr.strip()}",
                          "guarde o .gvt e esta mensagem e abra uma issue no GraviTy-framework")
    if r.stderr.strip() and not quiet:
        print(r.stderr.strip())
    return exe


def check_session():
    if not os.environ.get("WAYLAND_DISPLAY"):
        hint = "o Gravity desenha direto no Wayland: rode de dentro do Hyprland, Sway, GNOME, KDE (sessão Wayland) ou do Orbit"
        if os.environ.get("DISPLAY"):
            hint += ". Você está numa sessão X11: no login, escolha a sessão Wayland"
        raise NativeError("não há sessão Wayland aberta (WAYLAND_DISPLAY está vazio)", hint)
