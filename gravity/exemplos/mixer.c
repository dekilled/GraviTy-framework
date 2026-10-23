/*
 * O mixer de áudio do LUMNA (o MobileVolume.vue do shell), em Gravity. Os volumes ainda são de
 * mentira: a ligação ao PipeWire vem depois; aqui é o desenho, o toque e as animações.
 *
 *   ./mixer            numa janela
 *   ./mixer --camada   como no celular: uma camada por cima de tudo, com o véu atrás
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <xkbcommon/xkbcommon-keysyms.h>

#include "gravity.h"

struct app_som {
	const char *nome;
	const char *icone;
	float volume;
	bool mudo;
};

static const char *saidas[] = { "Alto-falante", "Fones Bluetooth", "HDMI" };
static const char *icones_saida[] = { "speaker", "headphones", "desktop" };

static struct {
	float global;
	int saida;
	bool lista;
	struct app_som apps[3];
} m = {
	.global = 0.62f,
	.apps = {
		{ "Música", "music", 0.8f, false },
		{ "Emma", "waves", 0.55f, false },
		{ "Navegador", "globe", 0.35f, true },
	},
};

static int pct(float v) {
	return (int)lroundf(v * 100);
}

static void cabecalho(gv_app *app) {
	CLAY(CLAY_ID("cabecalho"), {
		.layout = { .sizing = { CLAY_SIZING_GROW(0) }, .childGap = 16, .childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
	}) {
		gv_icone("volume", 32, gv_t.icone);
		CLAY(CLAY_ID("titulo"), { .layout = { .sizing = { CLAY_SIZING_GROW(0) } } }) {
			gv_texto(CLAY_STRING("Mixer de áudio"), gv_t.tamanho_titulo, gv_t.texto, GV_PESO_SEMINEGRITO);
		}
		Clay_ElementId fechar = CLAY_ID("fechar");
		bool sobre = gv_por_cima(fechar);
		CLAY(fechar, {
			.layout = { .sizing = { CLAY_SIZING_FIXED(40), CLAY_SIZING_FIXED(40) },
				.childAlignment = { CLAY_ALIGN_X_CENTER, CLAY_ALIGN_Y_CENTER } },
			.backgroundColor = gv_alfa(gv_cor(0xffffffff), gv_anim(fechar.id, sobre ? 0.08f : 0, gv_t.duracao_rapida)),
			.cornerRadius = CLAY_CORNER_RADIUS(20),
		}) {
			gv_icone("close", 24, gv_t.icone);
		}
		if (gv_tocado(fechar)) {
			gv_app_sair(app);
		}
	}
}

static void saida(void) {
	CLAY(CLAY_ID("linha-saida"), {
		.layout = { .sizing = { CLAY_SIZING_GROW(0) }, .padding = { .top = 22 }, .childGap = 12,
			.childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
	}) {
		CLAY(CLAY_ID("rotulo-saida"), { .layout = { .sizing = { CLAY_SIZING_GROW(0) } } }) {
			gv_texto(CLAY_STRING("Saída"), gv_t.tamanho_corpo, gv_t.texto_suave, GV_PESO_NORMAL);
		}
		Clay_ElementId chip = CLAY_ID("chip-saida");
		if (gv_tocado(chip)) {
			m.lista = !m.lista;
		}
		CLAY(chip, {
			.layout = { .sizing = { .height = CLAY_SIZING_FIXED(50) }, .padding = { 16, 16, 0, 0 }, .childGap = 10,
				.childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
			.backgroundColor = gv_alfa(gv_cor(0xffffffff), gv_premido(chip) ? 0.1f : 0.04f),
			.cornerRadius = CLAY_CORNER_RADIUS(25),
			.border = { .color = gv_alfa(gv_cor(0xffffffff), 0.12f), .width = GV_BORDA(1) },
		}) {
			gv_icone(icones_saida[m.saida], 20, gv_t.icone);
			gv_texto(gv_str(saidas[m.saida]), 14, gv_t.texto, GV_PESO_NORMAL);
			gv_icone(m.lista ? "chevron-down" : "forward", 16, gv_t.icone);

			/* a lista das saídas, flutuando por baixo do chip */
			if (m.lista) {
				CLAY(CLAY_ID("lista-saidas"), {
					.layout = { .layoutDirection = CLAY_TOP_TO_BOTTOM, .sizing = { CLAY_SIZING_FIXED(230) },
						.padding = CLAY_PADDING_ALL(6) },
					.backgroundColor = gv_cor(0x1c1828ff),
					.cornerRadius = CLAY_CORNER_RADIUS(14),
					.border = { .color = gv_alfa(gv_t.acento, 0.2f), .width = GV_BORDA(1) },
					.floating = { .attachTo = CLAY_ATTACH_TO_PARENT, .offset = { 0, 6 }, .zIndex = 10,
						.attachPoints = { .element = CLAY_ATTACH_POINT_RIGHT_TOP, .parent = CLAY_ATTACH_POINT_RIGHT_BOTTOM } },
					.userData = gv_sombra(24, 14, 0.5f),
				}) {
					for (int i = 0; i < 3; i++) {
						Clay_ElementId item = CLAY_IDI("saida", i);
						if (gv_tocado(item)) {
							m.saida = i;
							m.lista = false;
						}
						bool esta = m.saida == i;
						CLAY(item, {
							.layout = { .sizing = { CLAY_SIZING_GROW(0), CLAY_SIZING_FIXED(44) }, .padding = { 10, 10, 0, 0 },
								.childGap = 10, .childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
							.backgroundColor = esta ? gv_alfa(gv_t.acento, 0.14f)
								: gv_alfa(gv_cor(0xffffffff), gv_por_cima(item) ? 0.05f : 0),
							.cornerRadius = CLAY_CORNER_RADIUS(10),
						}) {
							gv_icone(icones_saida[i], 18, gv_t.icone);
							CLAY(CLAY_IDI("saida-nome", i), { .layout = { .sizing = { CLAY_SIZING_GROW(0) } } }) {
								gv_texto(gv_str(saidas[i]), 14, gv_t.texto, GV_PESO_NORMAL);
							}
							if (esta) {
								gv_icone("check", 16, gv_t.acento);
							}
						}
					}
				}
			}
		}
	}
}

