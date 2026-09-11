PYTHON ?= python3

.PHONY: test syntax

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	/bin/zsh tests/test_ssh_proxy.zsh
	/bin/zsh tests/test_install.zsh

syntax:
	$(PYTHON) -m py_compile python/*.py macos/*.py
	/bin/zsh -n install.sh uninstall.sh shell/ssh-proxy.zsh
