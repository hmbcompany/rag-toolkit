#!/bin/bash

# Build and publish RAG Toolkit to PyPI
# Usage: ./scripts/build_and_publish.sh [test|prod]

set -e

# Configuration
PACKAGE_NAME="ragtoolkit"
BUILD_DIR="dist"
MODE=${1:-test}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    log_error "setup.py not found. Run this script from the project root."
    exit 1
fi

# Clean previous builds
log_info "Cleaning previous builds..."
rm -rf $BUILD_DIR build *.egg-info

# Install/upgrade build tools
log_info "Installing/upgrading build tools..."
pip install --upgrade pip setuptools wheel twine build

# Build the package
log_info "Building package..."
python -m build

# Check the build
log_info "Checking package..."
twine check dist/*

# Show package contents
log_info "Package contents:"
ls -la dist/

# Extract version from package
VERSION=$(python -c "import ragtoolkit; print(ragtoolkit.__version__)")
log_info "Package version: $VERSION"

# Upload based on mode
if [ "$MODE" == "prod" ]; then
    log_warning "Publishing to PyPI (production)..."
    read -p "Are you sure you want to publish version $VERSION to PyPI? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        twine upload dist/*
        log_success "Published to PyPI!"
        log_info "Install with: pip install $PACKAGE_NAME==$VERSION"
    else
        log_info "Publish cancelled"
    fi
elif [ "$MODE" == "test" ]; then
    log_info "Publishing to TestPyPI..."
    twine upload --repository testpypi dist/*
    log_success "Published to TestPyPI!"
    log_info "Test install with: pip install --index-url https://test.pypi.org/simple/ $PACKAGE_NAME==$VERSION"
else
    log_error "Invalid mode: $MODE. Use 'test' or 'prod'"
    exit 1
fi

log_success "Build and publish complete!" 