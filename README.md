# GraviTy

**GraviTy** é uma linguagem de script para criar interfaces que vira **C** para o
[Gravity](https://github.com/dekilled/LUMNA_OS/tree/lumna-mobile/gravity), a biblioteca de UI do LUMNA OS.
Você escreve num arquivo `.gvt`, que se lê como script, e o compilador `gvt` gera o C que você
escreveria à mão. O gcc/clang compila esse C direto para código de máquina, então não há
interpretador nem nada rodando por baixo.

```gvt
app Ola {
    title: "Olá, LUMNA"
    size: 360 x 240

    var taps = 0

    view (center, gap: 16) {
        text("Olá, LUMNA", style: title, weight: semibold)
        text("Você tocou {taps} vez(es).", color: muted)

        button #more ("Tocar", icon: "check") {
            on_tap { taps += 1 }
        }
    }
}
```

## O que ele já faz

- **Pixel a pixel igual ao C feito à mão:** o [`mixer.gvt`](examples/mixer.gvt) e a
  [`galeria.gvt`](examples/galeria.gvt) geram exatamente a mesma tela dos originais em C do
  Gravity (0 pixels de diferença, com a lista aberta e com outro tema), com uns 40% menos linhas.
- **Sem custo em execução:** o C gerado usa `CLAY(...)` e os `gv_*` como no código original, e
  compila sem avisos com `-Wall -Wextra`.
- **Erros em português**, apontando a linha e a coluna do seu `.gvt`, com dica do que fazer:

  ```
  mixer.gvt:4:20: erro: text não tem a propriedade 'colr'
       4 |         text("oi", colr: muted)
         |                    ^
    dica: você quis dizer 'color'?
  ```

## Começar

Precisa de `python3` (sem nenhuma biblioteca extra), das dependências do Gravity (`wayland`,
`wayland-protocols`, `libxkbcommon`, `cairo`, `pango`) e da pasta `gravity/` do LUMNA_OS.

```sh
# com CMake (o jeito recomendado)
cmake -B build -DGRAVITY_DIR=/caminho/LUMNA_OS/gravity
cmake --build build
./build/mixer

# ou só o compilador
bin/gvt build examples/ola.gvt      # gera examples/ola.c
bin/gvt check examples/*.gvt        # só procura erros
```

No seu próprio projeto CMake:

```cmake
include(/caminho/GraviTy/cmake/GraviTy.cmake)
gravity_runtime(/caminho/LUMNA_OS/gravity)
gravity_add_app(meu_app meu_app.gvt)
```

## Documentação

| | |
|---|---|
| [Guia: o primeiro app](docs/guia.md) | do zero até um app com estado, listas e funções |
| [A linguagem](docs/linguagem.md) | variáveis, tipos, textos, `if`, `for`, funções, listas e registros |
| [Elementos](docs/elementos.md) | `row`, `column`, `card`, `text`, `button`, `slider`... com todas as propriedades |
| [Layout](docs/layout.md) | tamanhos, espaços, alinhamento, flutuar e rolar |
| [Tema, cores e animação](docs/tema.md) | o `theme`, as cores e o `animate()` |
| [Funções prontas](docs/funcoes.md) | `round`, `alpha`, `hovered`, `has_arg`, `print`... |
| [Por dentro](docs/por-dentro.md) | o C que sai, os ids e por que não há overhead |
| [Erros comuns](docs/erros-comuns.md) | o que a mensagem quer dizer e como resolver |
| [Próximos passos](docs/roadmap.md) | o editor, o linter, o formatador e o que falta na linguagem |

## Testes

```sh
python3 -m unittest discover -s tests -t .                                     # o compilador
GRAVITY_DIR=/caminho/LUMNA_OS/gravity python3 -m unittest discover -s tests -t .  # + gcc -Werror nos exemplos
GRAVITY_DIR=/caminho/LUMNA_OS/gravity tests/pixels.sh build                      # pixel a pixel contra o C original
```

O `pixels.sh` roda o mixer e a galeria num weston sem tela, tira um print de cada (o original em
C e o `.gvt`) e compara os dois.
