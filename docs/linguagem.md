# A linguagem

Tudo o que o GraviTy entende, menos os elementos de tela, que estão em [Elementos](elementos.md).

## O arquivo

Um `.gvt` tem **um** `app`. Funções (`fn`) e variáveis (`var`, `let`) podem ficar dentro do
`app` ou fora dele, no topo do arquivo: é a mesma coisa, e elas se enxergam de qualquer lugar,
em qualquer ordem.

```gvt
// comentário de uma linha
/* comentário
   de várias linhas */

app Relogio {
    title: "Relógio"
    size: 300 x 120

    view (center) {
        text("{hours}:{minutes}", style: title)
    }
}

var hours = 9
var minutes = 41
```

### Linhas

Cada comando fica na sua linha. Uma linha **continua** na próxima quando termina num operador
(`+`, `and`, `?`...), numa vírgula, ou com um `(` ou `[` ainda aberto, então pode quebrar à vontade
dentro das propriedades de um elemento:

```
row #chip (height: 50, padding_x: 16, gap: 10,
           align: center, radius: 25) {
```

Para pôr dois comandos na mesma linha, separe com `;`: `on_tap { output = i; open = false }`.

## Variáveis

```
var volume = 0.62        // var: muda
let outputs = ["Alto-falante", "HDMI"]   // let: não muda
var size: float = 16     // o tipo escrito à mão (aqui, sem ele seria int)
```

- O **tipo vem do valor inicial**: `0` é `int`, `0.5` é `float`, `true` é `bool`, `"oi"` é
  `string`, `"#a78bfa"` é `color`.
- Variáveis de fora de funções são o **estado do app**: vivem enquanto o app roda.
- Variáveis dentro de `view`, de um elemento ou de uma `fn` são **locais**: são criadas de novo a
  cada quadro e somem no fim do bloco.
- Mudar uma `let` é erro de compilação. Isso ajuda a achar bugs.
- Uma variável local (ou um parâmetro) que ninguém usa gera um aviso.

## Tipos

| tipo | exemplos | |
|---|---|---|
| `int` | `0`, `42`, `-3`, `0xff`, `1_000` | número inteiro |
| `float` | `0.5`, `16.0`, `1500.0` | número com casas decimais |
| `bool` | `true`, `false` | verdadeiro ou falso |
| `string` | `"Olá"`, `"Volume {v}%"` | texto |
| `color` | `"#a78bfa"`, `"#ffffff80"`, `accent`, `alpha(white, 0.1)` | cor |
| `[T]` | `[1, 2, 3]`, `["a", "b"]` | lista de tamanho fixo |
| registro | `{name: "Emma", volume: 0.5}` | vários campos juntos |

Um `int` entra onde se espera um `float` sem você fazer nada. O contrário pede `round(x)` (que
arredonda) ou `int(x)` (que corta as casas).

## Números e contas

`+ - * / %`, com a precedência de sempre, e parênteses.

- **`/` sempre dá `float`**: `1 / 2` é `0.5`, como numa calculadora. Para a divisão inteira, use
  `int(a / b)`.
- `%` é o resto da divisão (também funciona com `float`).
- `x += 1`, `x -= 1`, `x *= 2`, `x /= 2` mudam a variável.

## Textos

```
"Olá"
"linha 1\nlinha 2"              // \n \t \" \\ \{ \}
"Volume {volume * 100}%"         // interpolação: qualquer expressão entre { }
"{temperature:.1} °C"            // :.1 = uma casa decimal (só para float)
"{{ isto fica com chaves }}"     // {{ e }} viram { e }
```

- Dentro de `{ }` vai qualquer valor: `int`, `float`, `bool`, `string` ou uma chamada de função.
- `+` **não** junta textos. Use a interpolação: `"{a} {b}"`.
- `==` e `!=` comparam o conteúdo: `if name == "Emma"`.

## Cores

| como | exemplo |
|---|---|
| hexadecimal, como no CSS | `"#a78bfa"`, `"#a78bfa80"` (os dois últimos dígitos são a opacidade) |
| uma cor do tema | `accent`, `text`, `muted`, `surface`... (lista em [Tema](tema.md)) |
| nomes prontos | `white`, `black`, `transparent` |
| com transparência | `alpha(white, 0.08)`, `alpha(accent, 0.2)` |
| de um número | `rgb(0xa78bfaff)` |

Os nomes do tema valem onde se espera uma cor (`bg:`, `color:`, `border_color:`...). Em qualquer
outro lugar, escreva `theme.accent`. Uma cor tem os campos `.r`, `.g`, `.b` e `.a`, de 0 a 255.

## Comparações e lógica

`== != < > <= >=`, e `and`, `or`, `not` (ou `&&`, `||`, `!`, se preferir).

```
if volume > 0.5 and not muted { ... }
let label = open ? "Fechar" : "Abrir"     // condição ? se sim : se não
```

A condição de um `if` tem que ser `bool`. `if count { }` é erro; escreva `if count > 0 { }`.

## `if`

