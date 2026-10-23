# Guia: o primeiro app

Este guia monta, passo a passo, o app de ajustes rápidos que está em
[`examples/ajustes.gvt`](../examples/ajustes.gvt). No fim você vai saber usar estado, layout,
listas, funções e tema, que é quase tudo o que um app do LUMNA precisa.

## 1. A ideia: a tela é uma função do estado

No GraviTy você não cria botões e depois mexe neles. Você **descreve a tela inteira** dentro de
`view { ... }`, e o Gravity redesenha essa descrição sempre que algo muda: um toque, um tamanho
novo ou uma animação. Quem guarda o que muda são as **variáveis** (`var`). Os **eventos**
(`on_tap { ... }`) só mudam essas variáveis, e a tela acompanha sozinha.

Isso tem nome, *modo imediato*, e tem uma vantagem grande: nunca existe uma tela "desatualizada"
em relação ao estado. Se `ligado` é `true`, o interruptor aparece ligado, sempre.

## 2. Olá

Crie `ajustes.gvt`:

```gvt
app Ajustes {
    title: "Ajustes rápidos"
    size: 420 x 520

    view (padding: 24, bg: "#0b0814") {
        text("Ajustes rápidos", style: title, weight: semibold)
    }
}
```

Compile e rode:

```sh
gvt build ajustes.gvt           # gera ajustes.c
cc ajustes.c -I$GRAVITY_DIR/src -I$GRAVITY_DIR/vendor/clay $GRAVITY_DIR/libgravity.a \
   $(pkg-config --cflags --libs wayland-client wayland-cursor xkbcommon cairo pangocairo) -lm -o ajustes
./ajustes
```

