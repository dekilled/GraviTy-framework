/*
 * Gravity — a interface do LUMNA OS em C.
 *
 * Uma app Gravity desenha a tela inteira a cada quadro (modo imediato): a função de desenho
 * declara os elementos com o layout do Clay (CLAY(...) { ... }, como flexbox) e os componentes
 * gv_* (texto, ícone, botão, deslizante, interruptor...). O Gravity cuida do Wayland (janela
 * ou camada do LUMNA), do toque, do rato e do teclado, do texto (pango), dos ícones do LUMNA e
 * das animações; o visual sai do tema (gv_t), que um tema.ini muda sem recompilar.
 *
 *   static void desenhar(gv_app *app, void *dados) {
 *       CLAY(CLAY_ID("raiz"), { .layout = { .padding = CLAY_PADDING_ALL(16) } }) {
 *           if (gv_botao(CLAY_ID("ola"), "check", "Olá", GV_BOTAO_CHEIO)) gv_app_sair(app);
 *       }
 *   }
 *   int main(void) {
 *       gv_app *app = gv_app_criar(&(gv_opcoes){ .titulo = "Olá", .largura = 360, .altura = 200 });
 *       return gv_app_correr(app, desenhar, NULL);
 *   }
 *
 * Unidades: pixels lógicos (os do CSS). Num ecrã com escala 2 o Gravity desenha com o dobro.
 */
#ifndef GRAVITY_H
#define GRAVITY_H

#include <stdbool.h>
#include <stdint.h>

#include "clay.h"

/* ---- tema ---- */

enum gv_curva {
	GV_CURVA_SUAVE, /* sai depressa e assenta devagar (ease-out cúbica) */
	GV_CURVA_MOLA,  /* passa um pouco do alvo e volta */
	GV_CURVA_LINEAR,
};

typedef struct gv_tema {
	/* cores (0-255, como no Clay) */
	Clay_Color fundo;           /* o véu atrás de um painel */
	Clay_Color superficie;      /* cartões e painéis */
	Clay_Color superficie_alta; /* o que fica por cima de uma superfície (botões, campos) */
	Clay_Color texto;
	Clay_Color texto_suave;     /* legendas */
	Clay_Color texto_fraco;     /* o menos importante */
	Clay_Color acento;          /* violeta do LUMNA */
	Clay_Color acento_forte;
	Clay_Color icone;           /* ícones dos cabeçalhos */
	Clay_Color linha;           /* bordas e separadores */
	Clay_Color perigo;
	Clay_Color puxador;         /* o botão redondo do deslizante */
	/* forma */
	float raio_pequeno, raio_medio, raio_grande;
	float espaco;               /* a unidade dos espaçamentos (gv_e(n) = n × espaco) */
	float traco_icone;          /* grossura do traço dos ícones, em 24 px */
	/* texto */
	char fonte[64];
	float tamanho_legenda, tamanho_corpo, tamanho_destaque, tamanho_titulo;
	/* movimento */
	int duracao_rapida, duracao_normal, duracao_lenta; /* ms */
	enum gv_curva curva;
	bool animacoes;             /* falso: tudo muda na hora */
} gv_tema;

/* O tema activo. Os componentes lêem dele a cada quadro: mudar um campo muda a tela. */
extern gv_tema gv_t;

/* O tema do LUMNA, de fábrica. */
void gv_tema_padrao(gv_tema *tema);
/* Lê um tema.ini por cima do tema activo. NULL procura $GRAVITY_TEMA, depois
 * $XDG_CONFIG_HOME/gravity/tema.ini (~/.config/gravity/tema.ini). Devolve falso se não leu. */
bool gv_tema_carregar(const char *caminho);

static inline float gv_e(float n) { return n * gv_t.espaco; }
Clay_Color gv_cor(uint32_t rgba); /* 0xRRGGBBAA */
Clay_Color gv_alfa(Clay_Color cor, float alfa);

/* ---- app ---- */

enum gv_tipo {
	GV_JANELA, /* uma janela normal (xdg-shell) */
	GV_CAMADA, /* uma camada do LUMNA (layer-shell): barra, painel, teclado, bloqueio */
};

enum {
	GV_ANCORA_CIMA = 1,
	GV_ANCORA_BAIXO = 2,
	GV_ANCORA_ESQUERDA = 4,
	GV_ANCORA_DIREITA = 8,
	GV_ANCORA_TUDO = 15,
};

enum gv_nivel { GV_NIVEL_FUNDO, GV_NIVEL_BAIXO, GV_NIVEL_CIMA, GV_NIVEL_OVERLAY };

typedef struct gv_opcoes {
	const char *titulo;
	const char *app_id;
	enum gv_tipo tipo;
	int largura, altura;     /* o tamanho pedido (numa camada esticada, 0 é a saída inteira) */
	/* só camadas */
	enum gv_nivel nivel;
	uint32_t ancoras;
	int zona_exclusiva;
	bool teclado;            /* a camada quer o teclado */
} gv_opcoes;

typedef struct gv_app gv_app;
typedef void (*gv_desenho)(gv_app *app, void *dados);

gv_app *gv_app_criar(const gv_opcoes *opcoes);
/* Corre até gv_app_sair (ou o compositor fechar a janela). Devolve o código de saída. */
int gv_app_correr(gv_app *app, gv_desenho desenhar, void *dados);
void gv_app_sair(gv_app *app);
/* Pede outro quadro (os componentes e as animações já pedem sozinhos). */
void gv_app_redesenhar(gv_app *app);
/* Um descritor a vigiar no ciclo da app (um socket, um pipe); a função corre quando há o que ler. */
void gv_app_vigiar(gv_app *app, int fd, void (*pronto)(gv_app *app, int fd, void *dados), void *dados);
float gv_app_largura(gv_app *app);
float gv_app_altura(gv_app *app);
/* Segundos desde o arranque. */
double gv_agora(void);