```
if output == i {
    icon("check", 16, color: accent)
} else if output > i {
    text("antes")
} else {
    spacer
}
```

## `for` e `while`

```
for name in outputs { ... }           // cada item
for i, name in outputs { ... }        // o índice e o item
for i in 0..5 { ... }                 // 0, 1, 2, 3, 4
for i in 1..=5 { ... }                // 1, 2, 3, 4, 5
while n < 10 { n += 1 }
```

- Num `for` sobre uma lista de **registros**, mudar o item muda a lista:
  `for a in apps { a.volume = 1 }`.
- Num `for` sobre números ou textos, o item é uma cópia. Para mudar, use o índice: `xs[i] = 0`.
- `break` sai do laço e `continue` pula para a próxima volta. Os dois **não** podem ficar
  dentro de um elemento que está dentro do laço (o Clay precisa fechar cada elemento). Ponha a
  condição num `if` em volta do elemento.
- Dentro de um `while`, elementos que precisam de id pedem um `#nome[i]` explícito. Prefira `for`.

## Funções

```
fn pct(v: float) -> int {
    return round(v * 100)
}

fn section_title(title: string) {
    box (padding_top: 18, padding_bottom: 6) {
        text(title, style: caption, color: faint, weight: semibold)
    }
}
```

- Os parâmetros sempre têm tipo: `int`, `float`, `bool`, `string` ou `color`.
- **Com `-> tipo`** a função calcula e retorna um valor. Ela não pode desenhar.
- **Sem `-> tipo`** a função pode desenhar elementos, e funciona como um componente. Os ids dentro
  dela são locais a cada chamada, então dá para chamar a mesma função várias vezes.
- Argumentos podem ter nome: `slider_row(label: "Brilho", value: 0.5)`.
- Funções podem ser chamadas antes de aparecerem no arquivo.

## Listas

```
let outputs = ["Alto-falante", "Fones Bluetooth", "HDMI"]
var levels = [0.8, 0.5, 0.3]

text(outputs[1])           // "Fones Bluetooth"
levels[0] = 1              // muda um item (só numa var)
text("{len(outputs)}")     // 3
```

- As listas têm **tamanho fixo**: o do valor inicial. Ainda não dá para acrescentar nem tirar
  itens (veja [Próximos passos](roadmap.md)).
- Dá para mudar item a item, mas não trocar a lista inteira de uma vez.

## Registros

```
var apps = [
    {name: "Música", icon: "music", volume: 0.8, muted: false},
    {name: "Emma", icon: "waves", volume: 0.55, muted: false},
]
var player = {title: "Sem título", playing: false}

text(apps[0].name)
player.playing = true
```

- Todos os registros de uma lista têm que ter os mesmos campos.
- Os campos são `int`, `float`, `bool`, `string` ou `color`. Listas dentro de registros ainda não
  existem.

## O `app`

```
app Mixer {
    title: "Mixer de áudio"      // o título da janela
    id: "lumna-mixer"            // o app_id (o compositor usa para ícone e regras)
    size: 460 x 660              // largura x altura, em pixels lógicos
    kind: window                 // window (janela) ou layer (camada do LUMNA)
    layer: overlay               // só camadas: background, bottom, top, overlay
    anchors: all                 // só camadas: all ou [top, bottom, left, right]
    exclusive: 40                // só camadas: a zona exclusiva (uma barra, por exemplo)
    keyboard: true               // só camadas: quer o teclado
    theme: "/caminho/tema.ini"   // um tema por cima do padrão

    var ... let ... fn ...

    on_start { ... }             // uma vez, antes do primeiro quadro
    on_frame { ... }             // a cada quadro, antes do view
    on_key { ... }               // quando uma tecla é apertada (veja abaixo)

    view (...) { ... }           // a tela
}
```

As propriedades aceitam expressões, até condições. O mixer abre como camada quando recebe
`--camada`:

```
let layer_mode = has_arg("--camada")
kind: layer_mode ? layer : window
size: layer_mode ? 0 : 460 x layer_mode ? 0 : 660
```

### Teclas

Dentro de `on_key`, `key` é a tecla apertada, e se compara pelo nome:

```
on_key {
    if key == "Escape" { quit() }
    if key == "Return" or key == "space" { confirm() }
}
```

Os nomes são os do xkbcommon: `"Escape"`, `"Return"`, `"space"`, `"BackSpace"`, `"Tab"`,
`"Up"`, `"Down"`, `"Left"`, `"Right"`, `"a"`...`"z"`, `"A"`...`"Z"`, `"F1"`...

## Nomes

- Os nomes têm letras, números e `_`, e não começam com número.
- Palavras reservadas: `app fn var let if else for in while return break continue true false
  and or not view`. Depois de `#`, qualquer palavra serve de id (`#app` vale).
- Os nomes dos elementos (`row`, `text`, `button`...) e `theme`, `hovered`, `pressed` não podem
  ser nomes de variáveis.
- Nomes que colidem com o C (`int`, `default`, `s`...) são renomeados no C gerado sem você
  precisar fazer nada.
