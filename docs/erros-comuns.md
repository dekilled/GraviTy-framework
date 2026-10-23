# Erros comuns

O `gvt` mostra a linha e uma dica. Aqui está o que cada mensagem quer dizer.

### `X não tem a propriedade 'y'` / `X não conhece 'y'`

Um nome de propriedade errado, ou uma palavra solta que aquele elemento não aceita. Olhe a dica
("você quis dizer...?") e a tabela do elemento em [Elementos](elementos.md).

### `'n' é let (não muda)`

Você tentou mudar uma `let`. Troque por `var`.

### `a condição do if devia ser bool, mas é int`

O `if` quer verdadeiro ou falso. Compare: `if count > 0`, `if name == "x"`.

### `não dá para usar + com textos`

Para juntar textos, use a interpolação: `"Volume: {v}%"`, não `"Volume: " + v`.

### `devia ser int, mas é float`

Um número com casas foi parar onde só cabe inteiro (um índice, um `-> int`...). Use `round(x)`
para arredondar ou `int(x)` para cortar as casas.

### `break não pode ficar dentro de um elemento`

O Clay precisa fechar cada elemento. Ponha a condição fora:

```
// em vez disto
for i in 0..10 {
    row { if i == 3 { break } }
}
// isto
for i in 0..10 {
    if i == 3 { break }
    row { ... }
}
```

### `text não pode ficar dentro de um evento`

Eventos (`on_tap`, `on_change`, `on_key`...) mudam o estado; eles não desenham. Mude uma variável
no evento e use um `if` no corpo para desenhar:

```
var saved = false
button #save ("Salvar") { on_tap { saved = true } }
if saved { text("Salvo!") }
```

### `X desenha na tela e não pode ser chamada num evento`

A mesma ideia, só que com uma `fn` que desenha.

### `uma função que retorna valor não desenha elementos`

Uma `fn` com `-> tipo` calcula; sem `-> tipo`, desenha. Separe em duas.

### `nome desconhecido: 'x'`

A variável não existe (veja a dica de nome parecido), ou é uma palavra que só vale num lugar:
`center` vale em `align:`, `accent` vale onde se espera uma cor... Em outros lugares, use
`theme.accent`.

### `elementos sem #id[índice] dentro de um while`

Dentro de um `while` o GraviTy não sabe em que volta está para dar ids diferentes. Use um `for`, ou
dê o índice você mesmo: `button #b[i] (...)`.

### `uma lista [ ] só pode ser o valor inicial de um var ou let`

Ainda não dá para criar listas no meio de uma conta ou trocar uma lista inteira. Declare a lista
uma vez e mude item a item.

### `falta o ')' aqui`

Um parêntese aberto sem fechar. O `^` aponta onde ele deveria estar.

### Gerei o `.c` mas ele não roda / `gravity.h: No such file or directory`

O `gvt build app.gvt` só gera o código-fonte em C. Para ter um programa, use `gvt run app.gvt`
(compila e abre) ou `gvt build app.gvt --exe` (só compila). Eles acham o Gravity, compilam a
`libgravity` e chamam o compilador de C por você.

### `não achei o Gravity em '...'`

Você passou um `--gravity` (ou um `GRAVITY_DIR`) que não aponta para uma pasta do Gravity. Sem
nenhum dos dois, o `gvt` usa a pasta `gravity/` que vem com o framework, que é o normal.

### `faltam bibliotecas do Gravity`

A dica traz o comando de instalação da sua distribuição. No Arch:
`sudo pacman -S --needed wayland wayland-protocols libxkbcommon cairo pango pkgconf`.

### `não há sessão Wayland aberta`

O Gravity desenha direto no Wayland. Rode de dentro do Hyprland, do Sway, do GNOME ou KDE numa
sessão Wayland, ou do Orbit. Numa sessão X11 ou num terminal sem interface gráfica, ele não abre.

### Avisos

- **`'x' é declarado e nunca usado`**: uma variável local ou um parâmetro que ninguém lê. Apague, ou
  use `for i in 0..len(lista)` se só precisa do índice.
- **`o Gravity não tem o ícone 'x'`**: o nome não está entre os ícones do Gravity. A dica diz o
  nome mais parecido.
- **`este slider mostra uma conta e não tem on_change`**: o slider mexe, mas nada muda. Use uma
  variável no `value`, ou trate a mudança no `on_change`.

### Erro no C, não no `.gvt`

Não deveria acontecer: o `gvt` confere tudo antes. Se acontecer, é bug do GraviTy. Guarde o `.gvt`
e o erro, e abra uma issue.
