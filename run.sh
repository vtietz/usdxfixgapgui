#!/bin/bash

# Configuration
ENV_NAME="usdxfixgapgui"
PYTHON_VERSION="3.8"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Check if conda is available
if ! command -v conda &> /dev/null; then
    print_error "conda is not available in PATH"
    print_error "Please install Anaconda/Miniconda or add it to your PATH"
    exit 1
fi

# Initialize conda for bash (required for conda activate to work in scripts)
eval "$(conda shell.bash hook)"

# Function to check if environment is active
check_env_active() {
    if [[ "$CONDA_DEFAULT_ENV" == "$ENV_NAME" ]]; then
        return 0  # Environment is active
    else
        return 1  # Environment is not active
    fi
}

# Check if environment is active
if check_env_active; then
    print_info "Environment $ENV_NAME is already active"
else
    # Check if environment exists
    if conda info --envs | grep -q "^$ENV_NAME "; then
        print_info "Activating environment $ENV_NAME..."
        conda activate "$ENV_NAME"
        if [[ $? -ne 0 ]]; then
            print_error "Failed to activate conda environment"
            exit 1
        fi
    else
        print_info "Environment $ENV_NAME does not exist. Creating it..."
        conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
        if [[ $? -ne 0 ]]; then
            print_error "Failed to create conda environment"
            exit 1
        fi
        
        print_info "Installing requirements..."
        conda activate "$ENV_NAME"
        pip install -r "$SCRIPT_DIR/requirements.txt"
        if [[ $? -ne 0 ]]; then
            print_error "Failed to install requirements"
            exit 1
        fi
        print_success "Environment created and requirements installed"
    fi
fi

# Handle different command shortcuts
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [command] [args...]"
    echo ""
    echo "Available shortcuts:"
    echo "  start    - Start the USDXFixGap application"
    echo "  test     - Run all tests with pytest"
    echo "  install  - Install/update requirements"
    echo "  clean    - Clean cache and temporary files"
    echo "  shell    - Start interactive Python shell"
    echo "  info     - Show environment info"
    echo ""
    echo "Or run any Python command directly:"
    echo "  $0 python script.py"
    echo "  $0 pip install package"
    exit 0
fi

case "$1" in
    "start")
        print_info "Starting USDXFixGap application..."
        cd "$SCRIPT_DIR/src"
        python usdxfixgap.py
        ;;
    "test")
        print_info "Running tests..."
        cd "$SCRIPT_DIR"
        python -m pytest tests/ -v
        ;;
    "install")
        print_info "Installing/updating requirements..."
        pip install -r "$SCRIPT_DIR/requirements.txt" --upgrade
        ;;
    "clean")
        print_info "Cleaning cache and temporary files..."
        cd "$SCRIPT_DIR"
        
        # Remove cache files
        [[ -f "src/cache.db" ]] && rm "src/cache.db"
        [[ -d "src/__pycache__" ]] && rm -rf "src/__pycache__"
        [[ -d "tests/__pycache__" ]] && rm -rf "tests/__pycache__"
        [[ -d "output" ]] && rm -rf "output"
        
        # Remove all __pycache__ directories recursively
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        
        print_success "Cache cleaned successfully"
        ;;
    "shell")
        print_info "Starting Python interactive shell..."
        python
        ;;
    "info")
        echo "Environment Information:"
        echo "========================"
        conda info
        echo ""
        echo "Python Version:"
        python --version
        echo ""
        echo "Installed Packages:"
        pip list
        ;;
    *)
        print_info "Executing: $*"
        cd "$SCRIPT_DIR"
        "$@"
        ;;
esac

exit $?