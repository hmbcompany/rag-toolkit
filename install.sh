#!/bin/bash

# RAG Toolkit One-Command Installer
# Usage: bash <(curl -sL get.ragtoolkit.com)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RAGTK_VERSION="latest"
COMPOSE_URL="https://raw.githubusercontent.com/hmbcompany/rag-toolkit/main/docker-compose.production.yml"
RAGTK_DIR="$HOME/.ragtoolkit"
CONFIG_FILE="$HOME/.ragtk.yaml"

# Logging functions
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

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)  OS="macos";;
        Linux*)   OS="linux";;
        CYGWIN*|MINGW*|MSYS*) OS="windows";;
        *) 
            log_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac
    log_info "Detected OS: $OS"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Docker on macOS
install_docker_macos() {
    log_info "Installing Docker Desktop for macOS..."
    
    # Check if Homebrew is available
    if command_exists brew; then
        log_info "Using Homebrew to install Docker..."
        brew install --cask docker
    else
        log_warning "Homebrew not found. Please install Docker Desktop manually from https://docker.com/products/docker-desktop"
        log_info "After installation, please run this script again."
        exit 1
    fi
    
    log_warning "Please start Docker Desktop and run this script again."
    exit 0
}

# Function to install Docker on Linux
install_docker_linux() {
    log_info "Installing Docker on Linux..."
    
    # Detect Linux distribution
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    else
        log_error "Cannot detect Linux distribution"
        exit 1
    fi
    
    case $DISTRO in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg lsb-release
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$DISTRO/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        centos|rhel|fedora)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        *)
            log_error "Unsupported Linux distribution: $DISTRO"
            log_info "Please install Docker manually: https://docs.docker.com/engine/install/"
            exit 1
            ;;
    esac
    
    # Start and enable Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    log_warning "Please log out and log back in for Docker group changes to take effect, then run this script again."
    exit 0
}

# Function to install Docker on Windows
install_docker_windows() {
    log_error "Windows installation requires Docker Desktop to be installed manually."
    log_info "Please download and install Docker Desktop from: https://docker.com/products/docker-desktop"
    log_info "After installation, run this script again from Git Bash or WSL."
    exit 1
}

# Function to check and install Docker
ensure_docker() {
    log_info "Checking for Docker..."
    
    if command_exists docker; then
        # Check if Docker daemon is running
        if docker info >/dev/null 2>&1; then
            log_success "Docker is installed and running"
            return 0
        else
            log_warning "Docker is installed but not running"
            case $OS in
                macos)
                    log_info "Please start Docker Desktop"
                    open -a Docker
                    ;;
                linux)
                    log_info "Starting Docker service..."
                    sudo systemctl start docker
                    ;;
            esac
            
            # Wait for Docker to start
            log_info "Waiting for Docker to start..."
            for i in {1..30}; do
                if docker info >/dev/null 2>&1; then
                    log_success "Docker is now running"
                    return 0
                fi
                sleep 2
            done
            
            log_error "Docker failed to start"
            exit 1
        fi
    else
        log_warning "Docker not found. Installing Docker..."
        case $OS in
            macos)   install_docker_macos;;
            linux)   install_docker_linux;;
            windows) install_docker_windows;;
        esac
    fi
}

# Function to generate secure token
generate_token() {
    if command_exists openssl; then
        openssl rand -hex 32
    elif command_exists python3; then
        python3 -c "import secrets; print(secrets.token_hex(32))"
    elif command_exists python; then
        python -c "import os; print(os.urandom(32).hex())"
    else
        # Fallback to date-based token (less secure)
        echo "rtk_$(date +%s)_$(echo $RANDOM | md5sum | head -c 32)"
    fi
}

# Function to create configuration
create_config() {
    log_info "Creating configuration file..."
    
    # Generate secure admin token
    ADMIN_TOKEN="rtk_$(generate_token)"
    
    # Create config directory
    mkdir -p "$RAGTK_DIR"
    
    # Create config file
    cat > "$CONFIG_FILE" << EOF
# RAG Toolkit Configuration
api_url: "http://localhost:8000"
project: "default"
token: "$ADMIN_TOKEN"
created: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
version: "0.2.0"
EOF
    
    log_success "Configuration created at $CONFIG_FILE"
    echo "RAGTOOLKIT_API_KEY=$ADMIN_TOKEN" > "$RAGTK_DIR/.env"
}

# Function to setup Docker stack
setup_stack() {
    log_info "Setting up RAG Toolkit stack..."
    
    # Create ragtoolkit directory
    mkdir -p "$RAGTK_DIR"
    cd "$RAGTK_DIR"
    
    # Download docker-compose file
    log_info "Downloading Docker Compose configuration..."
    curl -fsSL "$COMPOSE_URL" -o docker-compose.yml
    
    # Generate secure postgres password
    POSTGRES_PASSWORD=$(generate_token | head -c 16)
    
    # Create environment file
    cat > .env << EOF
RAGTOOLKIT_API_KEY=$ADMIN_TOKEN
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
OPENAI_API_KEY=${OPENAI_API_KEY:-}
EOF
    
    log_info "Starting RAG Toolkit services..."
    docker compose pull
    docker compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    for i in {1..60}; do
        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            log_success "RAG Toolkit API is ready!"
            break
        fi
        if [ $i -eq 60 ]; then
            log_error "Services failed to start within 2 minutes"
            log_info "Check logs with: cd ~/.ragtoolkit && docker compose logs"
            exit 1
        fi
        sleep 2
    done
}

# Function to open browser
open_browser() {
    local url="http://localhost:3000"
    
    log_info "Opening RAG Toolkit dashboard..."
    
    # Wait a moment for frontend to be ready
    sleep 5
    
    case $OS in
        macos)
            open "$url"
            ;;
        linux)
            if command_exists xdg-open; then
                xdg-open "$url"
            elif command_exists gnome-open; then
                gnome-open "$url"
            else
                log_warning "Could not open browser automatically"
            fi
            ;;
        windows)
            if command_exists cmd.exe; then
                cmd.exe /c start "$url"
            else
                log_warning "Could not open browser automatically"
            fi
            ;;
    esac
}

# Function to show completion message
show_completion() {
    log_success "RAG Toolkit installation complete!"
    echo
    echo "🎉 RAG Toolkit is now running!"
    echo
    echo "📊 Dashboard: http://localhost:3000"
    echo "🔧 API:       http://localhost:8000"
    echo "📁 Config:    $CONFIG_FILE"
    echo
    echo "Quick start:"
    echo "  pip install ragtoolkit"
    echo "  # Add @trace decorator to your RAG functions"
    echo
    echo "Management commands:"
    echo "  cd ~/.ragtoolkit"
    echo "  docker compose logs    # View logs"
    echo "  docker compose stop    # Stop services"
    echo "  docker compose start   # Start services"
    echo
    echo "For help: https://docs.ragtoolkit.com"
}

# Main installation flow
main() {
    echo "🚀 RAG Toolkit One-Command Installer"
    echo "======================================"
    echo
    
    # Check for existing installation
    if [ -f "$CONFIG_FILE" ] && [ -d "$RAGTK_DIR" ]; then
        log_warning "Existing installation detected at $RAGTK_DIR"
        read -p "Continue with fresh installation? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled"
            exit 0
        fi
    fi
    
    # Installation steps
    detect_os
    ensure_docker
    create_config
    setup_stack
    open_browser
    show_completion
}

# Error handling
trap 'log_error "Installation failed at line $LINENO. Check the logs above for details."' ERR

# Run main function
main "$@" 