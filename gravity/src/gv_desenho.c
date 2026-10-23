/*
 * Os comandos do Clay no cairo: retângulos de cantos redondos (com sombra macia, se o elemento
 * tem gv_sombra), bordas, texto, recortes e os elementos próprios do Gravity (ícone,
 * deslizante, interruptor).
 */
#include "gv_interno.h"

#include <math.h>

static void cor(cairo_t *cr, Clay_Color c) {
	cairo_set_source_rgba(cr, c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0);
}

static void redondo(cairo_t *cr, double x, double y, double w, double h, Clay_CornerRadius r) {
	double max = fmin(w, h) / 2;
	double tl = fmin(r.topLeft, max), tr = fmin(r.topRight, max);
	double bl = fmin(r.bottomLeft, max), br = fmin(r.bottomRight, max);
	cairo_new_sub_path(cr);
	cairo_arc(cr, x + w - tr, y + tr, tr, -M_PI / 2, 0);
	cairo_arc(cr, x + w - br, y + h - br, br, 0, M_PI / 2);
	cairo_arc(cr, x + bl, y + h - bl, bl, M_PI / 2, M_PI);
	cairo_arc(cr, x + tl, y + tl, tl, M_PI, 3 * M_PI / 2);
	cairo_close_path(cr);
}

static Clay_CornerRadius todos(float r) {
	return (Clay_CornerRadius){ r, r, r, r };
}

/* Sombra macia: camadas cada vez maiores e mais fracas (o cairo não tem desfoque). */
static void sombra(cairo_t *cr, Clay_BoundingBox b, Clay_CornerRadius r, const struct gv_extra *s) {
	const int passos = 12;
	double d = s->sombra.desfoque;
	for (int i = passos; i >= 1; i--) {
		double f = (double)i / passos;
		double cresce = d * f;
		double alfa = s->sombra.alfa * (1 - f) * (1 - f) * 2.2 / passos;
		cairo_set_source_rgba(cr, 0, 0, 0, alfa);
		Clay_CornerRadius rr = { r.topLeft + cresce, r.topRight + cresce, r.bottomLeft + cresce, r.bottomRight + cresce };
		redondo(cr, b.x - cresce, b.y - cresce + s->sombra.desloca_y, b.width + 2 * cresce, b.height + 2 * cresce, rr);
		cairo_fill(cr);
	}
}

static void icone(cairo_t *cr, Clay_BoundingBox b, const struct gv_extra *e) {
	cairo_save(cr);
	double lado = fmin(b.width, b.height);
	cairo_translate(cr, b.x + (b.width - lado) / 2, b.y + (b.height - lado) / 2);
	cairo_scale(cr, lado / 24.0, lado / 24.0);
	cairo_new_path(cr);
	if (gv__svg_tracar(cr, e->icone.caminho)) {
		cor(cr, e->icone.cor);
		cairo_set_line_width(cr, e->icone.traco);
		cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
		cairo_set_line_join(cr, CAIRO_LINE_JOIN_ROUND);
		cairo_stroke(cr);
	}
	cairo_new_path(cr);
	cairo_restore(cr);
}

static void deslizante(cairo_t *cr, Clay_BoundingBox b, const struct gv_extra *e) {
	double v = fmax(0, fmin(1, e->deslizante.valor));
	double t = e->deslizante.trilho;
	double p = e->deslizante.puxador * (1 + 0.12 * e->deslizante.realce);
	double meio = b.y + b.height / 2;
	/* o trilho vai de borda a borda; o puxador anda por dentro dele */
	double x0 = b.x + e->deslizante.puxador / 2;
	double util = b.width - e->deslizante.puxador;
	double px = x0 + util * v;
	redondo(cr, b.x, meio - t / 2, b.width, t, todos(t / 2));
	cor(cr, e->deslizante.vazio);
	cairo_fill(cr);
	if (px - b.x > 0.5) {
		redondo(cr, b.x, meio - t / 2, px - b.x, t, todos(t / 2));
		cor(cr, e->deslizante.cheio);
		cairo_fill(cr);
	}
	/* a sombra do puxador (0 2px 8px rgba(0,0,0,.35) no shell) */
	for (int i = 6; i >= 1; i--) {
		cairo_arc(cr, px, meio + 2, p / 2 + i * 0.8, 0, 2 * M_PI);
		cairo_set_source_rgba(cr, 0, 0, 0, 0.35 / 6 * (7 - i) / 3.5);
		cairo_fill(cr);
	}
	cairo_arc(cr, px, meio, p / 2, 0, 2 * M_PI);
	cor(cr, e->deslizante.cor_puxador);
	cairo_fill(cr);
}

