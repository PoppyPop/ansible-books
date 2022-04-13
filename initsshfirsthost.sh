#!/bin/bash
#

ansible-playbook -i hosts.yaml --ask-vault-pass initssh.playbook