Ou, bem mais simples, com o CMake (veja [o passo 8](#8-no-cmake)).

- `app Ajustes { ... }` é o app. As linhas `nome: valor` lá dentro configuram a janela.
- `view` é a tela. Por padrão ele é uma **coluna** que ocupa a janela toda.
- `text(...)` desenha um texto. `style: title` usa o tamanho de título do tema, e `weight:
  semibold` deixa o texto mais grosso.
- `"#0b0814"` é uma cor, como no CSS.

## 3. Estado e eventos

Uma variável e um botão que mexe nela:

```gvt
app Ajustes {
    title: "Ajustes rápidos"
    size: 420 x 520

    var wifi = true

    view (padding: 24, gap: 16, bg: "#0b0814") {
        text("Ajustes rápidos", style: title, weight: semibold)
        text(wifi ? "Wi-Fi ligado" : "Wi-Fi desligado", color: muted)

        button #wifi_button (wifi ? "Desligar" : "Ligar", icon: "wifi") {
            on_tap { wifi = !wifi }
        }
    }
}
```

- `var wifi = true` cria o estado. O tipo (`bool`) vem do valor inicial.
- `#wifi_button` é o **id** do botão. Elementos que reagem a toques precisam de um id; nos
  outros, o GraviTy cria um sozinho. Ids podem se repetir em lugares diferentes do programa:
  dentro de um `for` ou de uma `fn`, cada cópia ganha o seu (veja [Por dentro](por-dentro.md)).
- `on_tap { ... }` roda quando o botão é tocado. `!wifi` é "o contrário de wifi".
- `cond ? a : b` escolhe entre dois valores.
- `gap: 16` põe 16 px entre os filhos da coluna.

## 4. Layout: linhas e colunas

Tudo é `row` (filhos lado a lado) ou `column` (um embaixo do outro), como o flexbox do CSS:

```
row (grow, gap: 12, align: center) {
    icon("wifi", 22)
    text("Wi-Fi", grow)
    toggle #wifi (value: wifi)
}
```

- `grow` (sozinho, sem valor) faz a linha ocupar a largura toda.
- `align: center` centraliza os filhos **no outro eixo**: numa linha, na vertical (como o
  `align-items` do CSS). Para o eixo principal use `justify:`.
- `text("Wi-Fi", grow)`: o texto ocupa o espaço que sobra e empurra o `toggle` para a direita.
- `toggle #wifi (value: wifi)`: o interruptor **muda a variável sozinho**. Não precisa de evento.

Mais sobre tamanhos, espaços e alinhamento em [Layout](layout.md).

## 5. Listas e `for`

Uma lista de **registros** (cada item com vários campos):

```
var settings = [
    {name: "Wi-Fi", icon: "wifi", on: true},
    {name: "Bluetooth", icon: "bluetooth", on: false},
    {name: "Não perturbe", icon: "moon", on: false},
]
```

E um `for` para desenhar uma linha por item:

```
card (grow, padding: 8) {
    for s in settings {
        row (grow, height: 52, padding_x: 12, gap: 12, align: center) {
            icon(s.icon, 22, color: s.on ? accent : muted)
            text(s.name, grow)
            toggle #switch (value: s.on)
        }
    }
}
```

- `card` é um cartão com a cara do LUMNA: superfície, borda, cantos e sombra do tema.
- `s.on` lê um campo. Dentro do `for`, mudar `s.on` muda o item da lista de verdade.
- `#switch` se repete em cada volta do `for`, e não tem problema: cada volta ganha o seu id.
- `accent` e `muted` são cores do tema (veja [Tema](tema.md)).

## 6. Funções que desenham

Quando um pedaço da tela cresce, tire ele para uma `fn`. Uma `fn` sem tipo de retorno pode
desenhar, e funciona como um componente:

```
fn setting_row(i: int) {
    let on = settings[i].on
    row #line (grow, height: 52, padding_x: 12, gap: 12, align: center, radius: 12,
               bg: alpha(white, animate(hovered ? 0.05 : 0, fast))) {
        icon(settings[i].icon, 22, color: on ? accent : muted)
        text(settings[i].name, grow)
        toggle #switch (value: settings[i].on)
    }
}
```

E no `view`:

```
for i in 0..len(settings) {
    setting_row(i)
}
```

- Parâmetros têm tipo: `i: int`. Os tipos são `int`, `float`, `bool`, `string` e `color`.
- `0..len(settings)` vai de 0 até o tamanho da lista, **sem** incluir o último (0, 1, 2).
- `hovered` é verdadeiro quando o ponteiro está sobre o elemento. `animate(x, fast)` faz o valor
  chegar a `x` suavemente, e `alpha(white, ...)` é o branco com essa transparência. O resultado é
  um fundo que acende quando o mouse passa.

Funções também calculam valores. Nesse caso, diga o tipo com `->`:

```
fn count_on() -> int {
    var n = 0
    for s in settings {
        if s.on { n += 1 }
    }
    return n
}
```

## 7. Textos com valores

Coloque qualquer valor dentro de um texto com `{ }`:

```
text("{count_on()} de {len(settings)} ligados", style: caption, color: faint)
text("{round(brightness * 100)}%", width: 44, align: end)
text("{temperatura:.1} °C")     // uma casa decimal
```

## 8. No CMake

```cmake
cmake_minimum_required(VERSION 3.16)
project(meus_apps C)

include(/caminho/GraviTy/cmake/GraviTy.cmake)
gravity_runtime(/caminho/LUMNA_OS/gravity)
gravity_add_app(ajustes ajustes.gvt)
```

```sh
cmake -B build && cmake --build build && ./build/ajustes
```

O `.gvt` vira C no build e volta a ser gerado sempre que você muda o arquivo. Se der erro no
`.gvt`, o build para e mostra a linha.

## O app inteiro

Está em [`examples/ajustes.gvt`](../examples/ajustes.gvt). Para continuar:

- [A linguagem](linguagem.md): tudo sobre variáveis, tipos e controle de fluxo;
- [Elementos](elementos.md): cada elemento e as suas propriedades;
- [Erros comuns](erros-comuns.md): quando o compilador reclamar.
