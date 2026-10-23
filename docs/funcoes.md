# Funções prontas

## Números

| função | retorna | |
|---|---|---|
| `round(x)` | int | arredonda: `round(2.5)` é 3 |
| `int(x)` | int | corta as casas: `int(2.9)` é 2 |
| `float(x)` | float | |
| `floor(x)`, `ceil(x)` | float | para baixo / para cima |
| `abs(x)` | int ou float | o valor sem sinal |
| `min(a, b)`, `max(a, b)` | int ou float | o menor / o maior |
| `clamp(x, lo, hi)` | int ou float | `x` preso entre `lo` e `hi` |
| `sqrt(x)`, `sin(x)`, `cos(x)`, `pow(a, b)` | float | |

## Listas

| função | retorna | |
|---|---|---|
| `len(lista)` | int | quantos itens |

## Cores

| função | retorna | |
|---|---|---|
| `alpha(cor, a)` | color | a cor com opacidade `a` (de 0 a 1) |
| `rgb(0xRRGGBBAA)` | color | uma cor de um número |

## Animação e interação

| função | retorna | |
|---|---|---|
| `animate(alvo)`, `animate(alvo, duração)` | float ou color | o valor caminhando até o alvo ([Tema](tema.md#animação-animate)) |
| `hovered` / `hovered(#id)` | bool | o ponteiro (ou o dedo) está sobre o elemento |
| `pressed` / `pressed(#id)` | bool | o toque começou no elemento e ainda não soltou |
| `tapped(#id)` | bool | o elemento foi tocado (dentro do próprio elemento, use `on_tap`) |

Sem `#id`, `hovered` e `pressed` falam do elemento onde estão escritos. Com `#id`, falam de
outro: o véu do mixer fecha só quando o toque é **fora** do cartão:

```
view (...) {
    on_tap {
        if not hovered(#card) { quit() }
    }
    card #card (...) { ... }
}
```

A interação sempre usa o quadro anterior (é assim que o modo imediato funciona), mas isso é
imperceptível.

## O app

| função | retorna | |
|---|---|---|
| `quit()` | | fecha o app |
| `redraw()` | | pede outro quadro (os componentes e as animações já pedem sozinhos) |
| `width()`, `height()` | float | o tamanho da janela agora |
| `now()` | float | segundos desde que o app abriu |
| `has_arg("--camada")` | bool | o app foi aberto com esse argumento |
| `load_theme("caminho")` | bool | lê um `tema.ini` por cima do tema ativo |
| `print(valor)` | | escreve no terminal (útil para depurar): `print("volume: {volume}")` |
