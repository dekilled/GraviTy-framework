/*
 * Os componentes do Gravity. Em modo imediato um componente é uma função chamada a cada quadro:
 * declara os elementos dele no Clay e responde à entrada pelo layout do quadro anterior.
 *
 * Interação: o elemento que recebe o aperto fica "activo" (gv__entrada.ativo) até soltar; um
 * toque é soltar ainda sobre ele. Os componentes declarados por dentro de outros são chamados
 * depois, por isso o mais fundo ganha o aperto (um botão dentro de um cartão tocável).
 */
#include "gv_interno.h"

#include <math.h>
#include <string.h>

/* ---- interação ---- */

static void candidato(Clay_ElementId id) {
	if (gv__entrada.apertou && Clay_PointerOver(id)) {
		gv__entrada.ativo = id.id;
	}
}

bool gv_por_cima(Clay_ElementId id) {
	return Clay_PointerOver(id);
}

bool gv_premido(Clay_ElementId id) {
	candidato(id);
	return gv__entrada.ativo == id.id && gv__entrada.baixo;
}

bool gv_segurado(Clay_ElementId id) {
	return gv__entrada.ativo == id.id && gv__entrada.baixo;
}

bool gv_tocado(Clay_ElementId id) {
	candidato(id);
	return gv__entrada.soltou && gv__entrada.ativo == id.id && Clay_PointerOver(id);
}

Clay_BoundingBox gv_caixa(Clay_ElementId id) {
	Clay_ElementData dados = Clay_GetElementData(id);
	return dados.found ? dados.boundingBox : (Clay_BoundingBox){ 0 };
}

uint32_t gv_tecla(void) {
	return gv__entrada.tecla;
}

void gv__entrada_fim_do_quadro(void) {
	if (gv__entrada.soltou && !gv__entrada.baixo) {
		gv__entrada.ativo = 0;
		/* um dedo que saiu não fica "por cima" de nada */
		if (gv__entrada.toque) {
			gv__entrada.x = gv__entrada.y = -1;
			gv__app_pedir();
		}
	}
	gv__entrada.apertou = false;
	gv__entrada.soltou = false;
	gv__entrada.tecla = 0;
	gv__entrada.roda_x = gv__entrada.roda_y = 0;
}

/* ---- peças ---- */

static struct gv_extra *extra(enum gv_extra_tipo tipo) {
	struct gv_extra *e = gv__quadro_alloc(sizeof(*e));
	if (e) {
		memset(e, 0, sizeof(*e));
		e->tipo = tipo;
	}
	return e;
}

void *gv_sombra(float desfoque, float desloca_y, float alfa) {
	struct gv_extra *e = extra(GV_EXTRA_SOMBRA);
	if (e) {
		e->sombra.desfoque = desfoque;
		e->sombra.desloca_y = desloca_y;
		e->sombra.alfa = alfa;
	}
	return e;
}

static Clay_Color misturar(Clay_Color a, Clay_Color b, float t) {
	return (Clay_Color){ a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t };
}

bool gv_icone_existe(const char *nome) {
	return gv__icone_caminho(nome) != NULL;
}

void gv_icone(const char *nome, float tamanho, Clay_Color cor) {
	const char *caminho = gv__icone_caminho(nome);
	if (!caminho) {
		caminho = gv__icone_caminho("app");
	}
	struct gv_extra *e = extra(GV_EXTRA_ICONE);
	if (e) {
		e->icone.caminho = caminho;
		e->icone.cor = cor;
		e->icone.traco = gv_t.traco_icone;
	}
	CLAY_AUTO_ID({
		.layout = { .sizing = { CLAY_SIZING_FIXED(tamanho), CLAY_SIZING_FIXED(tamanho) } },
		.custom = { .customData = e },
	}) {}
}

void gv_separador(bool vertical, float comprimento) {
	Clay_SizingAxis eixo = comprimento > 0 ? CLAY_SIZING_FIXED(comprimento) : CLAY_SIZING_GROW(0);
	CLAY_AUTO_ID({
		.layout = { .sizing = vertical ? (Clay_Sizing){ CLAY_SIZING_FIXED(1), eixo } : (Clay_Sizing){ eixo, CLAY_SIZING_FIXED(1) } },
		.backgroundColor = gv_t.linha,
	}) {}
}

Clay_ElementDeclaration gv_cartao(void) {
	return (Clay_ElementDeclaration){
		.layout = {
			.layoutDirection = CLAY_TOP_TO_BOTTOM,
			.padding = { 20, 20, 20, 20 },
			.childGap = 0,
		},
		.backgroundColor = gv_t.superficie,
		.cornerRadius = CLAY_CORNER_RADIUS(gv_t.raio_grande),
		.border = { .color = gv_t.linha, .width = GV_BORDA(1) },
		.userData = gv_sombra(48, 24, 0.55f),
	};
}

/* ---- botões ---- */

