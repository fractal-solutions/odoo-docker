#!/bin/bash

# Check if a module name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <module_name>"
  exit 1
fi

MODULE_NAME="$1"
SOURCE_DIR="/home/fractal/dev/Woocommerce/custom/$MODULE_NAME"
DEST_DIR="/home/fractal/dev/odoo-docker/addons/$MODULE_NAME"

# Check if the source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: Source module directory '$SOURCE_DIR' not found."
  exit 1
fi

# Create destination directory if it doesn't exist
mkdir -p "$(dirname "$DEST_DIR")"

echo "Copying module '$MODULE_NAME' from '$SOURCE_DIR' to '$DEST_DIR'..."
cp -r "$SOURCE_DIR" "$DEST_DIR"

if [ $? -eq 0 ]; then
  echo "Successfully copied '$MODULE_NAME'."
else
  echo "Error: Failed to copy '$MODULE_NAME'."
  exit 1
fi
