/*
 * Animações: um valor que anda até ao alvo na duração pedida, com a curva do tema. Em modo
 * imediato não há objectos para guardar o estado, por isso cada animação vive numa tabela pela
 * chave; uma que não é pedida há uns quadros cede o lugar.
 */
#include "gv_interno.h"

#include <math.h>

#define GV_MAX_ANIMS 512
#define GV_ESQUECER 120 /* quadros sem ser pedida */

struct anim {
	uint32_t chave;
	float de, para;
	double inicio;
	float duracao;
	uint32_t visto;
	bool usada;
};

static struct anim anims[GV_MAX_ANIMS];
static uint32_t quadro;

void gv__anim_quadro(void) {
	quadro++;
}

static float curva(float t) {
	if (t >= 1) {
		return 1;
	}
	switch (gv_t.curva) {
	case GV_CURVA_LINEAR:
		return t;
	case GV_CURVA_MOLA: {
		/* uma mola amortecida: passa ~6% do alvo e assenta */
		float c = 1.70158f * 1.1f;
		float u = t - 1;
		return 1 + (c + 1) * u * u * u + c * u * u;
	}
	default: {
		float u = 1 - t;
		return 1 - u * u * u;
	}
	}
}

static struct anim *achar(uint32_t chave, float alvo) {
	struct anim *livre = NULL, *velha = NULL;
	for (int i = 0; i < GV_MAX_ANIMS; i++) {
		struct anim *a = &anims[i];
		if (a->usada && a->chave == chave) {
			return a;
		}
		if (!a->usada || quadro - a->visto > GV_ESQUECER) {
			if (!livre) {
				livre = a;
			}
		} else if (!velha || a->visto < velha->visto) {
			velha = a;
		}
	}
	struct anim *a = livre ? livre : velha;
	*a = (struct anim){ .chave = chave, .de = alvo, .para = alvo, .usada = true };
	return a;
}

float gv_anim(uint32_t chave, float alvo, int duracao_ms) {
	struct anim *a = achar(chave, alvo);
	a->visto = quadro;
	double agora = gv_agora();
	if (!gv_t.animacoes || duracao_ms <= 0) {
		a->de = a->para = alvo;
		return alvo;
	}
	float t = a->duracao > 0 ? (float)((agora - a->inicio) / a->duracao) : 1;
	float valor = a->de + (a->para - a->de) * curva(t);
	if (alvo != a->para) {
		/* alvo novo: parte de onde está agora */
		a->de = valor;
		a->para = alvo;
		a->inicio = agora;
		a->duracao = duracao_ms / 1000.0f;
		t = 0;
		valor = a->de;
	}
	if (t < 1) {
		gv__app_pedir();
	}
	return valor;
}

Clay_Color gv_anim_cor(uint32_t chave, Clay_Color alvo, int duracao_ms) {
	return (Clay_Color){
		gv_anim(chave * 4 + 0, alvo.r, duracao_ms),
		gv_anim(chave * 4 + 1, alvo.g, duracao_ms),
		gv_anim(chave * 4 + 2, alvo.b, duracao_ms),
		gv_anim(chave * 4 + 3, alvo.a, duracao_ms),
	};
}
