#!/usr/bin/env python3
"""
Development Setup Script for Crypto Rebalancer

This script helps new developers set up their development environment.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_step(step: str):
    """Print step with formatting"""
    print(f"\n🔧 {step}")

def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print warning message"""
    print(f"⚠️  {message}")

def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")

def check_python_version():
    """Check if Python version is compatible"""
    print_step("Checking Python version...")
    
    version = sys.version_info
    if version.major != 3 or version.minor < 9:
        print_error(f"Python 3.9+ required. Current version: {version.major}.{version.minor}")
        return False
    
    print_success(f"Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def check_git():
    """Check if git is available"""
    print_step("Checking Git availability...")
    
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print_success("Git is available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning("Git not found. Some features may not work correctly.")
        return False

def create_venv():
    """Create virtual environment"""
    print_step("Setting up virtual environment...")
    
    venv_path = Path(".venv")
    if venv_path.exists():
        print_warning("Virtual environment already exists. Skipping creation.")
        return True
    
    try:
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print_success("Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to create virtual environment")
        return False

def install_requirements():
    """Install Python requirements"""
    print_step("Installing requirements...")
    
    # Determine pip path
    if os.name == 'nt':  # Windows
        pip_path = Path(".venv/Scripts/pip.exe")
        python_path = Path(".venv/Scripts/python.exe")
    else:  # Unix/Mac
        pip_path = Path(".venv/bin/pip")
        python_path = Path(".venv/bin/python")
    
    if not pip_path.exists():
        print_error("Virtual environment pip not found. Please create venv first.")
        return False
    
    try:
        # Upgrade pip first
        subprocess.run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        print_success("Requirements installed")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install requirements")
        return False

def setup_env_file():
    """Set up environment file"""
    print_step("Setting up environment file...")
    
    env_path = Path(".env")
    env_example_path = Path(".env.example")
    
    if env_path.exists():
        print_warning(".env file already exists. Skipping creation.")
        return True
    
    if not env_example_path.exists():
        print_warning(".env.example not found. Creating basic .env file.")
        # Create basic .env
        env_content = """# Crypto Rebalancer Environment Variables
# Development Configuration

# API Keys (fill in your own)
COINGECKO_API_KEY=your_coingecko_api_key_here
CT_API_KEY=your_cointracking_api_key_here
CT_API_SECRET=your_cointracking_api_secret_here

# Development settings
DEBUG=true
DEBUG_TOKEN=dev-secret-2024

# Database (optional)
DATABASE_URL=sqlite:///./crypto_rebalancer.db

# Redis (optional, for caching)
REDIS_URL=redis://localhost:6379

# CORS (development)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000
"""
        env_path.write_text(env_content)
    else:
        # Copy from example
        shutil.copy(env_example_path, env_path)
    
    print_success(".env file created. Please fill in your API keys!")
    return True

def create_data_dirs():
    """Create necessary data directories"""
    print_step("Creating data directories...")
    
    dirs = [
        "data/raw",
        "data/monitoring",
        "data/execution_history",
        "data/backups"
    ]
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print_success("Data directories created")
    return True

def check_ports():
    """Check if required ports are available"""
    print_step("Checking port availability...")
    
    import socket
    
    ports = [8000, 8765]  # FastAPI default ports
    available_ports = []
    
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', port))
            if result == 0:
                print_warning(f"Port {port} is already in use")
            else:
                available_ports.append(port)
                print_success(f"Port {port} is available")
    
    return len(available_ports) > 0

def print_next_steps():
    """Print next steps for the developer"""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    
    print("\n📋 NEXT STEPS:")
    print("1. Activate your virtual environment:")
    
    if os.name == 'nt':  # Windows
        print("   .venv\\Scripts\\activate")
    else:  # Unix/Mac
        print("   source .venv/bin/activate")
    
    print("\n2. Fill in your API keys in .env file")
    
    print("\n3. Start the development server:")
    print("   python -m uvicorn api.main:app --reload --port 8000")
    
    print("\n4. Open the dashboard:")
    print("   http://localhost:8000/static/dashboard.html")
    
    print("\n📁 USEFUL DIRECTORIES:")
    print("   /debug/        - Development tools and debug scripts")
    print("   /tests/        - Organized test suite")
    print("   /api/utils/    - Reusable utilities")
    print("   /shared/       - Common constants and assets groups")
    
    print("\n🧪 RUN TESTS:")
    print("   pytest tests/unit/           # Unit tests")
    print("   pytest tests/integration/    # Integration tests")
    print("   pytest tests/e2e/           # End-to-end tests")
    
    print("\n🐛 DEBUG TOOLS:")
    print("   python debug/scripts/debug_coingecko.py")
    print("   http://localhost:8000/debug/html/debug-dashboard.html")

def main():
    """Main setup function"""
    print("🚀 Crypto Rebalancer Development Setup")
    print("=====================================")
    
    # Check system requirements
    if not check_python_version():
        sys.exit(1)
    
    check_git()
    
    # Setup environment
    steps = [
        create_venv,
        install_requirements,
        setup_env_file,
        create_data_dirs,
        check_ports
    ]
    
    for step in steps:
        if not step():
            print_error("Setup failed. Please fix the issues above.")
            sys.exit(1)
    
    print_next_steps()

if __name__ == "__main__":
    main()