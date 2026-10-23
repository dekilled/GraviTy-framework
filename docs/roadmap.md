# Próximos passos

## O editor do GraviTy

Um app (feito em GraviTy, claro) para escrever `.gvt` com conforto:

- **Cores no código**: palavras-chave, textos, números, ids (`#nome`), elementos e propriedades,
  cada um com a sua cor, em vez de texto branco.
- **Erros enquanto você digita**: o `gvt check` já faz o trabalho (linha, coluna, mensagem e
  dica). O editor só precisa sublinhar.
- **Formatador** (`gvt fmt`): indentação de 4 espaços, propriedades alinhadas e linhas quebradas
  no mesmo estilo, para o código ficar sempre bonito.
- **Linter** (`gvt lint`): o que não é erro mas merece aviso. Já existem: variável não usada,
  ícone que não existe e slider sem `on_change`. Faltam: ids repetidos no mesmo nível, texto
  com cor de fundo sem contraste, `animate` dentro de `while`...
- **Pré-visualização ao vivo**: recompilar e reabrir o app a cada gravação.

O primeiro passo concreto é um **servidor de linguagem (LSP)** em cima do compilador. Com ele, o
VS Code, o Neovim, o Helix e o editor próprio ganham cores, erros e auto-completar de uma vez.
Antes disso, uma gramática TextMate simples já dá as cores no VS Code e no GitHub.

## A linguagem

- **Mais eventos**: `on_long_press` (segurar), `on_double_tap`, `on_scroll` e gestos (deslizar,
  pinça), conforme o Gravity ganhar suporte a eles.
- **Componentes com filhos**: `fn painel(title: string) { card { ...; slot } }` para encaixar
  conteúdo dentro de uma `fn`.
- **Listas que crescem**: `push`, `remove` e `clear`, para listas de verdade (notificações,
  arquivos, redes Wi-Fi).
- **Campo de texto**: assim que o Gravity tiver `gv_campo` (cursor, seleção, o teclado do LUMNA).
- **Imagens**: ícones de apps e capas de álbum, quando o Gravity tiver imagens.
- **Timers**: `every 1000 { ... }` para relógios e atualizações.
- **Ligação ao sistema**: ler um socket ou um pipe (`gv_app_vigiar`) para o mixer falar com o
  PipeWire, a barra com o compositor, e assim por diante.
- **Vários arquivos**: `import "componentes.gvt"`.
- **Parâmetros de lista e registro** nas funções.

## O compilador

- `#line` no C gerado, para o `gdb` mostrar a linha do `.gvt`.
- Mais testes do C gerado contra o Gravity (o mixer e a galeria já são comparados pixel a pixel).
- Testes de interação: tocar, arrastar e rolar automaticamente (hoje só a renderização é testada).

## Notas sobre o Gravity

- O `gv_anim` cria a animação já no valor alvo. Por isso a entrada do mixer (`gv_anim(1, 1, ...)`
  no `mixer.c`) sempre devolve 1, e o "pop" de abertura não anima. Para animar ao abrir, o Gravity
  precisaria de um `gv_anim_de(chave, inicio, alvo, ms)`, ou o app começa com o alvo em 0 e muda
  para 1 no primeiro quadro.
