#!/bin/bash

# Configuration
VENV_DIR=".venv"
PYTHON_VERSION="3.10"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/$VENV_DIR/bin/python"
VENV_PIP="$SCRIPT_DIR/$VENV_DIR/bin/pip"

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

# Bootstrap venv if missing
if [[ ! -f "$VENV_PYTHON" ]]; then
    print_info "Virtual environment not found. Creating at $VENV_DIR..."
    
    # Detect system Python
    if command -v python3.10 &> /dev/null; then
        SYS_PYTHON="python3.10"
        print_info "Using Python 3.10"
    elif command -v python3.8 &> /dev/null; then
        SYS_PYTHON="python3.8"
        print_info "Using Python 3.8"
    elif command -v python3 &> /dev/null; then
        SYS_PYTHON="python3"
        print_info "Using system python3"
    else
        print_error "No Python 3 installation found"
        print_error "Please install Python 3.8+ from your package manager"
        exit 1
    fi
    
    # Create venv
    $SYS_PYTHON -m venv "$SCRIPT_DIR/$VENV_DIR"
    if [[ $? -ne 0 ]]; then
        print_error "Failed to create virtual environment"
        print_error "Make sure python3-venv is installed: sudo apt-get install python3-venv"
        exit 1
    fi
    
    print_info "Upgrading pip..."
    "$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
    if [[ $? -ne 0 ]]; then
        print_error "Failed to upgrade pip"
        exit 1
    fi
    
    print_info "Installing requirements..."
    "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt"
    if [[ $? -ne 0 ]]; then
        print_error "Failed to install requirements"
        exit 1
    fi
    print_success "Virtual environment created successfully"
fi

# Handle different command shortcuts
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [command] [args...]"
    echo ""
    echo "Available shortcuts:"
    echo "  start       - Start the USDXFixGap application"
    echo "  test        - Run all tests with pytest"
    echo "  test --docs - Run tests and generate Tier-1/Tier-3 visual artifacts"
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
        "$VENV_PYTHON" usdxfixgap.py
        ;;
    "test")
        print_info "Running tests..."
        cd "$SCRIPT_DIR"
        
        # Check for --docs flag
        TEST_DOCS=""
        PYTEST_ARGS=""
        
        # Parse arguments looking for --docs or --artifacts
        for arg in "$@"; do
            if [[ "$arg" == "--docs" ]] || [[ "$arg" == "--artifacts" ]]; then
                TEST_DOCS=1
            else
                PYTEST_ARGS="$PYTEST_ARGS $arg"
            fi
        done
        
        # Set environment variables for doc generation
        if [[ -n "$TEST_DOCS" ]]; then
            export GAP_TIER1_WRITE_DOCS=1
            export GAP_TIER3_WRITE_DOCS=1
            print_info "[Test Artifacts] Visual artifacts will be generated in docs/gap-tests/"
        fi
        
        "$VENV_PYTHON" -m pytest tests/ -q $PYTEST_ARGS
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
            "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt" --upgrade
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
                "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt" --upgrade
                echo ""
                print_success "Installation complete!"
                exit 0
            fi
        fi
        
        # Install GPU version
        print_info "This will enable GPU acceleration for faster processing"
        
        # Install base requirements first (without PyTorch)
        "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt" --upgrade
        
        # Uninstall any existing PyTorch (CPU or CUDA)
        echo ""
        print_info "Removing existing PyTorch installation..."
        "$VENV_PIP" uninstall -y torch torchvision torchaudio 2>/dev/null || true
        
        # Install PyTorch with CUDA 12.1 support
        echo ""
        print_info "Installing PyTorch with CUDA 12.1 support..."
        "$VENV_PIP" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        
        # Verify CUDA availability
        echo ""
        print_info "Verifying GPU acceleration..."
        "$VENV_PYTHON" -c "import torch; print('GPU Available:', torch.cuda.is_available()); cuda_available = torch.cuda.is_available(); print('GPU:', torch.cuda.get_device_name(0) if cuda_available else 'N/A')"
        
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
        
        # Remove all __pycache__ directories recursively
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        
        print_success "Cache cleaned successfully"
        ;;
    "shell")
        print_info "Starting Python interactive shell..."
        print_info "Virtual environment: $VENV_DIR"
        "$VENV_PYTHON"
        ;;
    "info")
        echo "Environment Information:"
        echo "========================"
        echo "Virtual Environment: $VENV_DIR"
        echo ""
        echo "Python Version:"
        "$VENV_PYTHON" --version
        echo ""
        echo "Python Location:"
        which "$VENV_PYTHON"
        echo ""
        echo "Installed Packages:"
        "$VENV_PIP" list
        ;;
    "install-dev")
        print_info "Installing development dependencies..."
        "$VENV_PIP" install -r "$SCRIPT_DIR/requirements-dev.txt" --upgrade
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
        "$VENV_PYTHON" scripts/analyze_code.py "$ANALYZE_MODE" "${@:2}"
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
        "$VENV_PYTHON" scripts/cleanup_code.py "$CLEANUP_MODE" "${@:2}"
        ;;
    *)
        print_info "Executing: $*"
        cd "$SCRIPT_DIR"
        "$@"
        ;;
esac

exit $?