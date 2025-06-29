#!/bin/bash

# Build and push RAG Toolkit Docker image
# Usage: ./scripts/build_docker.sh [tag]

set -e

# Configuration
IMAGE_NAME="ragtoolkit/ragtoolkit"
TAG=${1:-latest}
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

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
if [ ! -f "Dockerfile.production" ]; then
    log_error "Dockerfile.production not found. Run this script from the project root."
    exit 1
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the frontend first (to ensure it's included)
log_info "Building React frontend..."
cd ragtoolkit/ui
if [ -f "package.json" ]; then
    npm install
    npm run build
    log_success "Frontend built successfully"
else
    log_warning "No package.json found, skipping frontend build"
fi
cd ../..

# Build the Docker image
log_info "Building Docker image: $FULL_IMAGE_NAME"
docker build -f Dockerfile.production -t "$FULL_IMAGE_NAME" .

# Also tag as latest if not already latest
if [ "$TAG" != "latest" ]; then
    docker tag "$FULL_IMAGE_NAME" "${IMAGE_NAME}:latest"
    log_info "Also tagged as ${IMAGE_NAME}:latest"
fi

log_success "Docker image built successfully!"

# Show image details
log_info "Image details:"
docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

# Ask if user wants to push
echo
read -p "Do you want to push the image to Docker Hub? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Pushing image to Docker Hub..."
    
    # Check if logged in to Docker Hub
    if ! docker info | grep -q "Username:"; then
        log_warning "You may need to login to Docker Hub first:"
        log_info "Run: docker login"
    fi
    
    docker push "$FULL_IMAGE_NAME"
    
    if [ "$TAG" != "latest" ]; then
        docker push "${IMAGE_NAME}:latest"
    fi
    
    log_success "Image pushed to Docker Hub!"
    log_info "Users can now pull with: docker pull $FULL_IMAGE_NAME"
else
    log_info "Image build complete but not pushed."
    log_info "To push later, run: docker push $FULL_IMAGE_NAME"
fi

# Test the image locally
echo
read -p "Do you want to test the image locally? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Testing image locally..."
    
    # Create a test docker-compose file
    cat > docker-compose.test.yml << EOF
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ragtoolkit
      POSTGRES_USER: ragtoolkit
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ragtoolkit"]
      interval: 5s
      timeout: 5s
      retries: 5

  ragtoolkit:
    image: $FULL_IMAGE_NAME
    environment:
      DATABASE_URL: postgresql://ragtoolkit:test_password@postgres:5432/ragtoolkit
      RAGTOOLKIT_API_KEY: test_key_123
    ports:
      - "8001:8000"  # Use different port to avoid conflicts
      - "3001:3000"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

    log_info "Starting test deployment..."
    docker-compose -f docker-compose.test.yml up -d
    
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Test API health
    if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
        log_success "✅ API is healthy at http://localhost:8001"
        log_success "✅ Dashboard should be available at http://localhost:3001"
        
        echo
        log_info "Test deployment is running!"
        log_info "API: http://localhost:8001"
        log_info "Dashboard: http://localhost:3001"
        echo
        read -p "Press Enter to stop the test deployment..."
        
    else
        log_error "❌ API health check failed"
        log_info "Check logs with: docker-compose -f docker-compose.test.yml logs"
    fi
    
    # Cleanup
    docker-compose -f docker-compose.test.yml down -v
    rm docker-compose.test.yml
    log_info "Test deployment cleaned up"
fi

log_success "Docker build and test complete!" 