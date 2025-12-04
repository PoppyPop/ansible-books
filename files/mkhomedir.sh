#!/bin/bash

if [ ! -e /datas/usershares/$1 ]; then
	mkdir /datas/usershares/$1
	chown $1:admins /datas/usershares/$1
fi
exit 0
