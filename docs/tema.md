# Tema, cores e animação

## O tema

`theme` é o tema ativo do Gravity. Os componentes leem dele a cada quadro, então **mudar um campo
muda a tela na hora**. De fábrica ele tem as cores do LUMNA, e um `tema.ini` muda o que você
quiser sem recompilar (`~/.config/gravity/tema.ini`, ou `GRAVITY_TEMA=caminho`; um exemplo está em
`gravity/exemplos/tema.ini`).

```
on_frame {
    theme.accent = colors[color].accent
    theme.radius_large = round(corners * 32)
    theme.curve = springy ? spring : smooth
}
```

### Cores

Onde se espera uma cor (`bg:`, `color:`, `border_color:`, `alpha(...)`), basta o nome. Em outro
lugar, escreva `theme.nome`.

| nome | para quê | no Gravity |
|---|---|---|
| `background` | o véu atrás de um painel | `fundo` |
| `surface` | cartões e painéis | `superficie` |
| `surface_high` | o que fica por cima de uma superfície (botões, campos) | `superficie_alta` |
| `text` | texto | `texto` |
| `muted` | legendas | `texto_suave` |
| `faint` | o menos importante | `texto_fraco` |
| `accent` | o violeta do LUMNA | `acento` |
| `accent_strong` | o acento mais forte | `acento_forte` |
| `icon` | ícones | `icone` |
| `line` | bordas e separadores | `linha` |
| `danger` | perigo, erro | `perigo` |
| `knob` | o botão redondo do deslizante | `puxador` |

E sempre: `white`, `black`, `transparent`.

### Forma, texto e movimento

| campo | tipo | |
|---|---|---|
| `theme.radius_small`, `radius_medium`, `radius_large` | float | os cantos |
| `theme.spacing` | float | a unidade de espaçamento |
| `theme.icon_stroke` | float | a grossura do traço dos ícones |
| `theme.size_caption`, `size_body`, `size_highlight`, `size_title` | float | os tamanhos de texto (os `style:` do `text`) |
| `theme.font` | string (só leitura) | a fonte, que se muda no `tema.ini` |
| `theme.duration_fast`, `duration_normal`, `duration_slow` | int (ms) | as durações das animações |
| `theme.curve` | `smooth`, `spring`, `linear` | a curva das animações |
| `theme.animations` | bool | `false`: tudo muda na hora |

O app também pode carregar um tema próprio: `theme: "/caminho/tema.ini"` no `app`, ou
`load_theme("/caminho/tema.ini")` a qualquer momento.

## Cores à mão

```
bg: "#1c1828"                   // hexadecimal
bg: "#ffffff14"                 // com opacidade (14 em hexa ≈ 8%)
bg: alpha(white, 0.08)          // o mesmo, mais legível
border_color: alpha(accent, 0.2)
color: on ? accent : muted
```

## Animação: `animate()`

`animate(alvo)` devolve um número (ou uma cor) que **caminha até o alvo** em vez de pular. Quando
o alvo muda, ele parte de onde está.

```
// um fundo que acende quando o ponteiro passa
box #close (width: 40, height: 40, radius: 20, bg: alpha(white, animate(hovered ? 0.08 : 0, fast))) {
    icon("close", 24)
}

// uma bolinha que encolhe quando é escolhida
let picked = animate(color == i ? 1 : 0)
box (width: 22 + 4 * (1 - picked), ...)

// uma cor que muda devagar
bg: animate(on ? accent : surface, slow)
```

- O segundo valor é a duração: `fast`, `normal` (padrão), `slow` (as do tema) ou um número em ms.
- A curva vem do tema (`theme.curve`). Com `theme.animations = false`, tudo muda na hora.
- Cada `animate()` é independente: um dentro de um `for` tem um por volta, e um dentro de uma `fn`
  tem um por chamada.
- Uma animação nova começa **no alvo**: ela só anima quando o alvo muda depois.
- O Gravity só redesenha enquanto há animação a rodar. Parado, não gasta nada.
