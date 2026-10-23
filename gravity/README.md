# Gravity

> O Gravity mora aqui no **GraviTy-framework** desde que saiu do LUMNA_OS (branch `lumna-mobile`,
> commit `a1fa96e`). Para escrever apps sem C, em `.gvt`, veja a [documentação do GraviTy](../docs/guia.md).

A interface do LUMNA OS em C. O LUMNA roda em cima do **Orbit** (o compositor) e é desenhado pelo
**Gravity**: componentes com a cara do LUMNA, leves (o mixer inteiro usa ~2,5 MB só dele, o resto
são bibliotecas partilhadas) e mudáveis por tema — cor, tamanho, cantos, texto e movimento.

## Como funciona

- **Modo imediato.** A app tem uma função `desenhar` que declara a tela inteira a cada quadro, com o
  layout do [Clay](https://github.com/nicbarker/clay) (flexbox em C: `CLAY(id, {...}) { filhos }`) e
  os componentes `gv_*`. Não há árvore de objectos para manter: o estado é o da app.
- **Só desenha quando precisa:** entrada, tamanho novo ou uma animação a correr, ao ritmo do ecrã
  (frame callback do Wayland). Parado, não gasta nada.
- **Wayland direto:** uma janela (xdg-shell) ou uma camada do LUMNA (layer-shell: barra, painel,
  teclado, bloqueio), com rato, **toque** (o primeiro dedo) e teclado, na escala do ecrã.
- **Desenho:** cairo; **texto:** pango (acentos, emoji, ligaduras, a fonte do tema).
- **Ícones:** os mesmos 130 do shell (`shell/src/components/Icon.vue`), lidos do traço SVG.
  `sh gravity/ferramentas/icones.sh /caminho/LUMNA_OS/shell/src/components/Icon.vue` regenera
  `src/gv_icones.c` quando o shell ganha ícones.

## Componentes

| | |
|---|---|
| `gv_texto`, `gv_rotulo` | texto com tamanho, cor e peso |
| `gv_icone` | um ícone do LUMNA |
| `gv_botao` | botão cheio, de contorno ou simples, com ícone e/ou texto |
| `gv_botao_redondo` | botão redondo (ligado / perigo), como os do mixer e dos ajustes rápidos |
| `gv_deslizante` | volume, brilho... (arrastar com o dedo ou o rato) |
| `gv_interruptor` | liga/desliga animado |
| `gv_separador` | linha de 1 px |
| `gv_cartao()` | a declaração de um cartão: superfície, borda, cantos e sombra |
| `gv_sombra()` | sombra macia em qualquer elemento |
| `gv_anim`, `gv_anim_cor` | qualquer número ou cor animado até ao alvo |
| `gv_tocado`, `gv_premido`, `gv_por_cima`, `gv_tecla` | interação |

## Tema

`gv_t` é o tema activo; os componentes lêem dele a cada quadro, então mudar um campo muda a tela.
De fábrica é o do LUMNA (as cores do `styles.css` e do mixer). Um `tema.ini` muda o que quiser
sem recompilar — `~/.config/gravity/tema.ini` ou `GRAVITY_TEMA=caminho`. Exemplo em
[`exemplos/tema.ini`](exemplos/tema.ini): cores, raios, espaçamento, grossura dos ícones, fonte,
tamanhos de texto, durações, curva (`suave`, `mola`, `linear`) e animações ligadas ou não.

## Compilar e testar

Precisa de `wayland`, `wayland-protocols`, `libxkbcommon`, `cairo` e `pango` (no Arch:
`sudo pacman -S --needed wayland wayland-protocols libxkbcommon cairo pango`).

```
cd gravity
make
./mixer              # o mixer de áudio do LUMNA, numa janela
./mixer --camada     # como no celular: uma camada por cima de tudo
./galeria            # os componentes, com o tema mudando ao vivo
```

Roda em qualquer compositor Wayland (Hyprland, Sway, Orbit...). Dentro do Orbit, o toque de teste
dele também serve: `orbit-msg toque baixo 0 X Y`.

## Uma app mínima

```c
#include "gravity.h"

static void desenhar(gv_app *app, void *dados) {
    CLAY(CLAY_ID("raiz"), { .layout = { .padding = CLAY_PADDING_ALL(24), .childGap = 12 } }) {
        gv_texto(CLAY_STRING("Olá, LUMNA"), gv_t.tamanho_titulo, gv_t.texto, GV_PESO_SEMINEGRITO);
        if (gv_botao(CLAY_ID("sair"), "close", "Sair", GV_BOTAO_CHEIO)) {
            gv_app_sair(app);
        }
    }
}

int main(void) {
    gv_app *app = gv_app_criar(&(gv_opcoes){ .titulo = "Olá", .largura = 360, .altura = 200 });
    return app ? gv_app_correr(app, desenhar, NULL) : 1;
}
```

`cc ola.c -Isrc -Ivendor/clay libgravity.a $(pkg-config --cflags --libs wayland-client wayland-cursor xkbcommon cairo pangocairo) -lm`

## O que vem a seguir

- campo de texto (cursor, seleção, o teclado do LUMNA pelo text-input);
- listas que rolam com física de dedo e vários dedos (pinça, deslizar);
- imagens (ícones das apps, capas de álbum);
- o mixer ligado ao PipeWire de verdade, e depois outras peças do LUMNA em Gravity;
- desenho na GPU quando o cairo não chegar.

O Clay vem em `vendor/clay` (licença zlib), no commit `e6cc369` do repositório dele.
