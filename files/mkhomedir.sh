#!/bin/bash

if [ ! -e /datas/Shares/usershare/$1 ]; then
	mkdir /datas/Shares/usershare/$1
	chown $1:admins /datas/Shares/usershare/$1
fi
exit 0
