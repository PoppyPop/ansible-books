#!/bin/bash
set -e

REQ_FILE="requirements.yml"

if [[ ! -f "$REQ_FILE" ]]; then
    echo "requirements.yml not found!"
    exit 1
fi

echo "Updating Ansible Galaxy roles and collections..."
ansible-galaxy install -r "$REQ_FILE" #--force
ansible-galaxy collection install -r "$REQ_FILE" #--force

echo "Done!"
