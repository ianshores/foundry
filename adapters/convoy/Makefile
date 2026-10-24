CXX ?= c++
CONVOY_ROOT ?= ../../modules/convoy
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra
.PHONY: pd
pd:
	@test -f "$(PD_INCLUDE_DIR)/m_pd.h" || (echo 'Set PD_INCLUDE_DIR to the directory containing m_pd.h'; exit 1)
	mkdir -p build
	$(CXX) $(CXXFLAGS) -shared -fPIC -I"$(CONVOY_ROOT)/include" -I"$(PD_INCLUDE_DIR)" pd/convoy_tilde.cpp -o 'build/convoy~.pd_linux'
