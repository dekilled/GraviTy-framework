# Os exemplos do GraviTy e os testes do compilador.
#
#   cmake -B build
#   cmake --build build
#   ./build/mixer
#   ctest --test-dir build
cmake_minimum_required(VERSION 3.16)
project(GraviTy C)

set(GRAVITY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/gravity" CACHE PATH "a pasta do Gravity (por padrão, a que vem com o framework)")

enable_testing()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME gvt-compilador
	COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -t .
	WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
set_tests_properties(gvt-compilador PROPERTIES ENVIRONMENT "GRAVITY_DIR=${GRAVITY_DIR}")

include(cmake/GraviTy.cmake)
gravity_runtime("${GRAVITY_DIR}")
gravity_add_app(ola examples/ola.gvt)
gravity_add_app(mixer examples/mixer.gvt)
gravity_add_app(galeria examples/galeria.gvt)
gravity_add_app(ajustes examples/ajustes.gvt)
