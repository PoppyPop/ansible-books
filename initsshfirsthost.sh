#!/bin/bash
#

ansible-playbook -i hosts.yaml --extra-vars '@secrets.yaml' initssh.playbook
