# Por dentro

Como o `.gvt` vira C, e por que isso não custa nada em execução.

## O caminho

```
mixer.gvt ──gvt──▶ mixer.c ──gcc/clang──▶ mixer (código de máquina)
                      │
                      └── #include "gravity.h"  (CLAY(...) e gv_*)
```

O `gvt` é escrito em Python, mas **só roda na hora de compilar**. O app final é C puro ligado à
`libgravity`: não há interpretador, máquina virtual nem coletor de lixo. O C gerado é o mesmo que
você escreveria à mão, e o mixer em `.gvt` dá a mesma tela do `mixer.c`, pixel a pixel.

## O que sai

Este `.gvt`:

```
app Ola {
    var taps = 0
    view (center, gap: 16) {
        button #more ("Tocar", icon: "check") {
            on_tap { taps += 1 }
        }
        text("Você tocou {taps} vez(es).", color: muted)
    }
}
```

vira (resumido):

```c
static struct {
	int taps;
} s = {
	.taps = 0,
};

static void gvt_draw(gv_app *app, void *dados) {
	Clay_ElementId _e1 = GVT_ID("view", 0, 0);
	CLAY(_e1, {
		.layout = { .layoutDirection = CLAY_TOP_TO_BOTTOM, .sizing = { ... GROW ... }, .childGap = 16, ... },
	}) {
		Clay_ElementId _e2 = GVT_ID("more", 0, 0);
		if (gv_botao(_e2, "check", "Tocar", GV_BOTAO_CHEIO)) {
			s.taps += 1;
		}
		gv_texto(gv_fmt("Você tocou %d vez(es).", s.taps), gv_t.tamanho_corpo, gv_t.texto_suave, GV_PESO_NORMAL);
	}
}

int main(int argc, char **argv) {
	gvt_app = gv_app_criar(&(gv_opcoes){ .titulo = "Ola" });
	return gv_app_correr(gvt_app, gvt_draw, NULL);
}
```

- As **variáveis do app** viram uma `struct` estática `s`. Valores constantes vão direto no
  inicializador; os calculados (`has_arg(...)`) são iniciados no `main`.
- O **`view`** vira a função de desenho que o Gravity chama a cada quadro.
- Cada **elemento** vira um `CLAY(id, { ... })` com só as propriedades que você deu.
- Cada **componente** vira a chamada `gv_*` correspondente, e o evento vira o `if` do valor que ela
  retorna.
- Os **textos com `{ }`** viram `gv_fmt(...)`, alocados no quadro (sem `malloc`).
- **Registros** viram `struct`, e **listas** viram vetores de tamanho fixo.
- **Funções** viram funções `static` do C (`fn_nome`).

Para ver o C de qualquer `.gvt`: `gvt build app.gvt -o app.c`. No CMake ele fica em `build/gvt/`.

## Os ids

O Clay identifica cada elemento por um número (o hash de um nome). O Gravity usa esse id para
saber em quem o dedo está, qual animação é de quem e qual lista rola. O GraviTy monta o id com
três coisas:

```c
#define GVT_ID(nome, indice, semente) Clay__HashStringWithOffset(CLAY_STRING(nome), (uint32_t)(indice), (semente))
```

1. **o nome**: o seu `#nome`, ou um nome tirado da linha e da coluna se você não deu nenhum;
2. **o índice**: dentro de um `for`, o índice da volta. Com dois `for`, um id encadeia o outro,
   então cada volta de cada laço tem o seu;
3. **a semente**: cada `fn` que desenha recebe um `_seed` diferente **por chamada**, então
   `setting_row(0)` e `setting_row(1)` não se misturam, mesmo com os mesmos `#id` lá dentro.

As chaves do `animate()` são feitas do mesmo jeito.

Consequência prática: `hovered(#card)` acha o `#card` do **mesmo lugar** (o mesmo `view`, a mesma
volta, a mesma chamada de `fn`). Um id de dentro de uma `fn` não é visto de fora dela.

## Eventos e o modo imediato

`on_tap { ... }` vira `if (gv_tocado(id)) { ... }`, colocado **antes** do `CLAY(...)` do
elemento. Assim a mudança de estado já aparece no mesmo quadro. O `gv_tocado` olha o layout do
quadro anterior, que é como o Gravity sabe onde cada elemento está.

Nos componentes (`button`, `slider`...), o evento vira o `if` da própria chamada:
`if (gv_botao(...)) { ... }`.

## Por que não dá `break` dentro de um elemento

O `CLAY(...) { ... }` do Clay é um `for` disfarçado: ele abre o elemento, roda o corpo uma vez e
fecha. Um `break` (ou `continue`, ou `return`) lá dentro pula o fechamento e estraga o layout, e o
GraviTy recusa isso já na compilação.

## Arquivos do compilador

| arquivo | |
|---|---|
| `gvt/lexer.py` | o texto vira tokens (e decide onde uma linha termina) |
| `gvt/parser.py` | os tokens viram a árvore do programa (`gvt/syntax.py`) |
| `gvt/compiler.py` | a árvore é conferida (tipos, nomes, ids) e vira C |
| `gvt/errors.py` | as mensagens de erro, com a linha e o `^` |
| `gvt/__main__.py` | a linha de comando (`gvt build`, `gvt check`) |
