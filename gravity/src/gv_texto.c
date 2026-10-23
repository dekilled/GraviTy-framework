/*
 * Texto: o pango mede e desenha (acentos, emoji, ligaduras, a fonte do tema). O Clay só sabe
 * de tamanhos; o peso vai no fontId (gv_peso).
 */
#include "gv_interno.h"

#include <pango/pangocairo.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- memória do quadro ---- */

#define GV_QUADRO_BLOCO (256 * 1024)

struct bloco {
	struct bloco *seguinte;
	size_t usado, capacidade;
	char dados[];
};

static struct bloco *blocos;

void *gv__quadro_alloc(size_t tamanho) {
	tamanho = (tamanho + 15) & ~(size_t)15;
	if (!blocos || blocos->usado + tamanho > blocos->capacidade) {
		size_t capacidade = tamanho > GV_QUADRO_BLOCO ? tamanho : GV_QUADRO_BLOCO;
		struct bloco *novo = malloc(sizeof(*novo) + capacidade);
		if (!novo) {
			return NULL;
		}
		novo->seguinte = blocos;
		novo->usado = 0;
		novo->capacidade = capacidade;
		blocos = novo;
	}
	void *p = blocos->dados + blocos->usado;
	blocos->usado += tamanho;
	return p;
}

void gv__quadro_limpar(void) {
	/* fica o bloco mais recente (o tamanho de um quadro normal), os outros saem */
	if (!blocos) {
		return;
	}
	struct bloco *b = blocos->seguinte;
	while (b) {
		struct bloco *s = b->seguinte;
		free(b);
		b = s;
	}
	blocos->seguinte = NULL;
	blocos->usado = 0;
}

Clay_String gv_str(const char *texto) {
	size_t n = texto ? strlen(texto) : 0;
	char *copia = gv__quadro_alloc(n + 1);
	if (!copia) {
		return (Clay_String){ 0 };
	}
	memcpy(copia, texto ? texto : "", n + 1);
	return (Clay_String){ .length = (int32_t)n, .chars = copia };
}

Clay_String gv_fmt(const char *formato, ...) {
	va_list ap;
	va_start(ap, formato);
	int n = vsnprintf(NULL, 0, formato, ap);
	va_end(ap);
	if (n < 0) {
		return (Clay_String){ 0 };
	}
	char *texto = gv__quadro_alloc(n + 1);
	if (!texto) {
		return (Clay_String){ 0 };
	}
	va_start(ap, formato);
	vsnprintf(texto, n + 1, formato, ap);
	va_end(ap);
	return (Clay_String){ .length = n, .chars = texto };
}

/* ---- pango ---- */

static PangoContext *contexto;
static PangoLayout *medidor;

void gv__texto_iniciar(void) {
	if (contexto) {
		return;
	}
	PangoFontMap *mapa = pango_cairo_font_map_get_default();
	contexto = pango_font_map_create_context(mapa);
	/* medidas em pixels lógicos, sem arredondar ao pixel (o desenho é que escala) */
	cairo_font_options_t *opcoes = cairo_font_options_create();
	cairo_font_options_set_hint_metrics(opcoes, CAIRO_HINT_METRICS_OFF);
	pango_cairo_context_set_font_options(contexto, opcoes);
	cairo_font_options_destroy(opcoes);
	medidor = pango_layout_new(contexto);
}

static const PangoWeight pesos[] = {
	[GV_PESO_NORMAL] = PANGO_WEIGHT_NORMAL,
	[GV_PESO_MEDIO] = PANGO_WEIGHT_MEDIUM,
	[GV_PESO_SEMINEGRITO] = PANGO_WEIGHT_SEMIBOLD,
	[GV_PESO_NEGRITO] = PANGO_WEIGHT_BOLD,
};

static void preparar(PangoLayout *layout, const char *texto, int n, int peso, float tamanho) {
	PangoFontDescription *fonte = pango_font_description_from_string(gv_t.fonte);
	pango_font_description_set_weight(fonte, pesos[peso <= GV_PESO_NEGRITO ? peso : 0]);
	pango_font_description_set_absolute_size(fonte, tamanho * PANGO_SCALE);
	pango_layout_set_font_description(layout, fonte);
	pango_font_description_free(fonte);
	pango_layout_set_text(layout, texto, n);
}

Clay_Dimensions gv__texto_medir(Clay_StringSlice texto, Clay_TextElementConfig *config, void *dados) {
	(void)dados;
	preparar(medidor, texto.chars, texto.length, config->fontId, config->fontSize);
	PangoRectangle logico;
	pango_layout_get_extents(medidor, NULL, &logico);
	float altura = config->lineHeight ? config->lineHeight : logico.height / (float)PANGO_SCALE;
	return (Clay_Dimensions){ logico.width / (float)PANGO_SCALE, altura };
}

void gv__texto_desenhar(cairo_t *cr, Clay_RenderCommand *cmd) {
	Clay_TextRenderData *t = &cmd->renderData.text;
	PangoLayout *layout = pango_cairo_create_layout(cr);
	cairo_font_options_t *opcoes = cairo_font_options_create();
	cairo_font_options_set_hint_metrics(opcoes, CAIRO_HINT_METRICS_OFF);
	cairo_font_options_set_antialias(opcoes, CAIRO_ANTIALIAS_GRAY);
	pango_cairo_context_set_font_options(pango_layout_get_context(layout), opcoes);
	cairo_font_options_destroy(opcoes);
	pango_layout_context_changed(layout);
	preparar(layout, t->stringContents.chars, t->stringContents.length, t->fontId, t->fontSize);
	PangoRectangle logico;
	pango_layout_get_extents(layout, NULL, &logico);
	float altura = logico.height / (float)PANGO_SCALE;
	cairo_set_source_rgba(cr, t->textColor.r / 255.0, t->textColor.g / 255.0, t->textColor.b / 255.0,
		t->textColor.a / 255.0);
	/* centrado na altura da linha, se ela for maior que a do texto */
	cairo_move_to(cr, cmd->boundingBox.x, cmd->boundingBox.y + (cmd->boundingBox.height - altura) / 2);
	pango_cairo_show_layout(cr, layout);
	g_object_unref(layout);
}

void gv_texto(Clay_String texto, float tamanho, Clay_Color cor, enum gv_peso peso) {
	if (!texto.isStaticallyAllocated && texto.chars) {
		/* um texto do chamador pode não viver até ao desenho: copia-o para o quadro */
		char *copia = gv__quadro_alloc(texto.length + 1);
		if (copia) {
			memcpy(copia, texto.chars, texto.length);
			copia[texto.length] = '\0';
			texto.chars = copia;
		}
	}
	CLAY_TEXT(texto, {
		.textColor = cor,
		.fontSize = (uint16_t)(tamanho > 0 ? tamanho : gv_t.tamanho_corpo),
		.fontId = (uint16_t)peso,
		.wrapMode = CLAY_TEXT_WRAP_WORDS,
	});
}
