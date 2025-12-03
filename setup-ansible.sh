#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

# --------------------------------------------------------------------
# 0. Install Debian packages required for pip and venv
# --------------------------------------------------------------------
install_debian_packages() {
    echo "📦 Vérification des paquets Debian requis..."

    # Check if running as root or with sudo capability
    if [[ $EUID -ne 0 ]]; then
        if command -v sudo &> /dev/null; then
            SUDO="sudo"
        else
            echo "⚠️  Ce script nécessite les privilèges root pour installer les paquets système."
            echo "   Veuillez exécuter avec sudo ou en tant que root."
            exit 1
        fi
    else
        SUDO=""
    fi

    # Detect if this is a Debian-based system
    if [[ -f /etc/debian_version ]]; then
        echo "🐧 Système Debian détecté, installation des dépendances..."
        $SUDO apt-get update -qq
        $SUDO apt-get install -y \
            python3 \
            python3-venv \
            python3-dev \
            build-essential \
            libssl-dev \
            libffi-dev \
            curl
        echo "✅ Paquets Debian installés."

            # Install uv if not already present
            if ! command -v uv &> /dev/null; then
                echo "📦 Installation d'uv..."
                curl -LsSf https://astral.sh/uv/install.sh | sh
                # Ensure uv is available in this shell immediately
                export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
                echo "✅ uv installé."
            else
                # Ensure PATH is correct even if uv is already present
                export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
                echo "✅ uv déjà installé."
            fi

            # Enable bash autocompletion for uv and uvx (idempotent)
            if [[ -n "${BASH_VERSION:-}" ]]; then
                if ! grep -q 'uv generate-shell-completion bash' "$HOME/.bashrc" 2>/dev/null; then
                    echo 'eval "$(uv generate-shell-completion bash)"' >> "$HOME/.bashrc"
                    echo "🔁 Autocomplétion uv activée dans ~/.bashrc"
                fi
                if ! grep -q 'uvx --generate-shell-completion bash' "$HOME/.bashrc" 2>/dev/null; then
                    echo 'eval "$(uvx --generate-shell-completion bash)"' >> "$HOME/.bashrc"
                    echo "🔁 Autocomplétion uvx activée dans ~/.bashrc"
                fi
            fi

            # Ensure uv tool and uv-managed Python bins are on PATH for future shells
            if command -v uv &> /dev/null; then
                uv tool update-shell || true
                uv python update-shell || true
            fi
    else
        echo "ℹ️  Système non-Debian détecté, passage de l'installation des paquets..."
    fi
}

# Install system packages
install_debian_packages

# --------------------------------------------------------------------
# Function: install ansible tooling in the currently active Python env
# --------------------------------------------------------------------
install_ansible_tooling() {
    echo "📦  Installation d'Ansible & outils avec uv..."
    uv pip install ansible ansible-lint yamllint

    echo "✅  Tooling Ansible installé."
}

# --------------------------------------------------------------------
# 1. Delete existing .venv and create fresh one
# --------------------------------------------------------------------
if [[ -d "$VENV_DIR" ]]; then
    echo "🗑️  Suppression du venv existant : $VENV_DIR"
    rm -rf "$VENV_DIR"
fi

echo "🐍 Création du venv : $VENV_DIR"
python3 -m venv "$VENV_DIR"

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