static void volume_global(void) {
	CLAY(CLAY_ID("global"), {
		.layout = { .layoutDirection = CLAY_TOP_TO_BOTTOM, .sizing = { CLAY_SIZING_GROW(0) },
			.padding = { .top = 18, .bottom = 16 }, .childGap = 8 },
		.border = { .color = gv_alfa(gv_cor(0xffffffff), 0.08f), .width = { .bottom = 1 } },
	}) {
		gv_texto(CLAY_STRING("Volume global"), gv_t.tamanho_corpo, gv_t.texto_suave, GV_PESO_NORMAL);
		CLAY(CLAY_ID("global-linha"), {
			.layout = { .sizing = { CLAY_SIZING_GROW(0) }, .childGap = 14, .childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
		}) {
			gv_deslizante(CLAY_ID("global-volume"), &m.global, 12, 28);
			CLAY(CLAY_ID("global-pct"), {
				.layout = { .sizing = { CLAY_SIZING_FIXED(44) }, .childAlignment = { .x = CLAY_ALIGN_X_RIGHT } },
			}) {
				gv_texto(gv_fmt("%d%%", pct(m.global)), gv_t.tamanho_corpo, gv_t.texto, GV_PESO_NORMAL);
			}
		}
	}
}

static void apps(void) {
	for (int i = 0; i < 3; i++) {
		struct app_som *a = &m.apps[i];
		CLAY(CLAY_IDI("app", i), {
			.layout = { .sizing = { CLAY_SIZING_GROW(0), CLAY_SIZING_FIT(62) }, .childGap = 12,
				.childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
			.border = { .color = gv_alfa(gv_cor(0xffffffff), 0.06f), .width = { .bottom = 1 } },
		}) {
			CLAY(CLAY_IDI("app-icone", i), {
				.layout = { .sizing = { CLAY_SIZING_FIXED(34), CLAY_SIZING_FIXED(34) },
					.childAlignment = { CLAY_ALIGN_X_CENTER, CLAY_ALIGN_Y_CENTER } },
				.backgroundColor = gv_alfa(gv_t.acento, 0.12f),
				.cornerRadius = CLAY_CORNER_RADIUS(gv_t.raio_pequeno),
			}) {
				gv_icone(a->icone, 22, gv_t.icone);
			}
			CLAY(CLAY_IDI("app-nome", i), { .layout = { .sizing = { CLAY_SIZING_FIXED(92) } } }) {
				gv_texto(gv_str(a->nome), gv_t.tamanho_corpo, gv_t.texto, GV_PESO_NORMAL);
			}
			if (gv_botao_redondo(CLAY_IDI("app-mudo", i), a->mudo ? "mute" : "volume", 44, a->mudo, true)) {
				a->mudo = !a->mudo;
			}
			float mostrado = a->mudo ? 0 : a->volume;
			if (gv_deslizante(CLAY_IDI("app-volume", i), &mostrado, 10, 24)) {
				a->volume = mostrado;
				a->mudo = false;
			}
			CLAY(CLAY_IDI("app-pct", i), {
				.layout = { .sizing = { CLAY_SIZING_FIXED(44) }, .childAlignment = { .x = CLAY_ALIGN_X_RIGHT } },
			}) {
				gv_texto(gv_fmt("%d%%", a->mudo ? 0 : pct(a->volume)), gv_t.tamanho_corpo, gv_t.texto, GV_PESO_NORMAL);
			}
		}
	}
}

static void rodape(gv_app *app) {
	CLAY(CLAY_ID("rodape"), {
		.layout = { .sizing = { CLAY_SIZING_GROW(0) }, .padding = { .top = 16 }, .childGap = 10,
			.childAlignment = { .y = CLAY_ALIGN_Y_CENTER } },
	}) {
		if (gv_botao(CLAY_ID("redefinir"), "refresh", "Redefinir volumes", GV_BOTAO_CONTORNO)) {
			m.global = 0.62f;
			for (int i = 0; i < 3; i++) {
				m.apps[i].volume = 1;
				m.apps[i].mudo = false;
			}
		}
		gv_separador(true, 40);
		if (gv_botao(CLAY_ID("ajustes"), "settings", "Ajustes de áudio", GV_BOTAO_SIMPLES)) {
			printf("abrir os ajustes de áudio\n");
			fflush(stdout);
		}
	}
	(void)app;
}

static void desenhar(gv_app *app, void *dados) {
	(void)dados;
	if (gv_tecla() == XKB_KEY_Escape) {
		gv_app_sair(app);
	}
	/* a entrada do painel: cresce de 97% e aparece (o "pop" do shell) */
	float entrada = gv_anim(1, 1, gv_t.duracao_normal);
	Clay_ElementId veu = CLAY_ID("veu");
	Clay_ElementId cartao = CLAY_ID("cartao");
	if (gv_tocado(veu) && !gv_por_cima(cartao)) {
		if (m.lista) {
			m.lista = false;
		} else {
			gv_app_sair(app);
		}
	}
	CLAY(veu, {
		.layout = { .sizing = { CLAY_SIZING_GROW(0), CLAY_SIZING_GROW(0) }, .padding = { 20, 20, 20, 20 },
			.childAlignment = { CLAY_ALIGN_X_CENTER, CLAY_ALIGN_Y_CENTER } },
		.backgroundColor = gv_alfa(gv_t.fundo, gv_t.fundo.a / 255.0f * entrada),
	}) {
		Clay_ElementDeclaration c = gv_cartao();
		c.layout.sizing = (Clay_Sizing){ CLAY_SIZING_GROW(0, 420 * (0.97f + 0.03f * entrada)) };
		c.layout.padding = (Clay_Padding){ 20, 20, 22, 16 };
		c.backgroundColor = gv_alfa(c.backgroundColor, c.backgroundColor.a / 255.0f * entrada);
		CLAY(cartao, c) {
			cabecalho(app);
			saida();
			volume_global();
			apps();
			rodape(app);
		}
	}
}

int main(int argc, char **argv) {
	bool camada = argc > 1 && strcmp(argv[1], "--camada") == 0;
	gv_app *app = gv_app_criar(&(gv_opcoes){
		.titulo = "Mixer de áudio",
		.app_id = "lumna-mixer",
		.tipo = camada ? GV_CAMADA : GV_JANELA,
		.largura = camada ? 0 : 460,
		.altura = camada ? 0 : 660,
		.nivel = GV_NIVEL_OVERLAY,
		.ancoras = GV_ANCORA_TUDO,
		.teclado = true,
	});
	if (!app) {
		return 1;
	}
	return gv_app_correr(app, desenhar, NULL);
}
