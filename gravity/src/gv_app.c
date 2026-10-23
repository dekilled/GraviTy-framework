/*
 * O Gravity no Wayland: a superfície (janela ou camada), os buffers em memória partilhada, a
 * escala do ecrã, o ponteiro, o toque e o teclado, e o ciclo dos quadros.
 *
 * Um quadro só é desenhado quando algo mudou (entrada, tamanho, uma animação a correr) e ao
 * ritmo do ecrã: depois de cada commit o próximo espera o frame callback do compositor.
 */
#define _GNU_SOURCE
#include "gv_interno.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/input-event-codes.h>
#include <math.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include <wayland-cursor.h>
#include <xkbcommon/xkbcommon.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

#define GV_MAX_SAIDAS 8
#define GV_MAX_VIGIAS 8

struct gv_buffer {
	struct wl_buffer *wl;
	void *dados;
	size_t tamanho;
	int largura, altura; /* em pixels do ecrã */
	bool ocupado;
	cairo_surface_t *superficie;
};

struct gv_saida {
	struct wl_output *wl;
	int escala;
	bool dentro; /* a nossa superfície está nela */
};

struct gv_vigia {
	int fd;
	void (*pronto)(gv_app *app, int fd, void *dados);
	void *dados;
};

struct gv_app {
	gv_opcoes opcoes;
	struct wl_display *display;
	struct wl_registry *registo;
	struct wl_compositor *compositor;
	struct wl_shm *shm;
	struct wl_seat *seat;
	struct xdg_wm_base *xdg;
	struct zwlr_layer_shell_v1 *camadas;
	struct gv_saida saidas[GV_MAX_SAIDAS];
	int nsaidas;

	struct wl_surface *superficie;
	struct xdg_surface *xdg_superficie;
	struct xdg_toplevel *janela;
	struct zwlr_layer_surface_v1 *camada;
	struct wl_callback *quadro_cb;

	struct wl_pointer *ponteiro;
	struct wl_touch *toque;
	struct wl_keyboard *teclado;
	struct wl_cursor_theme *cursores;
	struct wl_surface *cursor_sup;
	uint32_t ponteiro_serial;
	int32_t dedo; /* o dedo que manda (-1: nenhum) */

	struct xkb_context *xkb;
	struct xkb_keymap *mapa;
	struct xkb_state *estado;

	struct gv_buffer buffers[2];
	int largura, altura; /* lógicos */
	int escala;
	bool configurado;
	bool precisa;   /* há algo novo para desenhar */
	bool a_correr;
	int codigo;

	struct gv_vigia vigias[GV_MAX_VIGIAS];
	int nvigias;

	Clay_Arena arena;
	double ultimo_quadro;
};

struct gv_entrada gv__entrada = { .x = -1, .y = -1 };
static gv_app *atual;

double gv_agora(void) {
	static struct timespec inicio;
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	if (!inicio.tv_sec && !inicio.tv_nsec) {
		inicio = t;
	}
	return (t.tv_sec - inicio.tv_sec) + (t.tv_nsec - inicio.tv_nsec) / 1e9;
}

void gv_app_redesenhar(gv_app *app) {
	app->precisa = true;
}

void gv__app_pedir(void) {
	if (atual) {
		atual->precisa = true;
	}
}

float gv_app_largura(gv_app *app) {
	return app->largura;
}

float gv_app_altura(gv_app *app) {
	return app->altura;
}

void gv_app_sair(gv_app *app) {
	app->a_correr = false;
}

void gv_app_vigiar(gv_app *app, int fd, void (*pronto)(gv_app *, int, void *), void *dados) {
	if (app->nvigias >= GV_MAX_VIGIAS) {
		fprintf(stderr, "gravity: mais de %d descritores vigiados\n", GV_MAX_VIGIAS);
		return;
	}
	app->vigias[app->nvigias++] = (struct gv_vigia){ fd, pronto, dados };
}

/* ---- buffers ---- */

