#!/bin/bash
# Quick Install Script for Efficient Hybrid Enhancement

set -e  # Exit on error

echo "=================================================="
echo "Efficient Hybrid - Installation Script"
echo "=================================================="
echo

# Detect project directory
if [ -d "$HOME/Mnemonic" ]; then
    PROJECT_DIR="$HOME/Mnemonic"
elif [ -d "$(pwd)/mnemonic" ]; then
    PROJECT_DIR="$(pwd)"
else
    echo "❌ Error: Cannot find Mnemonic project directory"
    echo "Please run this script from your Mnemonic directory"
    exit 1
fi

echo "📁 Project directory: $PROJECT_DIR"
echo

# Backup existing files
echo "📦 Creating backups..."
BACKUP_DIR="$PROJECT_DIR/.backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "$PROJECT_DIR/mnemonic/checkpointing.py" ]; then
    cp "$PROJECT_DIR/mnemonic/checkpointing.py" "$BACKUP_DIR/checkpointing.py.backup"
    echo "✓ Backed up checkpointing.py"
fi

if [ -f "$PROJECT_DIR/mnemonic/entity_type_manager.py" ]; then
    cp "$PROJECT_DIR/mnemonic/entity_type_manager.py" "$BACKUP_DIR/entity_type_manager.py.backup"
    echo "✓ Backed up entity_type_manager.py"
fi

echo "✓ Backups saved to: $BACKUP_DIR"
echo

# Check if enhanced files exist
ENHANCED_DIR="/mnt/user-data/outputs"

if [ ! -f "$ENHANCED_DIR/checkpointing_ENHANCED.py" ]; then
    echo "❌ Error: checkpointing_ENHANCED.py not found"
    echo "Please ensure the enhanced files are in: $ENHANCED_DIR"
    exit 1
fi

if [ ! -f "$ENHANCED_DIR/entity_type_manager_ENHANCED.py" ]; then
    echo "❌ Error: entity_type_manager_ENHANCED.py not found"
    echo "Please ensure the enhanced files are in: $ENHANCED_DIR"
    exit 1
fi

# Install enhanced files
echo "📥 Installing enhanced files..."

cp "$ENHANCED_DIR/checkpointing_ENHANCED.py" "$PROJECT_DIR/mnemonic/checkpointing.py"
echo "✓ Installed checkpointing.py"

cp "$ENHANCED_DIR/entity_type_manager_ENHANCED.py" "$PROJECT_DIR/mnemonic/entity_type_manager.py"
echo "✓ Installed entity_type_manager.py"

echo
echo "=================================================="
echo "✅ Installation Complete!"
echo "=================================================="
echo
echo "📋 Next Steps:"
echo "  1. Test checkpointing:"
echo "     cd $PROJECT_DIR"
echo "     python -m mnemonic.checkpointing .mnemonic/mnemonic.db"
echo
echo "  2. Test suggestions:"
echo "     mnemonic entities suggest"
echo
echo "  3. If you need to rollback:"
echo "     cp $BACKUP_DIR/*.backup mnemonic/"
echo
echo "📚 Read IMPLEMENTATION_GUIDE.md for full details"
echo