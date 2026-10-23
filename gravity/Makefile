# Gravity — a interface do LUMNA OS em C.
#   make            a biblioteca (libgravity.a) e os exemplos
#   make mixer      só o mixer
PKGS = wayland-client wayland-cursor xkbcommon cairo pangocairo
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -D_POSIX_C_SOURCE=200809L -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers \
	-Isrc -Ivendor/clay -I. $(shell pkg-config --cflags $(PKGS))
LDLIBS = $(shell pkg-config --libs $(PKGS)) -lm
WAYLAND_PROTOCOLS = $(shell pkg-config --variable=pkgdatadir wayland-protocols)
WAYLAND_SCANNER = $(shell pkg-config --variable=wayland_scanner wayland-scanner)

FONTES = src/gv_app.c src/gv_texto.c src/gv_tema.c src/gv_anim.c src/gv_svg.c src/gv_icones.c \
	src/gv_desenho.c src/gv_componentes.c src/gv_clay.c
PROTOS = xdg-shell-client-protocol.h xdg-shell-protocol.c \
	wlr-layer-shell-unstable-v1-client-protocol.h wlr-layer-shell-unstable-v1-protocol.c
OBJS = $(FONTES:.c=.o) xdg-shell-protocol.o wlr-layer-shell-unstable-v1-protocol.o

all: libgravity.a mixer galeria

xdg-shell-client-protocol.h:
	$(WAYLAND_SCANNER) client-header $(WAYLAND_PROTOCOLS)/stable/xdg-shell/xdg-shell.xml $@
xdg-shell-protocol.c:
	$(WAYLAND_SCANNER) private-code $(WAYLAND_PROTOCOLS)/stable/xdg-shell/xdg-shell.xml $@
wlr-layer-shell-unstable-v1-client-protocol.h: protocolos/wlr-layer-shell-unstable-v1.xml
	$(WAYLAND_SCANNER) client-header $< $@
wlr-layer-shell-unstable-v1-protocol.c: protocolos/wlr-layer-shell-unstable-v1.xml
	$(WAYLAND_SCANNER) private-code $< $@

src/gv_app.o: xdg-shell-client-protocol.h wlr-layer-shell-unstable-v1-client-protocol.h
$(OBJS): src/gravity.h src/gv_interno.h

# o Clay é de fora: os avisos dele não são nossos
src/gv_clay.o: CFLAGS += -w

libgravity.a: $(OBJS)
	$(AR) rcs $@ $^

mixer: exemplos/mixer.c libgravity.a
	$(CC) $(CFLAGS) -o $@ $< libgravity.a $(LDLIBS)

galeria: exemplos/galeria.c libgravity.a
	$(CC) $(CFLAGS) -o $@ $< libgravity.a $(LDLIBS)

clean:
	rm -f $(OBJS) libgravity.a mixer galeria $(PROTOS)

.PHONY: all clean
