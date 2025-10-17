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
    echo "  start       - Start the USDXFixGap application"
    echo "  test        - Run all tests with pytest"
    echo "  install     - Install/update requirements (auto-detects GPU)"
    echo "  install --gpu   - Force GPU/CUDA PyTorch installation"
    echo "  install --cpu   - Force CPU-only PyTorch installation"
    echo "  install-dev - Install development dependencies (testing, analysis)"
    echo "  clean       - Clean cache and temporary files"
    echo "  shell       - Start interactive Python shell"
    echo "  info        - Show environment info"
    echo "  analyze     - Run code quality analysis (complexity, style)"
    echo "  analyze all - Analyze entire project"
    echo "  analyze files <path>  - Analyze specific files"
    echo "  cleanup     - Clean code (whitespace, unused imports)"
    echo "  cleanup all - Clean entire project"
    echo "  cleanup --dry-run  - Preview cleanup without changes"
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
        
        # Check for manual GPU/CPU override flags
        INSTALL_MODE="auto"
        if [[ "$2" == "--gpu" ]] || [[ "$2" == "--cuda" ]]; then
            INSTALL_MODE="gpu"
        elif [[ "$2" == "--cpu" ]]; then
            INSTALL_MODE="cpu"
        fi
        
        # Detect NVIDIA GPU for PyTorch optimization
        echo ""
        print_info "Detecting hardware configuration..."
        
        if [[ "$INSTALL_MODE" == "cpu" ]]; then
            print_warning "Manual Override: Installing CPU-only version as requested"
            pip install -r "$SCRIPT_DIR/requirements.txt" --upgrade
            echo ""
            print_success "Installation complete!"
            exit 0
        fi
        
        if [[ "$INSTALL_MODE" == "gpu" ]]; then
            print_warning "Manual Override: Installing GPU version as requested"
        else
            # Auto-detection mode
            if command -v nvidia-smi &> /dev/null; then
                print_success "GPU Detected: NVIDIA GPU found - installing PyTorch with CUDA support"
            else
                print_info "CPU Mode: No NVIDIA GPU detected - installing CPU-only PyTorch"
                print_info "Tip: If you have an NVIDIA GPU, use './run.sh install --gpu' to force GPU installation"
                pip install -r "$SCRIPT_DIR/requirements.txt" --upgrade
                echo ""
                print_success "Installation complete!"
                exit 0
            fi
        fi
        
        # Install GPU version
        print_info "This will enable GPU acceleration for faster processing"
        
        # Install base requirements first (without PyTorch)
        pip install -r "$SCRIPT_DIR/requirements.txt" --upgrade
        
        # Uninstall any existing PyTorch (CPU or CUDA)
        echo ""
        print_info "Removing existing PyTorch installation..."
        pip uninstall -y torch torchvision torchaudio 2>/dev/null || true
        
        # Install PyTorch with CUDA 12.1 support
        echo ""
        print_info "Installing PyTorch with CUDA 12.1 support..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        
        # Verify CUDA availability
        echo ""
        print_info "Verifying GPU acceleration..."
        python -c "import torch; print('GPU Available:', torch.cuda.is_available()); cuda_available = torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0) if cuda_available else 'N/A')"
        
        echo ""
        print_success "Installation complete!"
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
    "install-dev")
        print_info "Installing development dependencies..."
        pip install -r "$SCRIPT_DIR/requirements-dev.txt" --upgrade
        echo ""
        print_success "Development dependencies installed!"
        echo "You can now use:"
        echo "  - ./run.sh analyze    (code quality analysis)"
        echo "  - ./run.sh cleanup    (code cleanup tools)"
        ;;
    "analyze")
        print_info "Running code quality analysis..."
        cd "$SCRIPT_DIR"
        
        # Check if analyze script exists
        if [[ ! -f "scripts/analyze_code.py" ]]; then
            print_error "scripts/analyze_code.py not found"
            print_error "Make sure you're in the project root directory"
            exit 1
        fi
        
        # Default to "changed" mode if no second argument
        ANALYZE_MODE="${2:-changed}"
        
        # Pass all arguments to analyze script
        shift  # Remove first argument (analyze)
        python scripts/analyze_code.py "$ANALYZE_MODE" "${@:2}"
        ;;
    "cleanup")
        print_info "Running code cleanup..."
        cd "$SCRIPT_DIR"
        
        # Check if cleanup script exists
        if [[ ! -f "scripts/cleanup_code.py" ]]; then
            print_error "scripts/cleanup_code.py not found"
            print_error "Make sure you're in the project root directory"
            exit 1
        fi
        
        # Default to "changed" mode if no second argument
        CLEANUP_MODE="${2:-changed}"
        
        # Pass all arguments to cleanup script
        shift  # Remove first argument (cleanup)
        python scripts/cleanup_code.py "$CLEANUP_MODE" "${@:2}"
        ;;
    *)
        print_info "Executing: $*"
        cd "$SCRIPT_DIR"
        "$@"
        ;;
esac

exit $?