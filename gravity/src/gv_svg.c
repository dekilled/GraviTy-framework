/*
 * O "d" de um caminho SVG traçado no cairo: M L H V C S Q T A Z, absolutos e relativos. É o
 * que os ícones do LUMNA usam (Icon.vue: 24 × 24, só traço), então o Gravity desenha os mesmos.
 */
#include "gv_interno.h"

#include <ctype.h>
#include <math.h>
#include <stdlib.h>

struct leitor {
	const char *p;
};

static void saltar(struct leitor *l) {
	while (*l->p && (isspace((unsigned char)*l->p) || *l->p == ',')) {
		l->p++;
	}
}

static bool numero(struct leitor *l, double *v) {
	saltar(l);
	char *fim;
	*v = strtod(l->p, &fim);
	if (fim == l->p) {
		return false;
	}
	l->p = fim;
	return true;
}

/* As flags dos arcos podem vir coladas ("a1 1 0 011 1"): um dígito só. */
static bool flag(struct leitor *l, int *v) {
	saltar(l);
	if (*l->p != '0' && *l->p != '1') {
		return false;
	}
	*v = *l->p - '0';
	l->p++;
	return true;
}

/* Arco do SVG (de x1,y1 a x2,y2) convertido para o centro, como na especificação (F.6.5). */
static void arco(cairo_t *cr, double x1, double y1, double rx, double ry, double phi, int grande, int sentido,
		double x2, double y2) {
	if (rx == 0 || ry == 0) {
		cairo_line_to(cr, x2, y2);
		return;
	}
	rx = fabs(rx);
	ry = fabs(ry);
	double cphi = cos(phi), sphi = sin(phi);
	double dx = (x1 - x2) / 2, dy = (y1 - y2) / 2;
	double x1p = cphi * dx + sphi * dy;
	double y1p = -sphi * dx + cphi * dy;
	double lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
	if (lambda > 1) {
		rx *= sqrt(lambda);
		ry *= sqrt(lambda);
	}
	double num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p;
	double den = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
	double coef = den > 0 ? sqrt(fmax(0, num / den)) : 0;
	if (grande == sentido) {
		coef = -coef;
	}
	double cxp = coef * rx * y1p / ry;
	double cyp = -coef * ry * x1p / rx;
	double cx = cphi * cxp - sphi * cyp + (x1 + x2) / 2;
	double cy = sphi * cxp + cphi * cyp + (y1 + y2) / 2;
	double a1 = atan2((y1p - cyp) / ry, (x1p - cxp) / rx);
	double a2 = atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx);
	double delta = a2 - a1;
	if (sentido && delta < 0) {
		delta += 2 * M_PI;
	} else if (!sentido && delta > 0) {
		delta -= 2 * M_PI;
	}
	cairo_save(cr);
	cairo_translate(cr, cx, cy);
	cairo_rotate(cr, phi);
	cairo_scale(cr, rx, ry);
	if (sentido) {
		cairo_arc(cr, 0, 0, 1, a1, a1 + delta);
	} else {
		cairo_arc_negative(cr, 0, 0, 1, a1, a1 + delta);
	}
	cairo_restore(cr);
}

bool gv__svg_tracar(cairo_t *cr, const char *d) {
	struct leitor l = { d };
	double x = 0, y = 0;         /* ponto actual */
	double sx = 0, sy = 0;       /* início do subcaminho */
	double cx2 = 0, cy2 = 0;     /* último ponto de controlo (S/T) */
	char ultimo = 0;
	char cmd = 0;
	for (;;) {
		saltar(&l);
		if (!*l.p) {
			break;
		}
		if (isalpha((unsigned char)*l.p)) {
			cmd = *l.p++;
		} else if (!cmd) {
			return false;
		} else if (cmd == 'M') {
			cmd = 'L'; /* números depois de um M são linhas */
		} else if (cmd == 'm') {
			cmd = 'l';
		}
		bool rel = islower((unsigned char)cmd);
		double a, b, c, e, f, g;
		int fl1, fl2;
		switch (cmd) {
		case 'M': case 'm':
			if (!numero(&l, &a) || !numero(&l, &b)) return false;
			if (rel) { a += x; b += y; }
			cairo_move_to(cr, a, b);
			x = sx = a; y = sy = b;
			break;
		case 'L': case 'l':
			if (!numero(&l, &a) || !numero(&l, &b)) return false;
			if (rel) { a += x; b += y; }
			cairo_line_to(cr, a, b);
			x = a; y = b;
			break;
		case 'H': case 'h':
			if (!numero(&l, &a)) return false;
			x = rel ? x + a : a;
			cairo_line_to(cr, x, y);
			break;
		case 'V': case 'v':
			if (!numero(&l, &a)) return false;
			y = rel ? y + a : a;
			cairo_line_to(cr, x, y);
			break;
		case 'C': case 'c':
			if (!numero(&l, &a) || !numero(&l, &b) || !numero(&l, &c) || !numero(&l, &e) ||
				!numero(&l, &f) || !numero(&l, &g)) return false;
			if (rel) { a += x; b += y; c += x; e += y; f += x; g += y; }
			cairo_curve_to(cr, a, b, c, e, f, g);
			cx2 = c; cy2 = e; x = f; y = g;
			break;
		case 'S': case 's': {
			if (!numero(&l, &c) || !numero(&l, &e) || !numero(&l, &f) || !numero(&l, &g)) return false;
			if (rel) { c += x; e += y; f += x; g += y; }
			bool espelha = ultimo == 'C' || ultimo == 'c' || ultimo == 'S' || ultimo == 's';
			a = espelha ? 2 * x - cx2 : x;
			b = espelha ? 2 * y - cy2 : y;
			cairo_curve_to(cr, a, b, c, e, f, g);
			cx2 = c; cy2 = e; x = f; y = g;
			break;
		}
		case 'Q': case 'q':
			if (!numero(&l, &a) || !numero(&l, &b) || !numero(&l, &f) || !numero(&l, &g)) return false;
			if (rel) { a += x; b += y; f += x; g += y; }
			/* quadrática em cúbica */
			cairo_curve_to(cr, x + 2.0 / 3 * (a - x), y + 2.0 / 3 * (b - y), f + 2.0 / 3 * (a - f),
				g + 2.0 / 3 * (b - g), f, g);
			cx2 = a; cy2 = b; x = f; y = g;
			break;
		case 'T': case 't': {
			if (!numero(&l, &f) || !numero(&l, &g)) return false;
			if (rel) { f += x; g += y; }
			bool espelha = ultimo == 'Q' || ultimo == 'q' || ultimo == 'T' || ultimo == 't';
			a = espelha ? 2 * x - cx2 : x;
			b = espelha ? 2 * y - cy2 : y;
			cairo_curve_to(cr, x + 2.0 / 3 * (a - x), y + 2.0 / 3 * (b - y), f + 2.0 / 3 * (a - f),
				g + 2.0 / 3 * (b - g), f, g);
			cx2 = a; cy2 = b; x = f; y = g;
			break;
		}
		case 'A': case 'a':
			if (!numero(&l, &a) || !numero(&l, &b) || !numero(&l, &c) || !flag(&l, &fl1) ||
				!flag(&l, &fl2) || !numero(&l, &f) || !numero(&l, &g)) return false;
			if (rel) { f += x; g += y; }
			arco(cr, x, y, a, b, c * M_PI / 180, fl1, fl2, f, g);
			x = f; y = g;
			break;
		case 'Z': case 'z':
			cairo_close_path(cr);
			x = sx; y = sy;
			break;
		default:
			return false;
		}
		ultimo = cmd;
	}
	return true;
}