/* ---- texto ---- */

enum gv_peso { GV_PESO_NORMAL, GV_PESO_MEDIO, GV_PESO_SEMINEGRITO, GV_PESO_NEGRITO };

/* Uma cópia que vive até ao fim do quadro (o Clay guarda só o ponteiro). */
Clay_String gv_str(const char *texto);
Clay_String gv_fmt(const char *formato, ...) __attribute__((format(printf, 1, 2)));
/* Um texto com o tamanho, a cor e o peso dados (0 no tamanho: o do corpo). */
void gv_texto(Clay_String texto, float tamanho, Clay_Color cor, enum gv_peso peso);
/* Atalho: texto do corpo na cor do tema. */
#define gv_rotulo(literal) gv_texto(CLAY_STRING(literal), 0, gv_t.texto, GV_PESO_NORMAL)

/* ---- ícones (os do LUMNA: o mesmo traço de 24 px do shell) ---- */

void gv_icone(const char *nome, float tamanho, Clay_Color cor);
bool gv_icone_existe(const char *nome);

/* ---- animação ---- */

/* O valor de agora a caminho do alvo. A chave identifica a animação (use o id do elemento:
 * id.id, ou id.id + 1, + 2... para mais de uma). Muda o alvo e ela parte do valor de agora. */
float gv_anim(uint32_t chave, float alvo, int duracao_ms);
Clay_Color gv_anim_cor(uint32_t chave, Clay_Color alvo, int duracao_ms);

/* ---- interação (do quadro anterior: o modo imediato decide com o layout já desenhado) ---- */

bool gv_por_cima(Clay_ElementId id);     /* o ponteiro (ou o dedo) está sobre ele */
bool gv_premido(Clay_ElementId id);      /* começou nele e ainda não soltou */
/* O mesmo que gv_premido, mas só consulta: não se candidata ao toque. Serve para olhar um pai
 * depois dos filhos (quem fica com o toque é o último declarado debaixo do dedo). */
bool gv_segurado(Clay_ElementId id);
bool gv_tocado(Clay_ElementId id);       /* começou e acabou nele: um clique, um toque */
Clay_BoundingBox gv_caixa(Clay_ElementId id);
/* A tecla carregada neste quadro (um keysym do xkbcommon), ou 0. */
uint32_t gv_tecla(void);

/* ---- componentes ---- */

enum gv_estilo_botao {
	GV_BOTAO_CHEIO,    /* fundo de acento */
	GV_BOTAO_CONTORNO, /* só a borda */
	GV_BOTAO_SIMPLES,  /* só o conteúdo */
};

/* Um botão com ícone e/ou texto (NULL num deles tira-o). Devolve verdadeiro no toque. */
bool gv_botao(Clay_ElementId id, const char *icone, const char *texto, enum gv_estilo_botao estilo);

/* O botão com tudo à escolha. Comece do padrão de um estilo e mude o que quiser:
 *   gv_botao_opcoes o = gv_botao_padrao(GV_BOTAO_CHEIO);
 *   o.tamanho_texto = 18;
 *   o.largura = CLAY_SIZING_FIXED(160);
 *   if (gv_botao_ex(CLAY_ID("ok"), "check", "Ok", &o)) { ... }
 * O que não cabe na largura é cortado (o botão não vaza para cima dos vizinhos). */
typedef struct gv_botao_opcoes {
	float tamanho_icone, tamanho_texto;
	enum gv_peso peso;
	Clay_SizingAxis largura;  /* padrão: estica para ocupar o espaço */
	float altura;
	float margem;             /* o espaço dos lados, por dentro */
	float espaco;             /* entre o ícone e o texto */
	float raio;
	Clay_Color fundo;         /* transparente: só acende quando o ponteiro passa */
	Clay_Color conteudo;      /* o texto e o ícone */
	Clay_Color borda;         /* transparente: sem borda */
} gv_botao_opcoes;

gv_botao_opcoes gv_botao_padrao(enum gv_estilo_botao estilo);
bool gv_botao_ex(Clay_ElementId id, const char *icone, const char *texto, const gv_botao_opcoes *opcoes);
/* Um botão redondo só com ícone; "ligado" pinta-o como activo (perigo: em vermelho). */
bool gv_botao_redondo(Clay_ElementId id, const char *icone, float tamanho, bool ligado, bool perigo);
/* Um deslizante de 0 a 1. Devolve verdadeiro quando o valor mudou neste quadro. */
bool gv_deslizante(Clay_ElementId id, float *valor, float trilho, float puxador);
/* Um interruptor. Devolve verdadeiro quando mudou. */
bool gv_interruptor(Clay_ElementId id, bool *ligado);
/* Um separador de 1 px na cor da linha. */
void gv_separador(bool vertical, float comprimento);

/* A declaração de um cartão (superfície, borda, cantos e sombra do tema) para o CLAY():
 *   CLAY(CLAY_ID("cartao"), gv_cartao()) { ... }
 * Mude o que quiser depois: Clay_ElementDeclaration c = gv_cartao(); c.layout.padding = ...; */
Clay_ElementDeclaration gv_cartao(void);

/* Uma borda à volta (o CLAY_BORDER_ALL do Clay põe também linhas entre os filhos). */
#define GV_BORDA(largura) ((Clay_BorderWidth){ (largura), (largura), (largura), (largura), 0 })

/* Sombra num elemento: .userData = gv_sombra(raio_desfoque, deslocamento_y, alfa). */
void *gv_sombra(float desfoque, float desloca_y, float alfa);

#endif
