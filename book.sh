#!/bin/bash
#

ansible-playbook -i hosts-prepared.yaml --ask-vault-pass --extra-vars '@secrets.yaml' $@
