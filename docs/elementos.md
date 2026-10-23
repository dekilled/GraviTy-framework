# Elementos

Um elemento se escreve assim:

```
tipo #id (propriedades) {
    filhos
    on_evento { ... }
}
```

Tudo é opcional menos o tipo: `spacer`, `text("oi")`, `row (gap: 8) { ... }`,
`button #ok ("Ok") { on_tap { ... } }`.

- **`#id`** dá nome ao elemento. Quem reage a toques (`button`, `slider`, `toggle`, `round_button`,
  contêineres com `on_tap`, ou quem usa `hovered`/`pressed`) precisa de um id, mas o GraviTy
  cria um sozinho se você não der. Dê um id quando quiser falar do elemento de outro lugar:
  `hovered(#card)`. Para ids numa lista, use `#nome[i]`. Dentro de um `for` isso já acontece
  sozinho, então `#nome` basta.
- **Propriedades** são `nome: valor`. Algumas são **palavras soltas** (`grow`, `center`...).
  Alguns elementos aceitam o primeiro valor sem nome: `text("oi")` é `text(text: "oi")`.
- **Eventos** (`on_tap`, `on_hover`...) ficam no corpo, em qualquer lugar entre os filhos. O que
  está dentro deles muda o estado. Eles não desenham: elementos dentro de um evento são erro.

Dentro das propriedades e do corpo de um elemento, `hovered` (o ponteiro está em cima) e `pressed`
(foi tocado e ainda não soltou) falam **desse** elemento.

## Eventos

| evento | quando roda | quem tem |
|---|---|---|
| `on_tap` | um toque ou clique: começou **e** terminou no elemento | contêineres, `text` com caixa, `button`, `round_button` |
| `on_hover` | o ponteiro (ou o dedo) **entrou** no elemento | todos os de cima, `slider` e `toggle` |
| `on_leave` | o ponteiro **saiu** do elemento | os mesmos |
| `on_press` | o toque **começou** no elemento (o botão do mouse desceu) | os mesmos |
| `on_release` | o toque **terminou** (soltou), dentro ou fora do elemento | os mesmos |
| `on_change` | o valor mudou | `slider` e `toggle` |

```
button #inc ("Increase", icon: "plus") {
    on_tap { count += 1 }
    on_hover { status = "em cima do botão" }
    on_leave { status = "" }
}
slider #volume (value: volume) {
    on_press { dragging = true }
    on_release { dragging = false }
}
```

- `on_hover`/`on_leave` e `on_press`/`on_release` rodam **uma vez** na mudança. Para algo que
  vale **enquanto** o ponteiro está em cima, use o estado: `bg: hovered ? "#333" : "#222"`. É mais
  simples e não precisa de variável.
- Um clique completo dispara, na ordem: `on_press`, `on_release` e `on_tap`.
- O toque é de quem está **mais por dentro**: apertar um `button` dentro de um `row` dispara o
  `on_press` do botão, e não o do `row`. Já o `on_hover` vale para os dois, porque o ponteiro está
  em cima de ambos.
- Com toque (celular), `on_hover` roda quando o dedo encosta e `on_leave` quando ele sai.
- Se um elemento some da tela (dentro de um `if`) com o ponteiro em cima, o `on_leave` dele roda
  quando ele voltar a aparecer.
- Nomes de outros lugares (`on_click`, `on_mouseover`, `on_mouseout`...) dão erro com o nome
  certo na dica.

---

## Contêineres: `view`, `row`, `column`, `box`, `card`

Guardam outros elementos.

| | direção | começa com |
|---|---|---|
| `view` | coluna | a janela inteira (`fill`). É a raiz: um por app |
| `row` | linha (lado a lado) | o tamanho dos filhos |
| `column` | coluna (um embaixo do outro) | o tamanho dos filhos |
| `box` | linha | o tamanho dos filhos: uma caixa genérica |
| `card` | coluna | o cartão do LUMNA: superfície, borda, `radius_large`, `padding: 20` e sombra |

Propriedades (as mesmas para todos; detalhes em [Layout](layout.md)):

