# GraviTy no CMake: compila .gvt para C e liga ao Gravity.
#
#   include(caminho/para/GraviTy/cmake/GraviTy.cmake)
#   gravity_runtime(/caminho/para/LUMNA_OS/gravity)   # a biblioteca Gravity (libgravity)
#   gravity_add_app(mixer mixer.gvt)                  # um executável a partir de um .gvt
#   gravity_add_app(ajustes ajustes.gvt extra.c)      # .c a mais entram no mesmo executável
#
# O .gvt vira C no build (pasta build/gvt/) e volta a ser gerado sempre que o .gvt ou o
# compilador mudam. Precisa de python3 e das bibliotecas do Gravity: wayland, wayland-protocols,
# xkbcommon, cairo e pango.

include_guard(GLOBAL)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(PkgConfig REQUIRED)

set(GVT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." CACHE INTERNAL "a raiz do GraviTy")
set(GVT_COMPILER "${GVT_ROOT}/bin/gvt" CACHE INTERNAL "o compilador gvt")
file(GLOB GVT_COMPILER_SOURCES CONFIGURE_DEPENDS "${GVT_ROOT}/gvt/*.py")

# A biblioteca Gravity, compilada a partir das fontes (a pasta gravity/ do LUMNA_OS).
function(gravity_runtime dir)
	if(TARGET gravity)
		return()
	endif()
	get_filename_component(dir "${dir}" ABSOLUTE)
	if(NOT EXISTS "${dir}/src/gravity.h")
		message(FATAL_ERROR "GraviTy: não encontrei o Gravity em '${dir}' (falta src/gravity.h).\n"
			"Aponte para a pasta gravity/ do LUMNA_OS: -DGRAVITY_DIR=/caminho/LUMNA_OS/gravity")
	endif()

	pkg_check_modules(GRAVITY_DEPS REQUIRED IMPORTED_TARGET
		wayland-client wayland-cursor xkbcommon cairo pangocairo)
	pkg_get_variable(WAYLAND_PROTOCOLS_DIR wayland-protocols pkgdatadir)
	pkg_get_variable(WAYLAND_SCANNER wayland-scanner wayland_scanner)
	if(NOT WAYLAND_PROTOCOLS_DIR OR NOT WAYLAND_SCANNER)
		message(FATAL_ERROR "GraviTy: faltam wayland-protocols e wayland-scanner (no Arch: pacman -S wayland-protocols)")
	endif()

	# os protocolos do Wayland viram C com o wayland-scanner
	set(gen "${CMAKE_BINARY_DIR}/gravity-protocolos")
	file(MAKE_DIRECTORY "${gen}")
	set(xdg "${WAYLAND_PROTOCOLS_DIR}/stable/xdg-shell/xdg-shell.xml")
	set(layer "${dir}/protocolos/wlr-layer-shell-unstable-v1.xml")
	add_custom_command(
		OUTPUT "${gen}/xdg-shell-client-protocol.h" "${gen}/xdg-shell-protocol.c"
		COMMAND "${WAYLAND_SCANNER}" client-header "${xdg}" "${gen}/xdg-shell-client-protocol.h"
		COMMAND "${WAYLAND_SCANNER}" private-code "${xdg}" "${gen}/xdg-shell-protocol.c"
		DEPENDS "${xdg}" VERBATIM)
	add_custom_command(
		OUTPUT "${gen}/wlr-layer-shell-unstable-v1-client-protocol.h" "${gen}/wlr-layer-shell-unstable-v1-protocol.c"
		COMMAND "${WAYLAND_SCANNER}" client-header "${layer}" "${gen}/wlr-layer-shell-unstable-v1-client-protocol.h"
		COMMAND "${WAYLAND_SCANNER}" private-code "${layer}" "${gen}/wlr-layer-shell-unstable-v1-protocol.c"
		DEPENDS "${layer}" VERBATIM)

	file(GLOB sources CONFIGURE_DEPENDS "${dir}/src/*.c")
	add_library(gravity STATIC ${sources}
		"${gen}/xdg-shell-protocol.c" "${gen}/wlr-layer-shell-unstable-v1-protocol.c"
		"${gen}/xdg-shell-client-protocol.h" "${gen}/wlr-layer-shell-unstable-v1-client-protocol.h")
	target_include_directories(gravity PUBLIC "${dir}/src" "${dir}/vendor/clay" PRIVATE "${gen}")
	target_compile_definitions(gravity PRIVATE _POSIX_C_SOURCE=200809L)
	target_link_libraries(gravity PUBLIC PkgConfig::GRAVITY_DEPS m)
	set_target_properties(gravity PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON)
	# o Clay é de fora: os avisos dele não são nossos
	set_source_files_properties("${dir}/src/gv_clay.c" PROPERTIES COMPILE_OPTIONS "-w")
	set_property(GLOBAL PROPERTY GVT_GRAVITY_DIR "${dir}")
endfunction()

# Um app a partir de um .gvt (e, se quiser, .c a mais).
function(gravity_add_app name gvt)
	if(NOT TARGET gravity)
		message(FATAL_ERROR "GraviTy: chame gravity_runtime(<pasta do Gravity>) antes de gravity_add_app")
	endif()
	get_filename_component(src "${gvt}" ABSOLUTE)
	get_filename_component(base "${gvt}" NAME_WE)
	set(out "${CMAKE_CURRENT_BINARY_DIR}/gvt/${base}.c")
	get_property(gdir GLOBAL PROPERTY GVT_GRAVITY_DIR)
	add_custom_command(
		OUTPUT "${out}"
		COMMAND "${Python3_EXECUTABLE}" "${GVT_COMPILER}" build "${src}" -o "${out}" --gravity "${gdir}"
		DEPENDS "${src}" ${GVT_COMPILER_SOURCES}
		COMMENT "GraviTy: ${gvt} -> C"
		VERBATIM)
	add_executable(${name} "${out}" ${ARGN})
	target_link_libraries(${name} PRIVATE gravity)
	target_compile_definitions(${name} PRIVATE _POSIX_C_SOURCE=200809L)
	set_target_properties(${name} PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED ON)
	if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(${name} PRIVATE -Wall -Wextra -Wno-missing-field-initializers)
	endif()
endfunction()
