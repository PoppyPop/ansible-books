#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

# --------------------------------------------------------------------
# Function: install ansible tooling in the currently active Python env
# --------------------------------------------------------------------
install_ansible_tooling() {
    echo "📦  Mise à jour de pip/setuptools/wheel..."
    pip install --upgrade pip wheel setuptools

    echo "🛠️  Installation / Mise à jour d'Ansible & outils..."
    pip install --upgrade ansible ansible-lint yamllint

    echo "✅  Tooling Ansible installé."
}

# --------------------------------------------------------------------
# 0. Check if we are already inside a virtual environment
# --------------------------------------------------------------------
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "ℹ️  Déjà dans un environnement virtuel :"
    echo "    $VIRTUAL_ENV"
    echo "🔧 Installation dans l'environnement courant..."
    install_ansible_tooling
    echo "🎉 Terminé."
    exit 0
fi

# --------------------------------------------------------------------
# 1. Create .venv if missing
# --------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    echo "🐍 Création du venv : $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "📁 Le venv '$VENV_DIR' existe déjà."
fi

# --------------------------------------------------------------------
# 2. Activate .venv
# --------------------------------------------------------------------
echo "🔌 Activation du venv..."
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# --------------------------------------------------------------------
# 3. Install tooling inside .venv
# --------------------------------------------------------------------
install_ansible_tooling

# --------------------------------------------------------------------
# 4. Summary
# --------------------------------------------------------------------
echo ""
echo "🎯 Setup terminé avec succès (venv : $VENV_DIR)"
echo "🐍 Python :       $(which python)"
echo "📘 Ansible :      $(which ansible)"
echo "🔍 ansible-lint : $(which ansible-lint)"
echo "📏 yamllint :     $(which yamllint)"
echo "🚀 Prêt à l'emploi !"
