# Odoo Docker Dev (Manjaro / Arch)

## Contents
- [Start / Stop](#start-stop)
- [Logs](#logs)
- [Add Custom Modules](#add-custom-modules)
- [Odoo Config](#odoo-config)
- [Upgrade Modules](#upgrade-modules)
- [Dev Mode](#dev-mode)
- [Dev Auto Reload (optional)](#dev-auto-reload-optional)
- [Common Fixes](#common-fixes)
- [Database](#database)
- [Workflow](#workflow)
- [Copy Existing Module](#copy-existing-module)
- [Module Generator](#module-generator)
  - [Usage](#usage)
  - [Options](#options)
  - [Notes](#notes)


This repo runs Odoo in Docker and includes a small helper script to generate new modules under `./addons`.

## Start / Stop
```bash
docker compose up -d
docker compose down
docker compose restart odoo
```

## Logs
```bash
docker compose logs -f odoo
```

## Add Custom Modules
Put modules in:
```
./addons/
```

Example:
```
addons/my_module/
```

## Odoo Config
File: `config/odoo.conf`
```ini
[options]
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
admin_passwd = admin
```

## Upgrade Modules
UI:
- Apps → Upgrade

CLI:
```bash
docker exec -it odoo-app bash
odoo -u my_module -d fractal --stop-after-init
```

## Dev Mode
```
http://localhost:8069/web?debug=1
```

## Dev Auto Reload (optional)
Add to `docker-compose.yml`:
```yaml
command: >
  odoo --dev=reload
```

## Common Fixes
Permissions:
```bash
sudo chown -R $USER:$USER addons
```

Multiple modules:
```bash
odoo -u module1,module2 -d fractal
```

## Database
```bash
docker exec -it odoo-app odoo list-db
```

## Workflow
1. Edit module
2. Restart container
3. Upgrade module
4. Refresh browser

## Copy Existing Module
Script: `copy_module.sh`

Copies an existing module from:
```
/home/fractal/dev/Woocommerce/custom/<module_name>
```
to:
```
./addons/<module_name>
```

Usage:
```bash
./copy_module.sh my_module
```

Notes:
- Fails if the source module directory does not exist.
- Overwrites `./addons/<module_name>` if it already exists.

---
## Module Generator
Script: `create_module.py`

Creates a new Odoo module scaffold under `./addons`.

### Usage
```bash
./create_module.py my_module --author "Your Name" --application
```

```bash
./create_module.py my_module --name "My Module" --depends base,mail
```

```bash
./create_module.py my_module --no-model
```

### Options
- `module_name` (positional): technical module name (snake_case)
- `--name`: display name
- `--author`: author name (defaults to `$USER`)
- `--website`: website URL
- `--category`: app category (default `Uncategorized`)
- `--version`: module version (default `17.0.1.0.0`)
- `--license`: license (default `LGPL-3`)
- `--summary`: short summary
- `--description`: long description
- `--depends`: comma-separated deps (default `base`)
- `--application`: mark as Application (adds menu/action)
- `--no-application`: unset Application flag
- `--with-model`: generate sample model (default)
- `--no-model`: skip sample model
- `--force`: overwrite existing module folder

### Notes
- `--application` requires `--with-model` (menus/actions need a model)
- Creates:
  - `__manifest__.py`
  - `__init__.py`
  - `models/` (optional)
  - `views/`
  - `security/ir.model.access.csv` (if model generated)
