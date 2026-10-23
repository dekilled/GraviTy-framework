# Os exemplos do GraviTy e os testes do compilador.
#
#   cmake -B build -DGRAVITY_DIR=/caminho/LUMNA_OS/gravity
#   cmake --build build
#   ./build/mixer
#   ctest --test-dir build
cmake_minimum_required(VERSION 3.16)
project(GraviTy C)

set(GRAVITY_DIR "" CACHE PATH "a pasta gravity/ do LUMNA_OS (onde está src/gravity.h)")

enable_testing()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME gvt-compilador
	COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -t .
	WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
set_tests_properties(gvt-compilador PROPERTIES ENVIRONMENT "GRAVITY_DIR=${GRAVITY_DIR}")

if(NOT GRAVITY_DIR)
	message(WARNING "GraviTy: sem -DGRAVITY_DIR só correm os testes do compilador; os exemplos precisam do Gravity.")
	return()
endif()

include(cmake/GraviTy.cmake)
gravity_runtime("${GRAVITY_DIR}")
gravity_add_app(ola examples/ola.gvt)
gravity_add_app(mixer examples/mixer.gvt)
gravity_add_app(galeria examples/galeria.gvt)
gravity_add_app(ajustes examples/ajustes.gvt)
