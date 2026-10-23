# Layout

O layout do GraviTy é o do [Clay](https://github.com/nicbarker/clay), que funciona como o
flexbox do CSS: cada contêiner põe os filhos **numa direção** (`row`: lado a lado; `column`: um
embaixo do outro), com espaço por dentro (`padding`), espaço entre eles (`gap`) e um alinhamento.
As medidas são **pixels lógicos**, os mesmos do CSS: numa tela com escala 2, o Gravity desenha
com o dobro.

## Tamanho: `width` e `height`

| valor | o que faz | no Clay |
|---|---|---|
| (nada) | do tamanho do conteúdo | `FIT` |
| `120` | exatamente 120 px | `FIXED(120)` |
| `grow` | ocupa o que sobrar no pai | `GROW(0)` |
| `grow(200, 420)` ou `grow(max: 420)` | cresce, entre o mínimo e o máximo | `GROW(200, 420)` |
| `fit` / `fit(62)` | do tamanho do conteúdo, com um mínimo | `FIT(62)` |
| `percent(0.5)` ou `"50%"` | metade do pai | `PERCENT(0.5)` |

E as palavras soltas, para o caso mais comum:

- `grow`: `width: grow` (a largura toda);
- `fill`: `width: grow` e `height: grow`.

```
card #card (width: grow(0, 420), padding: [22, 20, 16, 20]) { ... }   // até 420 px de largura
row (grow, height: fit(62)) { ... }   // largura toda, no mínimo 62 de altura
```

Quando vários irmãos têm `grow`, eles dividem o espaço que sobra.

## Espaço: `padding` e `gap`

`padding` segue a ordem do CSS:

```
padding: 16                 // os quatro lados
padding: [14, 16]           // [cima e baixo, esquerda e direita]
padding: [22, 20, 16, 20]   // [cima, direita, baixo, esquerda]
padding_x: 16               // esquerda e direita
padding_top: 22             // um lado só (vale por cima do padding)
```

`gap: 12` põe 12 px entre cada filho, na direção do contêiner.

## Alinhamento: `align`, `justify` e `center`

Como no CSS:

- **`justify`** alinha os filhos no **eixo principal**: na horizontal num `row`, na vertical
  numa `column`;
- **`align`** alinha os filhos no **eixo cruzado**: na vertical num `row`, na horizontal numa
  `column`;
- **`center`** (palavra solta) centraliza nos dois eixos.

Valores: `start`, `center`, `end`. `left`, `right`, `top` e `bottom` também valem e indicam o
lado exato.

```
row (grow, gap: 12, align: center) { ... }   // filhos centrados na vertical
column (justify: end) { ... }                // filhos lá embaixo
view (center) { ... }                        // tudo no meio da janela
```

Para empurrar algo até o fim de uma linha, use um `spacer` ou um `text(..., grow)` antes dele.

## Por cima de tudo: `float`

Um elemento com `float` sai do fluxo: não empurra os irmãos e aparece por cima, preso ao pai.
É assim que se faz uma lista suspensa, um menu ou um balão:

```
row #chip (...) {
    on_tap { open = !open }
    text("Alto-falante")
    if open {
        column #list (width: 230, float: below_right, offset: [0, 6], shadow: [24, 14, 0.5], ...) {
            ...
        }
    }
}
```

`below_right` alinha a direita da lista com a direita do pai, logo abaixo dele. Os outros:
`below`, `below_left`, `above`, `above_left`, `above_right`, `left`, `right`, `center`,
`top_left`, `top_right`, `bottom_left`, `bottom_right`. `offset: [x, y]` afasta um pouco e `z`
escolhe quem fica por cima (padrão 10).

## Rolar: `scroll`

```
column #lista (grow, height: 300, scroll: vertical) {
    for item in items { ... }
}
```

O conteúdo que passa da altura rola com a roda do mouse, o touchpad ou o dedo. O contêiner precisa
de um tamanho (aqui `height: 300`, ou `grow` dentro de um pai com tamanho). `clip` (palavra solta)
só corta, sem rolar.

## Bordas e cantos

```
box (radius: 12, border: 1, border_color: alpha(white, 0.12)) { ... }
column (border_bottom: 1, border_color: alpha(white, 0.08)) { ... }   // uma linha embaixo
```

## Dicas

- Pense de fora para dentro: a `view` é a janela, e cada `row`/`column` divide o espaço do pai.
- Quando algo não aparece onde deveria, dê um `bg: "#ff000040"` temporário para ver a caixa.
- O texto não quebra linha sozinho, a não ser que a caixa dele tenha largura (`width:` ou `grow`).
