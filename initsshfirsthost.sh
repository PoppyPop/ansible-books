#!/bin/bash
#

ansible-playbook -i hosts.yaml --ask-vault-pass --extra-vars '@secrets.yaml' initssh.playbook
