# Rôle Ansible : shares

Ce rôle permet de gérer automatiquement des partages SMB et NFS à partir d’une configuration unique.  
Il crée les fichiers de configuration appropriés, met à jour les fichiers système et supprime les entrées obsolètes.

- Synchronisation complète SMB (création + include + nettoyage)
- Synchronisation complète NFS (exports + nettoyage)
- Normalisation automatique des noms de partage
- Pas d’installation de packages (purement configuration)
- Conforme ansible-lint (FQDN, noms des tasks en majuscule)

---

## Fonctionnement

Le rôle prend une liste de partages :

```
shares:
  - path: /data/media
  - path: /data/backup
    comment: "Sauvegardes"
```

Chaque partage :

- est exporté en SMB via un fichier dédié :  
  /etc/samba/shares/<safe_name>.conf

- est exporté en NFS dans /etc/exports avec des options fixes

Le rôle garantit que si un partage est supprimé de la variable `shares`, toutes ses traces SMB et NFS sont supprimées.

---

## Arborescence du rôle

```
roles/shares/
├── defaults/
│   └── main.yml
├── handlers/
│   └── main.yml
├── tasks/
│   ├── main.yml
│   ├── normalize.yml
│   ├── smb.yml
│   ├── cleanup_smb.yml
│   ├── nfs.yml
│   └── cleanup_nfs.yml
└── templates/
    └── smb-share.conf.j2
```

---

## Variables

### `shares` (obligatoire)

```
shares:
  - path: /srv/media
    comment: "Données multimédia"
  - path: /srv/backup
```

### Variables SMB

```
smb_main_config: "/etc/samba/smb.conf"
smb_shares_dir: "/etc/samba/shares.d/"
```

### Variables NFS

Options fixes (non personnalisables) :

```
nfs_default_options: "10.0.0.0/20(rw,no_subtree_check,anongid=513,async,anonuid=11001)"
```

---

## Normalisation des noms

Chaque partage reçoit automatiquement un nom « safe » :

- basé sur `name` si fourni
- sinon basé sur le nom du répertoire
- caractères invalides → remplacés par `_`
- jamais vide
- jamais commencé par un chiffre

Exemples :

| Path              | safe_name       |
|-------------------|-----------------|
| /data/media       | media           |
| /my data/test!    | my_data_test    |
| /42share          | share_42share   |

---

## Exports SMB

Pour chaque partage, un fichier est généré :

```
/etc/samba/shares/<safe_name>.conf
```

Ce fichier est automatiquement inclus dans smb.conf :

```
include = /etc/samba/shares/<safe_name>.conf
```

Options SMB imposées :

```
writeable = yes
browseable = yes
```

---

## Exports NFS

Chaque partage ajoute une ligne dans /etc/exports :

```
/path/to/share 10.0.0.0/20(rw,no_subtree_check,anongid=513,async,anonuid=11001)
```

---

## Nettoyage automatique

Le rôle supprime automatiquement :

- les fichiers SMB abandonnés
- les directives `include = ...` obsolètes
- les lignes NFS obsolètes dans /etc/exports

---

## Exemple d’utilisation

```
- hosts: fileserver
  become: yes

  roles:
    - role: shares
      vars:
        shares:
          - path: /data/media
            comment: "Media"
            extra_group: audiophiles
            extra_permissions: rx
          - path: /data/backup
```

---

## Compatibilité

- Ansible 2.12+
- Samba préinstallé
- NFS server préinstallé

---

## Licence

MIT

---

## Contributions

PR bienvenues.