bool gv_botao(Clay_ElementId id, const char *icone, const char *texto, enum gv_estilo_botao estilo) {
	bool tocado = gv_tocado(id);
	bool premido = gv_premido(id);
	bool sobre = gv_por_cima(id) && !gv__entrada.toque;
	float realce = gv_anim(id.id, premido ? 1 : sobre ? 0.5f : 0, gv_t.duracao_rapida);

	Clay_Color fundo = { 0 }, borda = { 0 }, conteudo = gv_t.texto;
	if (estilo == GV_BOTAO_CHEIO) {
		fundo = misturar(gv_t.acento_forte, gv_cor(0xffffffff), realce * 0.12f);
		conteudo = gv_cor(0xffffffff);
	} else {
		fundo = gv_alfa(gv_cor(0xffffffff), realce * 0.08f);
		conteudo = misturar(gv_t.acento, gv_t.texto, 0.35f);
		if (estilo == GV_BOTAO_CONTORNO) {
			borda = gv_t.linha;
		}
	}
	CLAY(id, {
		.layout = {
			.sizing = { CLAY_SIZING_GROW(0), CLAY_SIZING_FIXED(52) },
			.padding = { 16, 16, 0, 0 },
			.childGap = 10,
			.childAlignment = { CLAY_ALIGN_X_CENTER, CLAY_ALIGN_Y_CENTER },
		},
		.backgroundColor = fundo,
		.cornerRadius = CLAY_CORNER_RADIUS(gv_t.raio_medio),
		.border = { .color = borda, .width = GV_BORDA(borda.a > 0 ? 1 : 0) },
	}) {
		if (icone) {
			gv_icone(icone, 22, conteudo);
		}
		if (texto) {
			gv_texto(gv_str(texto), 14, conteudo, estilo == GV_BOTAO_CHEIO ? GV_PESO_SEMINEGRITO : GV_PESO_NORMAL);
		}
	}
	return tocado;
}

bool gv_botao_redondo(Clay_ElementId id, const char *icone, float tamanho, bool ligado, bool perigo) {
	bool tocado = gv_tocado(id);
	bool premido = gv_premido(id);
	bool sobre = gv_por_cima(id) && !gv__entrada.toque;
	float realce = gv_anim(id.id, premido ? 1 : sobre ? 0.5f : 0, gv_t.duracao_rapida);
	float ativo = gv_anim(id.id + 1, ligado ? 1 : 0, gv_t.duracao_normal);

	Clay_Color marca = perigo ? gv_t.perigo : gv_t.acento;
	Clay_Color fundo = misturar(gv_t.superficie_alta, gv_alfa(marca, perigo ? 0.06f : 0.18f), ativo);
	fundo = misturar(fundo, gv_alfa(gv_cor(0xffffffff), 0.14f), realce * 0.5f);
	Clay_Color borda = misturar(gv_t.linha, gv_alfa(marca, 0.4f), ativo);
	Clay_Color cor = misturar(gv_t.texto_suave, marca, ativo);
	if (tamanho <= 0) {
		tamanho = 44;
	}
	CLAY(id, {
		.layout = {
			.sizing = { CLAY_SIZING_FIXED(tamanho), CLAY_SIZING_FIXED(tamanho) },
			.childAlignment = { CLAY_ALIGN_X_CENTER, CLAY_ALIGN_Y_CENTER },
		},
		.backgroundColor = fundo,
		.cornerRadius = CLAY_CORNER_RADIUS(tamanho / 2),
		.border = { .color = borda, .width = GV_BORDA(1) },
	}) {
		gv_icone(icone, tamanho * 0.46f, cor);
	}
	return tocado;
}

/* ---- deslizante e interruptor ---- */

bool gv_deslizante(Clay_ElementId id, float *valor, float trilho, float puxador) {
	if (trilho <= 0) {
		trilho = 12;
	}
	if (puxador <= 0) {
		puxador = 28;
	}
	candidato(id);
	bool arrastando = gv__entrada.ativo == id.id && (gv__entrada.baixo || gv__entrada.soltou);
	bool mudou = false;
	if (arrastando) {
		Clay_BoundingBox b = gv_caixa(id);
		if (b.width > puxador) {
			float v = (gv__entrada.x - b.x - puxador / 2) / (b.width - puxador);
			v = fmaxf(0, fminf(1, v));
			if (fabsf(v - *valor) > 0.0005f) {
				*valor = v;
				mudou = true;
			}
		}
	}
	struct gv_extra *e = extra(GV_EXTRA_DESLIZANTE);
	if (e) {
		e->deslizante.valor = *valor;
		e->deslizante.trilho = trilho;
		e->deslizante.puxador = puxador;
		e->deslizante.cheio = gv_t.acento;
		e->deslizante.vazio = gv_alfa(gv_cor(0xffffffff), 0.1f);
		e->deslizante.cor_puxador = gv_t.puxador;
		e->deslizante.realce = gv_anim(id.id, arrastando ? 1 : 0, gv_t.duracao_rapida);
	}
	CLAY(id, {
		.layout = { .sizing = { CLAY_SIZING_GROW(0), CLAY_SIZING_FIXED(fmaxf(puxador + 8, 30)) } },
		.custom = { .customData = e },
	}) {}
	return mudou;
}

bool gv_interruptor(Clay_ElementId id, bool *ligado) {
	bool mudou = false;
	if (gv_tocado(id)) {
		*ligado = !*ligado;
		mudou = true;
	}
	float pos = gv_anim(id.id, *ligado ? 1 : 0, gv_t.duracao_normal);
	struct gv_extra *e = extra(GV_EXTRA_INTERRUPTOR);
	if (e) {
		e->interruptor.posicao = pos;
		e->interruptor.fundo = misturar(gv_alfa(gv_cor(0xffffffff), 0.14f), gv_t.acento_forte, pos);
		e->interruptor.bolinha = gv_cor(0xffffffff);
	}
	CLAY(id, {
		.layout = { .sizing = { CLAY_SIZING_FIXED(52), CLAY_SIZING_FIXED(32) } },
		.custom = { .customData = e },
	}) {}
	return mudou;
}
