#!/bin/bash
#

ansible-playbook -i hosts.ansible --ask-vault-pass --extra-vars '@secrets.yaml' $@