static void buffer_libertado(void *dados, struct wl_buffer *wl) {
	struct gv_buffer *buffer = dados;
	buffer->ocupado = false;
	(void)wl;
}

static const struct wl_buffer_listener buffer_ouvinte = { .release = buffer_libertado };

static void buffer_destruir(struct gv_buffer *buffer) {
	if (buffer->superficie) {
		cairo_surface_destroy(buffer->superficie);
	}
	if (buffer->wl) {
		wl_buffer_destroy(buffer->wl);
	}
	if (buffer->dados) {
		munmap(buffer->dados, buffer->tamanho);
	}
	*buffer = (struct gv_buffer){ 0 };
}

static bool buffer_criar(gv_app *app, struct gv_buffer *buffer, int largura, int altura) {
	int passo = cairo_format_stride_for_width(CAIRO_FORMAT_ARGB32, largura);
	size_t tamanho = (size_t)passo * altura;
	int fd = memfd_create("gravity", MFD_CLOEXEC);
	if (fd < 0 || ftruncate(fd, tamanho) < 0) {
		if (fd >= 0) {
			close(fd);
		}
		return false;
	}
	void *dados = mmap(NULL, tamanho, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (dados == MAP_FAILED) {
		close(fd);
		return false;
	}
	struct wl_shm_pool *pool = wl_shm_create_pool(app->shm, fd, tamanho);
	buffer->wl = wl_shm_pool_create_buffer(pool, 0, largura, altura, passo, WL_SHM_FORMAT_ARGB8888);
	wl_shm_pool_destroy(pool);
	close(fd);
	wl_buffer_add_listener(buffer->wl, &buffer_ouvinte, buffer);
	buffer->dados = dados;
	buffer->tamanho = tamanho;
	buffer->largura = largura;
	buffer->altura = altura;
	buffer->superficie = cairo_image_surface_create_for_data(dados, CAIRO_FORMAT_ARGB32, largura, altura, passo);
	return true;
}

static struct gv_buffer *buffer_livre(gv_app *app) {
	int largura = app->largura * app->escala;
	int altura = app->altura * app->escala;
	for (int i = 0; i < 2; i++) {
		struct gv_buffer *buffer = &app->buffers[i];
		if (buffer->ocupado) {
			continue;
		}
		if (buffer->wl && (buffer->largura != largura || buffer->altura != altura)) {
			buffer_destruir(buffer);
		}
		if (!buffer->wl && !buffer_criar(app, buffer, largura, altura)) {
			return NULL;
		}
		return buffer;
	}
	return NULL;
}

/* ---- escala: a maior das saídas onde a superfície está ---- */

static void escala_rever(gv_app *app) {
	int escala = 1;
	for (int i = 0; i < app->nsaidas; i++) {
		if (app->saidas[i].dentro && app->saidas[i].escala > escala) {
			escala = app->saidas[i].escala;
		}
	}
	if (escala != app->escala) {
		app->escala = escala;
		wl_surface_set_buffer_scale(app->superficie, escala);
		if (app->cursores) {
			wl_cursor_theme_destroy(app->cursores);
			app->cursores = NULL;
		}
		app->precisa = true;
	}
}

static void saida_geometria(void *d, struct wl_output *o, int32_t x, int32_t y, int32_t pw, int32_t ph,
		int32_t sub, const char *marca, const char *modelo, int32_t transf) {}
static void saida_modo(void *d, struct wl_output *o, uint32_t f, int32_t w, int32_t h, int32_t r) {}
static void saida_feito(void *d, struct wl_output *o) {}
static void saida_escala(void *dados, struct wl_output *o, int32_t escala) {
	struct gv_saida *saida = dados;
	saida->escala = escala;
	if (atual) {
		escala_rever(atual);
	}
}
static void saida_nome(void *d, struct wl_output *o, const char *n) {}
static void saida_descricao(void *d, struct wl_output *o, const char *n) {}

static const struct wl_output_listener saida_ouvinte = {
	.geometry = saida_geometria,
	.mode = saida_modo,
	.done = saida_feito,
	.scale = saida_escala,
	.name = saida_nome,
	.description = saida_descricao,
};

static void sup_entrou(void *dados, struct wl_surface *s, struct wl_output *wl) {
	gv_app *app = dados;
	for (int i = 0; i < app->nsaidas; i++) {
		if (app->saidas[i].wl == wl) {
			app->saidas[i].dentro = true;
		}
	}
	escala_rever(app);
}

static void sup_saiu(void *dados, struct wl_surface *s, struct wl_output *wl) {
	gv_app *app = dados;
	for (int i = 0; i < app->nsaidas; i++) {
		if (app->saidas[i].wl == wl) {
			app->saidas[i].dentro = false;
		}
	}
	escala_rever(app);
}

static const struct wl_surface_listener sup_ouvinte = { .enter = sup_entrou, .leave = sup_saiu };

/* ---- ponteiro ---- */

static void cursor_aplicar(gv_app *app) {
	if (!app->cursores) {
		app->cursores = wl_cursor_theme_load(getenv("XCURSOR_THEME"), 24 * app->escala, app->shm);
	}
	struct wl_cursor *cursor = app->cursores ? wl_cursor_theme_get_cursor(app->cursores, "default") : NULL;
	if (!cursor && app->cursores) {
		cursor = wl_cursor_theme_get_cursor(app->cursores, "left_ptr");
	}
	if (!cursor) {
		return;
	}
	struct wl_cursor_image *imagem = cursor->images[0];
	if (!app->cursor_sup) {
		app->cursor_sup = wl_compositor_create_surface(app->compositor);
	}
	wl_surface_set_buffer_scale(app->cursor_sup, app->escala);
	wl_surface_attach(app->cursor_sup, wl_cursor_image_get_buffer(imagem), 0, 0);
	wl_surface_damage_buffer(app->cursor_sup, 0, 0, INT32_MAX, INT32_MAX);
	wl_surface_commit(app->cursor_sup);
	wl_pointer_set_cursor(app->ponteiro, app->ponteiro_serial, app->cursor_sup,
		imagem->hotspot_x / app->escala, imagem->hotspot_y / app->escala);
}

static void ponteiro_entrou(void *dados, struct wl_pointer *p, uint32_t serial, struct wl_surface *s,
		wl_fixed_t x, wl_fixed_t y) {
	gv_app *app = dados;
	app->ponteiro_serial = serial;
	gv__entrada.x = wl_fixed_to_double(x);
	gv__entrada.y = wl_fixed_to_double(y);
	gv__entrada.toque = false;
	cursor_aplicar(app);
	app->precisa = true;
}

static void ponteiro_saiu(void *dados, struct wl_pointer *p, uint32_t serial, struct wl_surface *s) {
	gv_app *app = dados;
	if (!gv__entrada.baixo) {
		gv__entrada.x = gv__entrada.y = -1;
	}
	app->precisa = true;
}

static void ponteiro_moveu(void *dados, struct wl_pointer *p, uint32_t t, wl_fixed_t x, wl_fixed_t y) {
	gv_app *app = dados;
	gv__entrada.x = wl_fixed_to_double(x);
	gv__entrada.y = wl_fixed_to_double(y);
	gv__entrada.toque = false;
	app->precisa = true;
}

static void ponteiro_botao(void *dados, struct wl_pointer *p, uint32_t serial, uint32_t t, uint32_t botao,
		uint32_t estado) {
	gv_app *app = dados;
	if (botao != BTN_LEFT) {
		return;
	}
	if (estado == WL_POINTER_BUTTON_STATE_PRESSED) {
		gv__entrada.baixo = true;
		gv__entrada.apertou = true;
	} else {
		gv__entrada.baixo = false;
		gv__entrada.soltou = true;
	}
	app->precisa = true;
}

static void ponteiro_eixo(void *dados, struct wl_pointer *p, uint32_t t, uint32_t eixo, wl_fixed_t valor) {
	gv_app *app = dados;
	if (eixo == WL_POINTER_AXIS_VERTICAL_SCROLL) {
		gv__entrada.roda_y -= wl_fixed_to_double(valor);
	} else {
		gv__entrada.roda_x -= wl_fixed_to_double(valor);
	}
	app->precisa = true;
}

static void ponteiro_quadro(void *d, struct wl_pointer *p) {}
static void ponteiro_fonte(void *d, struct wl_pointer *p, uint32_t f) {}
static void ponteiro_parou(void *d, struct wl_pointer *p, uint32_t t, uint32_t e) {}
static void ponteiro_discreto(void *d, struct wl_pointer *p, uint32_t e, int32_t v) {}
static void ponteiro_v120(void *d, struct wl_pointer *p, uint32_t e, int32_t v) {}
static void ponteiro_direcao(void *d, struct wl_pointer *p, uint32_t e, uint32_t dir) {}

static const struct wl_pointer_listener ponteiro_ouvinte = {
	.enter = ponteiro_entrou,
	.leave = ponteiro_saiu,
	.motion = ponteiro_moveu,
	.button = ponteiro_botao,
	.axis = ponteiro_eixo,
	.frame = ponteiro_quadro,
	.axis_source = ponteiro_fonte,
	.axis_stop = ponteiro_parou,
	.axis_discrete = ponteiro_discreto,
	.axis_value120 = ponteiro_v120,
	.axis_relative_direction = ponteiro_direcao,
};

/* ---- toque: o primeiro dedo faz de ponteiro (os gestos de vários dedos ficam para depois) ---- */

static void toque_baixo(void *dados, struct wl_touch *t, uint32_t serial, uint32_t tempo, struct wl_surface *s,
		int32_t id, wl_fixed_t x, wl_fixed_t y) {
	gv_app *app = dados;
	if (app->dedo >= 0) {
		return;
	}
	app->dedo = id;
	gv__entrada.x = wl_fixed_to_double(x);
	gv__entrada.y = wl_fixed_to_double(y);
	gv__entrada.baixo = true;
	gv__entrada.apertou = true;
	gv__entrada.toque = true;
	app->precisa = true;
}

static void toque_cima(void *dados, struct wl_touch *t, uint32_t serial, uint32_t tempo, int32_t id) {
	gv_app *app = dados;
	if (id != app->dedo) {
		return;
	}
	app->dedo = -1;
	gv__entrada.baixo = false;
	gv__entrada.soltou = true;
	app->precisa = true;
}

static void toque_moveu(void *dados, struct wl_touch *t, uint32_t tempo, int32_t id, wl_fixed_t x, wl_fixed_t y) {
	gv_app *app = dados;
	if (id != app->dedo) {
		return;
	}
	gv__entrada.x = wl_fixed_to_double(x);
	gv__entrada.y = wl_fixed_to_double(y);
	app->precisa = true;
}

static void toque_quadro(void *d, struct wl_touch *t) {}

static void toque_cancelado(void *dados, struct wl_touch *t) {
	gv_app *app = dados;
	app->dedo = -1;
	gv__entrada.baixo = false;
	gv__entrada.ativo = 0;
	gv__entrada.x = gv__entrada.y = -1;
	app->precisa = true;
}

static void toque_forma(void *d, struct wl_touch *t, int32_t id, wl_fixed_t a, wl_fixed_t b) {}
static void toque_orientacao(void *d, struct wl_touch *t, int32_t id, wl_fixed_t o) {}

static const struct wl_touch_listener toque_ouvinte = {
	.down = toque_baixo,
	.up = toque_cima,
	.motion = toque_moveu,
	.frame = toque_quadro,
	.cancel = toque_cancelado,
	.shape = toque_forma,
	.orientation = toque_orientacao,
};

/* ---- teclado ---- */

static void teclado_mapa(void *dados, struct wl_keyboard *k, uint32_t formato, int32_t fd, uint32_t tamanho) {
	gv_app *app = dados;
	if (formato != WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1) {
		close(fd);
		return;
	}
	char *texto = mmap(NULL, tamanho, PROT_READ, MAP_PRIVATE, fd, 0);
	close(fd);
	if (texto == MAP_FAILED) {
		return;
	}
	struct xkb_keymap *mapa = xkb_keymap_new_from_string(app->xkb, texto, XKB_KEYMAP_FORMAT_TEXT_V1,
		XKB_KEYMAP_COMPILE_NO_FLAGS);
	munmap(texto, tamanho);
	if (!mapa) {
		return;
	}
	if (app->estado) {
		xkb_state_unref(app->estado);
	}
	if (app->mapa) {
		xkb_keymap_unref(app->mapa);
	}
	app->mapa = mapa;
	app->estado = xkb_state_new(mapa);
}

static void teclado_entrou(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sup, struct wl_array *t) {}
static void teclado_saiu(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sup) {}

static void teclado_tecla(void *dados, struct wl_keyboard *k, uint32_t serial, uint32_t tempo, uint32_t tecla,
		uint32_t estado) {
	gv_app *app = dados;
	if (estado != WL_KEYBOARD_KEY_STATE_PRESSED || !app->estado) {
		return;
	}
	gv__entrada.tecla = xkb_state_key_get_one_sym(app->estado, tecla + 8);
	app->precisa = true;
}

static void teclado_mods(void *dados, struct wl_keyboard *k, uint32_t serial, uint32_t baixo, uint32_t preso,
		uint32_t trancado, uint32_t grupo) {
	gv_app *app = dados;
	if (app->estado) {
		xkb_state_update_mask(app->estado, baixo, preso, trancado, 0, 0, grupo);
	}
}

static void teclado_repete(void *d, struct wl_keyboard *k, int32_t taxa, int32_t atraso) {}

static const struct wl_keyboard_listener teclado_ouvinte = {
	.keymap = teclado_mapa,
	.enter = teclado_entrou,
	.leave = teclado_saiu,
	.key = teclado_tecla,
	.modifiers = teclado_mods,
	.repeat_info = teclado_repete,
};

static void seat_capacidades(void *dados, struct wl_seat *seat, uint32_t caps) {
	gv_app *app = dados;
	if ((caps & WL_SEAT_CAPABILITY_POINTER) && !app->ponteiro) {
		app->ponteiro = wl_seat_get_pointer(seat);
		wl_pointer_add_listener(app->ponteiro, &ponteiro_ouvinte, app);
	} else if (!(caps & WL_SEAT_CAPABILITY_POINTER) && app->ponteiro) {
		wl_pointer_release(app->ponteiro);
		app->ponteiro = NULL;
	}
	if ((caps & WL_SEAT_CAPABILITY_TOUCH) && !app->toque) {
		app->toque = wl_seat_get_touch(seat);
		wl_touch_add_listener(app->toque, &toque_ouvinte, app);
	} else if (!(caps & WL_SEAT_CAPABILITY_TOUCH) && app->toque) {
		wl_touch_release(app->toque);
		app->toque = NULL;
	}
	if ((caps & WL_SEAT_CAPABILITY_KEYBOARD) && !app->teclado) {
		app->teclado = wl_seat_get_keyboard(seat);
		wl_keyboard_add_listener(app->teclado, &teclado_ouvinte, app);
	} else if (!(caps & WL_SEAT_CAPABILITY_KEYBOARD) && app->teclado) {
		wl_keyboard_release(app->teclado);
		app->teclado = NULL;
	}
}

static void seat_nome(void *d, struct wl_seat *s, const char *n) {}

static const struct wl_seat_listener seat_ouvinte = { .capabilities = seat_capacidades, .name = seat_nome };

/* ---- registo ---- */

static void xdg_ping(void *d, struct xdg_wm_base *xdg, uint32_t serial) {
	xdg_wm_base_pong(xdg, serial);
}

static const struct xdg_wm_base_listener xdg_ouvinte = { .ping = xdg_ping };

static void registo_global(void *dados, struct wl_registry *r, uint32_t nome, const char *iface, uint32_t versao) {
	gv_app *app = dados;
	if (!strcmp(iface, wl_compositor_interface.name)) {
		app->compositor = wl_registry_bind(r, nome, &wl_compositor_interface, versao < 4 ? versao : 4);
	} else if (!strcmp(iface, wl_shm_interface.name)) {
		app->shm = wl_registry_bind(r, nome, &wl_shm_interface, 1);
	} else if (!strcmp(iface, wl_seat_interface.name) && !app->seat) {
		app->seat = wl_registry_bind(r, nome, &wl_seat_interface, versao < 8 ? versao : 8);
		wl_seat_add_listener(app->seat, &seat_ouvinte, app);
	} else if (!strcmp(iface, xdg_wm_base_interface.name)) {
		app->xdg = wl_registry_bind(r, nome, &xdg_wm_base_interface, 1);
		xdg_wm_base_add_listener(app->xdg, &xdg_ouvinte, app);
	} else if (!strcmp(iface, zwlr_layer_shell_v1_interface.name)) {
		app->camadas = wl_registry_bind(r, nome, &zwlr_layer_shell_v1_interface, versao < 4 ? versao : 4);
	} else if (!strcmp(iface, wl_output_interface.name) && app->nsaidas < GV_MAX_SAIDAS) {
		struct gv_saida *saida = &app->saidas[app->nsaidas++];
		saida->escala = 1;
		saida->wl = wl_registry_bind(r, nome, &wl_output_interface, versao < 4 ? versao : 4);
		wl_output_add_listener(saida->wl, &saida_ouvinte, saida);
	}
}

static void registo_saiu(void *d, struct wl_registry *r, uint32_t nome) {}

static const struct wl_registry_listener registo_ouvinte = { .global = registo_global, .global_remove = registo_saiu };

/* ---- a superfície ---- */

static void tamanho_novo(gv_app *app, int largura, int altura) {
	if (largura > 0) {
		app->largura = largura;
	}
	if (altura > 0) {
		app->altura = altura;
	}
	app->configurado = true;
	app->precisa = true;
}

static void xdg_sup_configurar(void *dados, struct xdg_surface *s, uint32_t serial) {
	xdg_surface_ack_configure(s, serial);
	gv_app *app = dados;
	app->configurado = true;
	app->precisa = true;
}

static const struct xdg_surface_listener xdg_sup_ouvinte = { .configure = xdg_sup_configurar };

static void janela_configurar(void *dados, struct xdg_toplevel *j, int32_t largura, int32_t altura,
		struct wl_array *estados) {
	tamanho_novo(dados, largura, altura);
}

static void janela_fechar(void *dados, struct xdg_toplevel *j) {
	gv_app_sair(dados);
}

static void janela_limites(void *d, struct xdg_toplevel *j, int32_t w, int32_t h) {}
static void janela_capacidades(void *d, struct xdg_toplevel *j, struct wl_array *c) {}

static const struct xdg_toplevel_listener janela_ouvinte = {
	.configure = janela_configurar,
	.close = janela_fechar,
	.configure_bounds = janela_limites,
	.wm_capabilities = janela_capacidades,
};

static void camada_configurar(void *dados, struct zwlr_layer_surface_v1 *c, uint32_t serial, uint32_t largura,
		uint32_t altura) {
	zwlr_layer_surface_v1_ack_configure(c, serial);
	tamanho_novo(dados, largura, altura);
}

static void camada_fechar(void *dados, struct zwlr_layer_surface_v1 *c) {
	gv_app_sair(dados);
}

static const struct zwlr_layer_surface_v1_listener camada_ouvinte = {
	.configure = camada_configurar,
	.closed = camada_fechar,
};

static void quadro_pronto(void *dados, struct wl_callback *cb, uint32_t tempo) {
	gv_app *app = dados;
	wl_callback_destroy(cb);
	app->quadro_cb = NULL;
}

static const struct wl_callback_listener quadro_ouvinte = { .done = quadro_pronto };

static void clay_erro(Clay_ErrorData erro) {
	fprintf(stderr, "gravity: layout: %.*s\n", erro.errorText.length, erro.errorText.chars);
}

gv_app *gv_app_criar(const gv_opcoes *opcoes) {
	gv_app *app = calloc(1, sizeof(*app));
	if (!app) {
		return NULL;
	}
	app->opcoes = *opcoes;
	app->escala = 1;
	app->dedo = -1;
	app->largura = opcoes->largura > 0 ? opcoes->largura : 480;
	app->altura = opcoes->altura > 0 ? opcoes->altura : 640;
	atual = app;

	gv_tema_padrao(&gv_t);
	gv_tema_carregar(NULL);
	gv__texto_iniciar();

	app->display = wl_display_connect(NULL);
	if (!app->display) {
		fprintf(stderr, "gravity: sem compositor Wayland (WAYLAND_DISPLAY)\n");
		free(app);
		return NULL;
	}
	app->xkb = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
	app->registo = wl_display_get_registry(app->display);
	wl_registry_add_listener(app->registo, &registo_ouvinte, app);
	wl_display_roundtrip(app->display);
	wl_display_roundtrip(app->display);
	if (!app->compositor || !app->shm) {
		fprintf(stderr, "gravity: o compositor não tem wl_compositor/wl_shm\n");
		free(app);
		return NULL;
	}

	app->superficie = wl_compositor_create_surface(app->compositor);
	wl_surface_add_listener(app->superficie, &sup_ouvinte, app);
	if (opcoes->tipo == GV_CAMADA) {
		if (!app->camadas) {
			fprintf(stderr, "gravity: o compositor não tem layer-shell; abrindo como janela\n");
			app->opcoes.tipo = GV_JANELA;
		} else {
			app->camada = zwlr_layer_shell_v1_get_layer_surface(app->camadas, app->superficie, NULL,
				opcoes->nivel, opcoes->app_id ? opcoes->app_id : "gravity");
			zwlr_layer_surface_v1_add_listener(app->camada, &camada_ouvinte, app);
			zwlr_layer_surface_v1_set_size(app->camada, opcoes->largura > 0 ? opcoes->largura : 0,
				opcoes->altura > 0 ? opcoes->altura : 0);
			zwlr_layer_surface_v1_set_anchor(app->camada, opcoes->ancoras);
			zwlr_layer_surface_v1_set_exclusive_zone(app->camada, opcoes->zona_exclusiva);
			zwlr_layer_surface_v1_set_keyboard_interactivity(app->camada,
				opcoes->teclado ? ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_ON_DEMAND
						: ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
		}
	}
	if (app->opcoes.tipo == GV_JANELA) {
		if (!app->xdg) {
			fprintf(stderr, "gravity: o compositor não tem xdg-shell\n");
			free(app);
			return NULL;
		}
		app->xdg_superficie = xdg_wm_base_get_xdg_surface(app->xdg, app->superficie);
		xdg_surface_add_listener(app->xdg_superficie, &xdg_sup_ouvinte, app);
		app->janela = xdg_surface_get_toplevel(app->xdg_superficie);
		xdg_toplevel_add_listener(app->janela, &janela_ouvinte, app);
		xdg_toplevel_set_title(app->janela, opcoes->titulo ? opcoes->titulo : "Gravity");
		xdg_toplevel_set_app_id(app->janela, opcoes->app_id ? opcoes->app_id : "gravity");
	}
	wl_surface_commit(app->superficie);

	uint32_t memoria = Clay_MinMemorySize();
	app->arena = Clay_CreateArenaWithCapacityAndMemory(memoria, malloc(memoria));
	Clay_Initialize(app->arena, (Clay_Dimensions){ app->largura, app->altura }, (Clay_ErrorHandler){ .errorHandlerFunction = clay_erro });
	Clay_SetMeasureTextFunction(gv__texto_medir, NULL);
	app->precisa = true;
	return app;
}

/* ---- o quadro ---- */

static void desenhar_quadro(gv_app *app, gv_desenho desenhar, void *dados) {
	struct gv_buffer *buffer = buffer_livre(app);
	if (!buffer) {
		return; /* os dois ainda no compositor: fica para o próximo */
	}
	double agora = gv_agora();
	float dt = app->ultimo_quadro > 0 ? (float)(agora - app->ultimo_quadro) : 0.016f;
	app->ultimo_quadro = agora;
	app->precisa = false;

	gv__anim_quadro();
	Clay_SetLayoutDimensions((Clay_Dimensions){ app->largura, app->altura });
	Clay_SetPointerState((Clay_Vector2){ gv__entrada.x, gv__entrada.y }, gv__entrada.baixo || gv__entrada.apertou);
	Clay_UpdateScrollContainers(gv__entrada.toque, (Clay_Vector2){ gv__entrada.roda_x * 2, gv__entrada.roda_y * 2 }, dt);
	Clay_BeginLayout();
	desenhar(app, dados);
	Clay_RenderCommandArray comandos = Clay_EndLayout(dt);

	cairo_t *cr = cairo_create(buffer->superficie);
	cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
	cairo_set_source_rgba(cr, 0, 0, 0, 0);
	cairo_paint(cr);
	cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
	cairo_scale(cr, app->escala, app->escala);
	gv__desenhar(cr, comandos);
	cairo_destroy(cr);
	cairo_surface_flush(buffer->superficie);

	gv__entrada_fim_do_quadro();
	gv__quadro_limpar();

	wl_surface_attach(app->superficie, buffer->wl, 0, 0);
	wl_surface_damage_buffer(app->superficie, 0, 0, INT32_MAX, INT32_MAX);
	app->quadro_cb = wl_surface_frame(app->superficie);
	wl_callback_add_listener(app->quadro_cb, &quadro_ouvinte, app);
	wl_surface_commit(app->superficie);
	buffer->ocupado = true;
}

int gv_app_correr(gv_app *app, gv_desenho desenhar, void *dados) {
	app->a_correr = true;
	struct pollfd fds[1 + GV_MAX_VIGIAS];
	while (app->a_correr) {
		if (app->precisa && app->configurado && !app->quadro_cb) {
			desenhar_quadro(app, desenhar, dados);
		}
		while (wl_display_prepare_read(app->display) != 0) {
			wl_display_dispatch_pending(app->display);
		}
		if (wl_display_flush(app->display) < 0 && errno != EAGAIN) {
			wl_display_cancel_read(app->display);
			break;
		}
		fds[0] = (struct pollfd){ .fd = wl_display_get_fd(app->display), .events = POLLIN };
		for (int i = 0; i < app->nvigias; i++) {
			fds[1 + i] = (struct pollfd){ .fd = app->vigias[i].fd, .events = POLLIN };
		}
		/* com um quadro por desenhar mas à espera do compositor, o poll acorda com o callback */
		int espera = (app->precisa && app->configurado && !app->quadro_cb) ? 0 : -1;
		if (poll(fds, 1 + app->nvigias, espera) < 0 && errno != EINTR) {
			wl_display_cancel_read(app->display);
			break;
		}
		if (fds[0].revents & POLLIN) {
			if (wl_display_read_events(app->display) < 0) {
				break;
			}
		} else {
			wl_display_cancel_read(app->display);
		}
		if (wl_display_dispatch_pending(app->display) < 0) {
			break;
		}
		for (int i = 0; i < app->nvigias; i++) {
			if (fds[1 + i].revents & (POLLIN | POLLHUP)) {
				app->vigias[i].pronto(app, app->vigias[i].fd, app->vigias[i].dados);
				app->precisa = true;
			}
		}
	}
	for (int i = 0; i < 2; i++) {
		buffer_destruir(&app->buffers[i]);
	}
	wl_display_disconnect(app->display);
	return app->codigo;
}