| propriedade | valor | |
|---|---|---|
| `grow` | palavra solta | ocupa a largura disponível |
| `fill` | palavra solta | ocupa a largura e a altura |
| `center` | palavra solta | centraliza os filhos nos dois eixos |
| `clip` | palavra solta | corta o que passa das bordas |
| `width`, `height` | `120`, `grow`, `fit`, `grow(0, 420)`, `fit(62)`, `percent(0.5)`, `"50%"` | o tamanho |
| `padding` | `16`, `[vertical, horizontal]`, `[cima, direita, baixo, esquerda]` | o espaço por dentro (ordem do CSS) |
| `padding_x`, `padding_y` | número | dos lados / em cima e embaixo |
| `padding_top`, `padding_right`, `padding_bottom`, `padding_left` | número | um lado |
| `gap` | número | o espaço entre os filhos |
| `align` | `start`, `center`, `end` (ou `top`/`bottom`, `left`/`right`) | os filhos no eixo cruzado (como `align-items`) |
| `justify` | o mesmo | os filhos no eixo principal (como `justify-content`) |
| `bg` (ou `background`) | uma cor | o fundo |
| `radius` | número | os cantos arredondados |
| `border` | número | a borda em volta |
| `border_top`, `border_right`, `border_bottom`, `border_left` | número | a borda de um lado só |
| `border_color` | uma cor | a cor da borda (sem ela: `line` do tema) |
| `float` | `below`, `below_left`, `below_right`, `above`, `above_left`, `above_right`, `left`, `right`, `center`, `top_left`, `top_right`, `bottom_left`, `bottom_right` | flutua por cima de tudo, preso ao pai |
| `offset` | `[x, y]` | desloca um elemento flutuante |
| `z` | int | a ordem dos flutuantes (padrão 10) |
| `shadow` | `true` ou `[desfoque, y, opacidade]` | sombra macia |
| `scroll` | `vertical`, `horizontal`, `both` | rola com o dedo, o mouse e a roda |
| `direction` | `row`, `column` | troca a direção (útil no `card` e no `box`) |

