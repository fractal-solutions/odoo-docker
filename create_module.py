#!/usr/bin/env python3
"""Create a new Odoo module scaffold under ./addons.

Examples:
  ./create_module.py my_module --author "Ada Lovelace" --application
  ./create_module.py my_module --name "My Module" --depends base,mail
  ./create_module.py my_module --no-model
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ADDONS_DIR = REPO_ROOT / "addons"


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def normalize_module_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        die("module name is empty after normalization")
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        die("module name must start with a letter and contain only letters, digits, underscores")
    return name


def title_from_module(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("_"))


def parse_depends(depends_raw: str) -> list[str]:
    if not depends_raw:
        return []
    parts = [p.strip() for p in depends_raw.split(",")]
    return [p for p in parts if p]


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new Odoo module scaffold in ./addons")
    parser.add_argument("module_name", help="Technical module name (snake_case)")
    parser.add_argument("--name", dest="display_name", help="Display name")
    parser.add_argument("--author", default=os.getenv("USER", ""), help="Author name")
    parser.add_argument("--website", default="", help="Website URL")
    parser.add_argument("--category", default="Uncategorized", help="App category")
    parser.add_argument("--version", default="17.0.1.0.0", help="Module version")
    parser.add_argument("--license", default="LGPL-3", help="License")
    parser.add_argument("--summary", default="", help="Short summary")
    parser.add_argument("--description", default="", help="Long description")
    parser.add_argument("--depends", default="base", help="Comma-separated dependencies")
    parser.add_argument("--application", action="store_true", help="Mark module as an Application")
    parser.add_argument("--no-application", dest="application", action="store_false")
    parser.set_defaults(application=False)
    parser.add_argument("--with-model", dest="with_model", action="store_true", help="Generate a sample model")
    parser.add_argument("--no-model", dest="with_model", action="store_false", help="Skip sample model")
    parser.set_defaults(with_model=True)
    parser.add_argument("--force", action="store_true", help="Overwrite existing module directory")

    args = parser.parse_args()

    module_name = normalize_module_name(args.module_name)
    display_name = args.display_name or title_from_module(module_name)
    depends = parse_depends(args.depends) or ["base"]

    if args.application and not args.with_model:
        die("--application requires --with-model (menus/actions need a model)")

    module_dir = ADDONS_DIR / module_name
    if module_dir.exists():
        if not args.force:
            die(f"module already exists: {module_dir}")
        shutil.rmtree(module_dir)

    model_name = f"{module_name}.item"
    model_class = "Item"
    model_file = f"{module_name}.py"

    init_py = "from . import models\n"

    models_init = "from . import {file}\n".format(file=module_name) if args.with_model else ""

    model_py = """from odoo import models, fields\n\n\nclass {class_name}(models.Model):\n    _name = "{model}"\n    _description = "{desc}"\n\n    name = fields.Char(required=True)\n""".format(
        class_name=title_from_module(module_name).replace(" ", "") + model_class,
        model=model_name,
        desc=f"{display_name} Item",
    )

    views_xml_parts = ["<odoo>"]
    if args.with_model:
        views_xml_parts.append(
            f"""
    <record id="view_{module_name}_item_tree" model="ir.ui.view">
        <field name="name">{model_name}.tree</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <tree>
                <field name="name" />
            </tree>
        </field>
    </record>

    <record id="view_{module_name}_item_form" model="ir.ui.view">
        <field name="name">{model_name}.form</field>
        <field name="model">{model_name}</field>
        <field name="arch" type="xml">
            <form>
                <sheet>
                    <group>
                        <field name="name" />
                    </group>
                </sheet>
            </form>
        </field>
    </record>
""".rstrip()
        )

    if args.application and args.with_model:
        views_xml_parts.append(
            f"""
    <record id="action_{module_name}_item" model="ir.actions.act_window">
        <field name="name">{display_name}</field>
        <field name="res_model">{model_name}</field>
        <field name="view_mode">tree,form</field>
    </record>

    <menuitem id="menu_{module_name}_root" name="{display_name}" sequence="10" />
    <menuitem id="menu_{module_name}_items" name="Items" parent="menu_{module_name}_root" action="action_{module_name}_item" sequence="10" />
""".rstrip()
        )

    views_xml_parts.append("</odoo>\n")
    views_xml = "\n".join(views_xml_parts)

    access_csv = "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
    if args.with_model:
        access_csv += f"access_{module_name}_item,{module_name}.item,model_{module_name}_item,,1,1,1,1\n"

    manifest = {
        "name": display_name,
        "summary": args.summary,
        "description": args.description or args.summary,
        "author": args.author,
        "website": args.website,
        "category": args.category,
        "version": args.version,
        "license": args.license,
        "depends": depends,
        "data": [],
        "application": bool(args.application),
        "installable": True,
    }

    data_files: list[str] = []
    if args.with_model:
        data_files.append("security/ir.model.access.csv")
    data_files.append(f"views/{module_name}_views.xml")
    manifest["data"] = data_files

    manifest_lines = ["{"]
    for key in [
        "name",
        "summary",
        "description",
        "author",
        "website",
        "category",
        "version",
        "license",
        "depends",
        "data",
        "application",
        "installable",
    ]:
        value = manifest[key]
        manifest_lines.append(f"    {key!r}: {value!r},")
    manifest_lines.append("}\n")

    # Write files
    write_file(module_dir / "__init__.py", init_py)
    write_file(module_dir / "__manifest__.py", "\n".join(manifest_lines))
    if args.with_model:
        write_file(module_dir / "models" / "__init__.py", models_init)
        write_file(module_dir / "models" / model_file, model_py)
        write_file(module_dir / "security" / "ir.model.access.csv", access_csv)
    else:
        write_file(module_dir / "models" / "__init__.py", "")
    write_file(module_dir / "views" / f"{module_name}_views.xml", views_xml)

    print(f"Created module: {module_dir}")


if __name__ == "__main__":
    main()
