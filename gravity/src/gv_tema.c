/*
 * O tema: as cores, a forma, o texto e o movimento do LUMNA, num sítio só. Um tema.ini muda o
 * que quiser, chave a chave (o que não aparece fica como está):
 *
 *   # ~/.config/gravity/tema.ini
 *   acento = #f472b6
 *   raio_grande = 18
 *   fonte = Noto Sans
 *   duracao_normal = 300
 *   curva = mola
 *   animacoes = sim
 *
 * Cores em #RRGGBB ou #RRGGBBAA. Linhas com # ou ; são comentários; [secções] são só arrumação.
 */
#include "gv_interno.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

gv_tema gv_t;

Clay_Color gv_cor(uint32_t rgba) {
	return (Clay_Color){ (rgba >> 24) & 0xff, (rgba >> 16) & 0xff, (rgba >> 8) & 0xff, rgba & 0xff };
}

Clay_Color gv_alfa(Clay_Color cor, float alfa) {
	cor.a = alfa * 255;
	return cor;
}

void gv_tema_padrao(gv_tema *t) {
	*t = (gv_tema){
		/* as do shell: styles.css e o mixer (MobileVolume.vue) */
		.fundo = gv_cor(0x04030a66),
		.superficie = gv_cor(0x16131ff7),
		.superficie_alta = gv_cor(0xffffff0a),
		.texto = gv_cor(0xece8ffff),
		.texto_suave = gv_cor(0xcfc6eeff),
		.texto_fraco = gv_cor(0xa59cc9ff),
		.acento = gv_cor(0xa78bfaff),
		.acento_forte = gv_cor(0x8b5cf6ff),
		.icone = gv_cor(0xb9a2fbff),
		.linha = gv_cor(0xffffff1a),
		.perigo = gv_cor(0xfca5a5ff),
		.puxador = gv_cor(0xffffffff),
		.raio_pequeno = 9,
		.raio_medio = 16,
		.raio_grande = 26,
		.espaco = 4,
		.traco_icone = 1.8f,
		.fonte = "Inter, Noto Sans, sans-serif",
		.tamanho_legenda = 13,
		.tamanho_corpo = 15,
		.tamanho_destaque = 17,
		.tamanho_titulo = 22,
		.duracao_rapida = 120,
		.duracao_normal = 200,
		.duracao_lenta = 320,
		.curva = GV_CURVA_SUAVE,
		.animacoes = true,
	};
}

static bool ler_cor(const char *texto, Clay_Color *cor) {
	if (texto[0] != '#') {
		return false;
	}
	size_t n = strlen(texto + 1);
	char *fim;
	unsigned long v = strtoul(texto + 1, &fim, 16);
	if (*fim) {
		return false;
	}
	if (n == 6) {
		*cor = gv_cor((uint32_t)(v << 8) | 0xff);
	} else if (n == 8) {
		*cor = gv_cor((uint32_t)v);
	} else {
		return false;
	}
	return true;
}

struct chave_cor {
	const char *nome;
	size_t deslocamento;
};

#define COR(campo) { #campo, offsetof(gv_tema, campo) }
static const struct chave_cor cores[] = {
	COR(fundo), COR(superficie), COR(superficie_alta), COR(texto), COR(texto_suave), COR(texto_fraco),
	COR(acento), COR(acento_forte), COR(icone), COR(linha), COR(perigo), COR(puxador),
};

#define NUM(campo) { #campo, offsetof(gv_tema, campo) }
static const struct chave_cor numeros[] = {
	NUM(raio_pequeno), NUM(raio_medio), NUM(raio_grande), NUM(espaco), NUM(traco_icone),
	NUM(tamanho_legenda), NUM(tamanho_corpo), NUM(tamanho_destaque), NUM(tamanho_titulo),
};

static const struct chave_cor inteiros[] = {
	NUM(duracao_rapida), NUM(duracao_normal), NUM(duracao_lenta),
};

static char *aparar(char *s) {
	while (isspace((unsigned char)*s)) {
		s++;
	}
	char *fim = s + strlen(s);
	while (fim > s && isspace((unsigned char)fim[-1])) {
		*--fim = '\0';
	}
	return s;
}

static void aplicar(gv_tema *t, const char *chave, const char *valor, const char *ficheiro, int linha) {
	for (size_t i = 0; i < sizeof(cores) / sizeof(cores[0]); i++) {
		if (!strcmp(chave, cores[i].nome)) {
			if (!ler_cor(valor, (Clay_Color *)((char *)t + cores[i].deslocamento))) {
				fprintf(stderr, "gravity: %s:%d: cor %s inválida (use #RRGGBB ou #RRGGBBAA)\n", ficheiro, linha, valor);
			}
			return;
		}
	}
	for (size_t i = 0; i < sizeof(numeros) / sizeof(numeros[0]); i++) {
		if (!strcmp(chave, numeros[i].nome)) {
			*(float *)((char *)t + numeros[i].deslocamento) = strtof(valor, NULL);
			return;
		}
	}
	for (size_t i = 0; i < sizeof(inteiros) / sizeof(inteiros[0]); i++) {
		if (!strcmp(chave, inteiros[i].nome)) {
			*(int *)((char *)t + inteiros[i].deslocamento) = atoi(valor);
			return;
		}
	}
	if (!strcmp(chave, "fonte")) {
		snprintf(t->fonte, sizeof(t->fonte), "%s", valor);
	} else if (!strcmp(chave, "curva")) {
		t->curva = !strcasecmp(valor, "mola") ? GV_CURVA_MOLA
			: !strcasecmp(valor, "linear") ? GV_CURVA_LINEAR : GV_CURVA_SUAVE;
	} else if (!strcmp(chave, "animacoes")) {
		t->animacoes = !strcasecmp(valor, "sim") || !strcmp(valor, "1") || !strcasecmp(valor, "true");
	} else {
		fprintf(stderr, "gravity: %s:%d: chave %s desconhecida\n", ficheiro, linha, chave);
	}
}

bool gv_tema_carregar(const char *caminho) {
	char padrao[512];
	if (!caminho) {
		caminho = getenv("GRAVITY_TEMA");
	}
	if (!caminho) {
		const char *config = getenv("XDG_CONFIG_HOME");
		const char *casa = getenv("HOME");
		if (config && *config) {
			snprintf(padrao, sizeof(padrao), "%s/gravity/tema.ini", config);
		} else if (casa) {
			snprintf(padrao, sizeof(padrao), "%s/.config/gravity/tema.ini", casa);
		} else {
			return false;
		}
		caminho = padrao;
	}
	FILE *f = fopen(caminho, "r");
	if (!f) {
		return false;
	}
	char linha[512];
	int n = 0;
	while (fgets(linha, sizeof(linha), f)) {
		n++;
		char *s = aparar(linha);
		if (!*s || *s == '#' || *s == ';' || *s == '[') {
			continue;
		}
		char *igual = strchr(s, '=');
		if (!igual) {
			fprintf(stderr, "gravity: %s:%d: falta o =\n", caminho, n);
			continue;
		}
		*igual = '\0';
		aplicar(&gv_t, aparar(s), aparar(igual + 1), caminho, n);
	}
	fclose(f);
	return true;
}