Eventos: **`on_tap`**, quando o elemento é tocado (o toque começa e termina nele), e os de
ponteiro (`on_hover`, `on_leave`, `on_press`, `on_release`), [descritos acima](#eventos).

```
row #chip (height: 50, padding_x: 16, gap: 10, align: center, radius: 25,
           bg: alpha(white, pressed ? 0.1 : 0.04), border: 1, border_color: alpha(white, 0.12)) {
    on_tap { open = !open }
    icon("speaker", 20)
    text("Alto-falante", size: 14)
}
```

---

## `text`

```
text("Olá")
text("Mixer de áudio", style: title, weight: semibold)
text("{pct(volume)}%", width: 44, align: end)
text(name, size: 14, grow)
```

| propriedade | valor | padrão |
|---|---|---|
| `text` (o 1.º valor) | `string` (com interpolação) | (obrigatório) |
| `style` | `caption`, `body`, `highlight`, `title` | `body` |
| `size` | número (troca o `style`) | o do `style` |
| `color` | uma cor | `text` |
| `weight` | `normal`, `medium`, `semibold`, `bold` | `normal` |

O texto também aceita **as propriedades de contêiner** (`grow`, `width`, `padding`, `bg`...). Com
elas, o texto ganha uma caixa em volta, e então **`align` alinha o texto dentro da caixa**
(`start`, `center`, `end`). Com caixa, `on_tap` também funciona.

---

## `icon`

```
icon("volume")
icon("close", 24)
icon("check", 16, color: accent)
```

| propriedade | valor | padrão |
|---|---|---|
| `name` (o 1.º valor) | o nome de um ícone do LUMNA | (obrigatório) |
| `size` (o 2.º valor) | número | `24` |
| `color` | uma cor | `icon` do tema |

Os ícones são os mesmos 130 do shell do LUMNA (`shell/src/components/Icon.vue`, no LUMNA_OS). O
`gvt` avisa quando o nome não existe e sugere o certo. A lista está em `gravity/src/gv_icones.c`.

---

## `button`

```
button #save ("Salvar", icon: "check") {
    on_tap { save() }
}
button #reset ("Redefinir", icon: "refresh", style: outline) { ... }
button #more (icon: "dots", style: plain) { ... }
```

| propriedade | valor | padrão |
|---|---|---|
| `text` (o 1.º valor) | `string` | sem texto |
| `icon` | o nome de um ícone | sem ícone |
| `style` | `filled` (cheio, de acento), `outline` (só a borda), `plain` (só o conteúdo) | `filled` |

Precisa de texto, de ícone ou dos dois. Eventos: **`on_tap`** e os [de ponteiro](#eventos).

O `button` **não tem `size`**: ele tem 52 px de altura e **estica para ocupar a largura que
tiver**. Para ele ficar mais estreito, ponha numa caixa com a largura que quiser:

```
box (width: 200) {                 // ou width: "50%"
    button #ok ("Ok", icon: "check") { on_tap { ... } }
}
row (grow, gap: 10) {              // dois numa linha dividem o espaço
    button #no ("Cancelar", style: outline) { on_tap { ... } }
    button #yes ("Ok", icon: "check") { on_tap { ... } }
}
```

Para um botão redondo com tamanho, use o [`round_button`](#round_button). Para um botão com
altura e conteúdo próprios, use um contêiner:

```
row #big (height: 64, padding_x: 24, gap: 10, align: center, radius: 32, bg: accent) {
    on_tap { count += 1 }
    icon("plus", 24, color: white)
    text("Increase", weight: semibold)
}
```

---

## `round_button`

O botão redondo **só com ícone**, como os do mixer e dos ajustes rápidos. É o único botão com
`size`.

```
round_button #wifi (icon: "wifi", size: 52, on: wifi) {
    on_tap { wifi = !wifi }
}
round_button #mute (icon: muted ? "mute" : "volume", on: muted, danger: true) { ... }
```

| propriedade | valor | padrão |
|---|---|---|
| `icon` (o 1.º valor) | o nome de um ícone | (obrigatório) |
| `size` | número | `44` |
| `on` | `bool`: pinta como ativo | `false` |
| `danger` | `bool`: o "ativo" fica vermelho | `false` |

Eventos: **`on_tap`** e os [de ponteiro](#eventos).

---

## `slider`

Um deslizante de 0 a 1 (volume, brilho...). Ocupa a largura que sobrar.

```
slider #volume (value: volume)
slider #brightness (value: brightness, track: 10, knob: 24)
```

| propriedade | valor | padrão |
|---|---|---|
| `value` (o 1.º valor) | um `float` | (obrigatório) |
| `track` | a grossura do trilho | `12` |
| `knob` | o tamanho do botão redondo | `28` |

Se `value` é uma variável (ou um campo, ou um item de lista), **o slider muda ela sozinho**.

Se `value` é uma conta, o slider só mostra o resultado. Para reagir quando ele mexe, use
**`on_change`**, onde `value` é o valor novo:

```
// mudo mostra 0, mas o volume fica guardado
slider #volume[i] (value: a.muted ? 0.0 : a.volume) {
    on_change {
        a.volume = value
        a.muted = false
    }
}
```

`on_change` também funciona com uma variável: roda depois de ela mudar.

---

## `toggle`

O interruptor liga/desliga animado.

```
toggle #wifi (value: wifi)
toggle #anim (value: animations) {
    on_change { print("animações: {value}") }
}
```

`value` é um `bool` e funciona como no `slider`: com uma variável, ele muda sozinho; com uma conta,
use `on_change`.

---

## `separator`

Uma linha de 1 px na cor `line` do tema.

```
separator               // atravessa o pai todo
separator(length: 40)   // 40 px
separator(vertical)
```

Num `row` ele é vertical e numa `column`, horizontal. `vertical` e `horizontal` forçam a
direção. Sem `length`, ocupa o pai todo.

---

## `spacer`

Um espaço vazio.

```
row (grow) {
    text("Animações")
    spacer                  // empurra o toggle para a direita
    toggle #anim (value: animations)
}
spacer(8)                   // 8 px fixos
```

Sem valor, ocupa o espaço que sobrar no eixo do pai: largura num `row`, altura numa `column`.
Com valor, ocupa só aqueles pixels.
