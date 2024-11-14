#!/bin/bash
#

### Set default parameters
action=$1
sharePath=$2
shareName=$3
group=$4
user=$5

defaultGroup='admins'
smbBase='/etc/samba'
nfsConfFile='/etc/exports'

### don't modify from here unless you know what you are doing ####

function CleanSambaConfFile {
	if [ -f $smbBase/smb.d/$shareName.share ] 
	then 
		if ! rm $smbBase/smb.d/$shareName.share
		then
			echo -e $"There is an ERROR Cleaning Samba"
			exit;exit 10;
		else
			echo -e $"Samba Cleaned"
		fi
	fi
}

function SetSambaConfFile {
	right="$groupSmb,$user"
	if [[ "${right:0:1}" == "," ]] ; then 
		right="${right:-1}"
	fi
	
	# the space before -1 is mandatory
	if [[ "${right: -1}" == "," ]] ; then 
		right="${right:0:-1}"
	fi

	if ! echo "
	[$shareName]
		writeable = yes
		browseable = yes
		write list = $right
		read list = $right
		valid users = $right
		path = $sharePath
		" > $smbBase/smb.d/$shareName.share
	then
		echo -e $"There is an ERROR creating $shareName Samba"
		exit;exit 15;
	else
		echo -e $"New samba share created"
	fi
}

function ReloadSambaConfFile {
	# Compile config files
	count=$(find /etc/samba/smb.d/ -name *.share -prune -print | grep -c /)
	if [ $count -gt 0 ]; then
		ls $smbBase/smb.d/*.share | sed -e 's/^/include = /' > $smbBase/includes.conf
	else
		echo "" > $smbBase/includes.conf
	fi
	
	if ! smbcontrol smbd reload-config
	then
		echo -e $"There is an ERROR Reloading Samba"
		exit;exit 19;
	else
		echo -e $"Samba Reloaded"
	fi
}

function CleanNfsConfFile {
	if ! sed -i "\|$sharePath|d" $nfsConfFile
	then
		echo -e $"There is an ERROR Cleaning Nfs"
		exit;exit 20;
	else
		echo -e $"NFS Cleaned"
	fi
}

function SetNfsConfFile {
	if ! echo "$sharePath	10.0.0.0/20(rw,no_subtree_check,anongid=513,async,anonuid=11001)" >> $nfsConfFile
	then
		echo -e $"There is an ERROR creating $shareName Nfs"
		exit;exit 25;
	else
		echo -e $"New NFS share created"
	fi
}

function ReloadNfsConfFile {
	if ! exportfs -a
	then
		echo -e $"There is an ERROR Reloading Nfs"
		exit;exit 29;
	else
		echo -e $"NFS Reloaded"
	fi
}

function SetAcl {
	if [ "$group" != "" ]; then
		export IFS=","
		for acl in $group; do
		  setfacl -d -R -m g:$acl:rwX $sharePath
		  setfacl -R -m g:$acl:rwX $sharePath
		done
	fi
	
	if [ "$user" != "" ]; then
		export IFS=","
		for acl in $user; do
		  setfacl -R -m u:$acl:rwX $sharePath
		done
	fi
}

function RemoveAcl {
	if [ "$group" != "" ]; then
		export IFS=","
		for acl in $group; do
		  setfacl -d -R -x g:$acl $sharePath
		  setfacl -R -x g:$acl $sharePath
		done
	fi
	
	if [ "$user" != "" ]; then
		export IFS=","
		for acl in $user; do
		  setfacl -R -x u:$acl $sharePath
		done
	fi
}

if [ "$(whoami)" != 'root' ]; then
	echo $"You have no permission to run $0 as non-root user. Use sudo"
		exit 1;
fi

if [ "$action" == "" ]; then
	echo $"You need to prompt for action (add, replace, delete) -- Lower-case only"
	exit 1;
fi

while [ "$sharePath" == "" ];
do
	echo -e $"Please provide a valid share path. e.g./datas"
	read sharePath
done

if [ ! -d "$sharePath" ]; then
	echo -e $"$sharePath does not exists, do you want to create it ? [Yn]"
	read createSharePath
	if [ "$createSharePath" == "" ] || [ "$createSharePath" == "y" ] || [ "$createSharePath" == "Y" ]; then
		mkdir -p $sharePath
	else
		exit 18
	fi
fi

while [ "$shareName" == "" ]
do
	echo -e $"Please provide share name. e.g.share1"
	read shareName
done

group="$group,$defaultGroup"
if [[ ${group:0:1} == "," ]] ; then 
	group=${group:1} 
fi

export IFS=","
for g in $group; do
  groupSmb="$groupSmb,@$g"
done
groupSmb=${groupSmb:1}


#check conf file/directory
if [ ! -d "$smbBase/smb.d/" ]; then
	if ! mkdir "$smbBase/smb.d/"; then 
		exit 90
	fi
fi

if [ ! -f "$nfsConfFile" ]; then
	if ! touch "$nfsConfFile"; then
		exit 91
	fi
fi

#Sanitize shareName case
shareName=$(echo "$shareName" | tr '[:upper:]' '[:lower:]')
action=$(echo "$action" | tr '[:upper:]' '[:lower:]')

echo "====== Configuration ======"
echo "Action    : $action"
echo "Path      : $sharePath"
echo "Name      : $shareName"
echo "Groups    : $group"
echo "Users     : $user"
echo "GroupsSmb : $groupSmb"
echo "UsersSmb  : $user"

while true; do
		    read -p "Do you wish to commit this configuration?" yn
    		case $yn in
        		[Yy]* ) break;break;;
        		[Nn]* ) exit;;
        		* ) echo "Please answer yes or no.";;
    		esac
		done

if [ "$action" == 'add' ]
then
	### check if domain already exists
	if [ -f $smbBase/smb.d/$shareName.share ]; then
		echo -e $"This share already exists.\nPlease Try Another one"
		exit 2;
	fi
	
	if grep -Fxq "$sharePath" $nfsConfFile
	then
		echo -e $"This share already exists.\nPlease Try Another one"
		exit 3;
	fi
	
	SetSambaConfFile
	SetNfsConfFile
	
	SetAcl
elif [ "$action" == 'replace' ]; then
	CleanSambaConfFile
	CleanNfsConfFile
	
	SetSambaConfFile
	SetNfsConfFile
	
	SetAcl
elif [ "$action" == 'delete' ]; then
	CleanSambaConfFile
	CleanNfsConfFile
	
	RemoveAcl
elif [ "$action" == 'acl' ]; then
	SetAcl
elif [ "$action" == 'remacl' ]; then	
	RemoveAcl
else
	echo $"You need to prompt for action (add, replace, acl, remacl, delete) -- Lower-case only"
	exit 1;
fi

ReloadSambaConfFile
ReloadNfsConfFile
