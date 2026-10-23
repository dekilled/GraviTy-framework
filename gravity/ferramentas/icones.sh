#!/bin/sh
# Gera src/gv_icones.c com os ícones do shell do LUMNA (shell/src/components/Icon.vue, no LUMNA_OS):
# o mesmo desenho nos dois lados. Rode de novo quando o Icon.vue ganhar ícones:
#   sh gravity/ferramentas/icones.sh /caminho/LUMNA_OS/shell/src/components/Icon.vue
set -eu
export LC_ALL=C # a ordem do bsearch é a do strcmp
VUE=${1:?diga onde está o Icon.vue: sh gravity/ferramentas/icones.sh /caminho/LUMNA_OS/shell/src/components/Icon.vue}
SAIDA="$(cd "$(dirname "$0")/.." && pwd)/src/gv_icones.c"

{
	echo "/* Gerado por ferramentas/icones.sh a partir de shell/src/components/Icon.vue: não edite à mão. */"
	echo '#include "gv_interno.h"'
	echo
	echo '#include <string.h>'
	echo
	echo 'struct icone {'
	echo '	const char *nome;'
	echo '	const char *caminho;'
	echo '};'
	echo
	echo 'static const struct icone icones[] = {'
	# linhas como:   volume: "M4 9v6...",   ou   "volume-off": "M4 9h4...",
	sed -n 's/^[[:space:]]*"\{0,1\}\([a-z0-9-]*\)"\{0,1\}: \("[^"]*"\),\{0,1\}$/	{ "\1", \2 },/p' "$VUE" | sort
	echo '};'
	echo
	echo 'static int comparar(const void *chave, const void *item) {'
	echo '	return strcmp(chave, ((const struct icone *)item)->nome);'
	echo '}'
	echo
	echo '#include <stdlib.h>'
	echo
	echo 'const char *gv__icone_caminho(const char *nome) {'
	echo '	const struct icone *i = bsearch(nome, icones, sizeof(icones) / sizeof(icones[0]), sizeof(icones[0]), comparar);'
	echo '	return i ? i->caminho : NULL;'
	echo '}'
} >"$SAIDA"
echo "$(grep -c '^	{ "' "$SAIDA") ícones em $SAIDA"
