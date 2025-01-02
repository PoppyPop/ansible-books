#!/bin/bash
#

ansible-playbook -i hosts-prepared.yaml --extra-vars '@secrets.yaml' $@