static void interruptor(cairo_t *cr, Clay_BoundingBox b, const struct gv_extra *e) {
	double h = b.height;
	redondo(cr, b.x, b.y, b.width, h, todos(h / 2));
	cor(cr, e->interruptor.fundo);
	cairo_fill(cr);
	double bolinha = h - 6;
	double x = b.x + 3 + bolinha / 2 + (b.width - 6 - bolinha) * e->interruptor.posicao;
	cairo_arc(cr, x, b.y + h / 2, bolinha / 2, 0, 2 * M_PI);
	cor(cr, e->interruptor.bolinha);
	cairo_fill(cr);
}

void gv__desenhar(cairo_t *cr, Clay_RenderCommandArray comandos) {
	for (int i = 0; i < comandos.length; i++) {
		Clay_RenderCommand *cmd = Clay_RenderCommandArray_Get(&comandos, i);
		Clay_BoundingBox b = cmd->boundingBox;
		switch (cmd->commandType) {
		case CLAY_RENDER_COMMAND_TYPE_RECTANGLE: {
			Clay_RectangleRenderData *r = &cmd->renderData.rectangle;
			struct gv_extra *extra = cmd->userData;
			if (extra && extra->tipo == GV_EXTRA_SOMBRA) {
				sombra(cr, b, r->cornerRadius, extra);
			}
			redondo(cr, b.x, b.y, b.width, b.height, r->cornerRadius);
			cor(cr, r->backgroundColor);
			cairo_fill(cr);
			break;
		}
		case CLAY_RENDER_COMMAND_TYPE_BORDER: {
			Clay_BorderRenderData *r = &cmd->renderData.border;
			/* a borda é por dentro da caixa: um contorno a meia largura para dentro */
			double w = r->width.top ? r->width.top : r->width.left ? r->width.left : r->width.bottom ? r->width.bottom : r->width.right;
			if (w <= 0) {
				break;
			}
			bool inteira = r->width.top && r->width.bottom && r->width.left && r->width.right;
			cor(cr, r->color);
			cairo_set_line_width(cr, w);
			if (inteira) {
				Clay_CornerRadius c = r->cornerRadius;
				Clay_CornerRadius dentro = { fmax(0, c.topLeft - w / 2), fmax(0, c.topRight - w / 2),
					fmax(0, c.bottomLeft - w / 2), fmax(0, c.bottomRight - w / 2) };
				redondo(cr, b.x + w / 2, b.y + w / 2, b.width - w, b.height - w, dentro);
				cairo_stroke(cr);
			} else {
				/* lados soltos (um separador em baixo, por exemplo): linhas rectas */
				if (r->width.top) {
					cairo_rectangle(cr, b.x, b.y, b.width, r->width.top);
				}
				if (r->width.bottom) {
					cairo_rectangle(cr, b.x, b.y + b.height - r->width.bottom, b.width, r->width.bottom);
				}
				if (r->width.left) {
					cairo_rectangle(cr, b.x, b.y, r->width.left, b.height);
				}
				if (r->width.right) {
					cairo_rectangle(cr, b.x + b.width - r->width.right, b.y, r->width.right, b.height);
				}
				cairo_fill(cr);
			}
			break;
		}
		case CLAY_RENDER_COMMAND_TYPE_TEXT:
			gv__texto_desenhar(cr, cmd);
			break;
		case CLAY_RENDER_COMMAND_TYPE_SCISSOR_START:
			cairo_save(cr);
			cairo_rectangle(cr, b.x, b.y, b.width, b.height);
			cairo_clip(cr);
			break;
		case CLAY_RENDER_COMMAND_TYPE_SCISSOR_END:
			cairo_restore(cr);
			break;
		case CLAY_RENDER_COMMAND_TYPE_CUSTOM: {
			Clay_CustomRenderData *c = &cmd->renderData.custom;
			if (c->backgroundColor.a > 0) {
				redondo(cr, b.x, b.y, b.width, b.height, c->cornerRadius);
				cor(cr, c->backgroundColor);
				cairo_fill(cr);
			}
			struct gv_extra *extra = c->customData;
			if (!extra) {
				break;
			}
			switch (extra->tipo) {
			case GV_EXTRA_ICONE:
				icone(cr, b, extra);
				break;
			case GV_EXTRA_DESLIZANTE:
				deslizante(cr, b, extra);
				break;
			case GV_EXTRA_INTERRUPTOR:
				interruptor(cr, b, extra);
				break;
			default:
				break;
			}
			break;
		}
		default:
			break;
		}
	}
}
