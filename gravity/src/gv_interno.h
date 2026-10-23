/* O que as partes do Gravity dividem entre si (as apps usam só o gravity.h). */
#ifndef GV_INTERNO_H
#define GV_INTERNO_H

#include <cairo.h>
#include <stddef.h>

#include "gravity.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ---- memória do quadro: textos e dados dos elementos, apagada a cada quadro ---- */
void *gv__quadro_alloc(size_t tamanho);
void gv__quadro_limpar(void);

/* ---- entrada do quadro (gv_app.c enche, os componentes lêem) ---- */
struct gv_entrada {
	float x, y;         /* ponteiro ou dedo, em pixels lógicos */
	bool baixo;         /* botão ou dedo em baixo agora */
	bool apertou;       /* desceu desde o último quadro */
	bool soltou;        /* subiu desde o último quadro */
	bool toque;         /* o último a mexer foi um dedo */
	uint32_t ativo;     /* o id que recebeu o aperto (0: nenhum) */
	uint32_t tecla;     /* keysym carregado neste quadro */
	float roda_x, roda_y;
};
extern struct gv_entrada gv__entrada;
void gv__entrada_fim_do_quadro(void);
void gv__app_pedir(void); /* o quadro actual pede outro (animação a correr) */

/* ---- o que vai pendurado nos elementos, para o desenho ---- */
enum gv_extra_tipo {
	GV_EXTRA_SOMBRA = 1,
	GV_EXTRA_ICONE,
	GV_EXTRA_DESLIZANTE,
	GV_EXTRA_INTERRUPTOR,
};

struct gv_extra {
	enum gv_extra_tipo tipo;
	union {
		struct {
			float desfoque, desloca_y, alfa;
		} sombra;
		struct {
			const char *caminho; /* o "d" do SVG, em 24 × 24 */
			Clay_Color cor;
			float traco;
		} icone;
		struct {
			float valor; /* 0..1 */
			float trilho, puxador;
			Clay_Color cheio, vazio, cor_puxador;
			float realce; /* 0..1: o puxador cresce um pouco ao arrastar */
		} deslizante;
		struct {
			float posicao; /* 0 desligado .. 1 ligado (animado) */
			Clay_Color fundo, bolinha;
		} interruptor;
	};
};

/* ---- texto (pango) ---- */
void gv__texto_iniciar(void);
Clay_Dimensions gv__texto_medir(Clay_StringSlice texto, Clay_TextElementConfig *config, void *dados);
void gv__texto_desenhar(cairo_t *cr, Clay_RenderCommand *cmd);

/* ---- ícones ---- */
const char *gv__icone_caminho(const char *nome);
/* Traça o caminho SVG (só o "d") no cairo; quem chama faz o stroke. */
bool gv__svg_tracar(cairo_t *cr, const char *d);

/* ---- desenho ---- */
void gv__desenhar(cairo_t *cr, Clay_RenderCommandArray comandos);

/* ---- animações ---- */
void gv__anim_quadro(void);

#endif
