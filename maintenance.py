#!/usr/bin/env python3
"""
Maintenance Script for Crypto Rebalancer

Provides utilities for cleaning up temporary files, rotating logs, etc.
"""
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json

def print_step(step: str):
    """Print step with formatting"""
    print(f"\n🔧 {step}")

def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")

def print_warning(message: str):
    """Print warning message"""
    print(f"⚠️  {message}")

def clean_temp_files():
    """Clean up temporary files"""
    print_step("Cleaning temporary files...")
    
    temp_patterns = [
        "temp_*.json",
        "*_temp.json", 
        "*.tmp",
        "*.log",
        "*.bak",
        "rebalance-actions.csv"
    ]
    
    cleaned_count = 0
    
    # Clean root directory
    for pattern in temp_patterns:
        for file_path in Path(".").glob(pattern):
            if file_path.is_file():
                file_path.unlink()
                cleaned_count += 1
                print(f"   Removed: {file_path}")
    
    # Clean data directory
    data_dir = Path("data")
    if data_dir.exists():
        for pattern in temp_patterns:
            for file_path in data_dir.rglob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_count += 1
                    print(f"   Removed: {file_path}")
    
    # Clean test fixtures temp files
    fixtures_dir = Path("tests/fixtures")
    if fixtures_dir.exists():
        for pattern in ["temp_*.json", "diagnostic_*.html"]:
            for file_path in fixtures_dir.glob(pattern):
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_count += 1
                    print(f"   Removed: {file_path}")
    
    print_success(f"Cleaned {cleaned_count} temporary files")

def clean_old_backups(days_old: int = 30):
    """Clean backup files older than specified days"""
    print_step(f"Cleaning backups older than {days_old} days...")
    
    backup_dirs = [
        "data/backups",
        "data"
    ]
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    cleaned_count = 0
    
    for backup_dir in backup_dirs:
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            continue
            
        # Look for backup files
        backup_patterns = ["*_backup_*.json", "*.bak"]
        
        for pattern in backup_patterns:
            for file_path in backup_path.glob(pattern):
                if file_path.is_file():
                    # Check file modification time
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_path.unlink()
                        cleaned_count += 1
                        print(f"   Removed old backup: {file_path}")
    
    print_success(f"Cleaned {cleaned_count} old backup files")

def clean_cache():
    """Clean Python cache files"""
    print_step("Cleaning Python cache...")
    
    cleaned_count = 0
    
    # Remove __pycache__ directories
    for cache_dir in Path(".").rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)
            cleaned_count += 1
            print(f"   Removed: {cache_dir}")
    
    # Remove .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        if pyc_file.is_file():
            pyc_file.unlink()
            cleaned_count += 1
            print(f"   Removed: {pyc_file}")
    
    print_success(f"Cleaned {cleaned_count} cache files")

def rotate_logs():
    """Rotate log files in data directory"""
    print_step("Rotating log files...")
    
    data_dir = Path("data")
    if not data_dir.exists():
        print_warning("Data directory not found")
        return
    
    # Look for large monitoring files
    monitoring_dir = data_dir / "monitoring"
    if monitoring_dir.exists():
        for json_file in monitoring_dir.glob("metrics_*.json"):
            if json_file.stat().st_size > 10 * 1024 * 1024:  # > 10MB
                # Create backup and truncate
                backup_name = f"{json_file.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = monitoring_dir / backup_name
                
                shutil.copy2(json_file, backup_path)
                
                # Keep only recent entries (truncate file)
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list) and len(data) > 1000:
                        # Keep only last 500 entries
                        truncated_data = data[-500:]
                        with open(json_file, 'w') as f:
                            json.dump(truncated_data, f, indent=2)
                        
                        print(f"   Rotated: {json_file} (kept last 500 entries)")
                
                except (json.JSONDecodeError, Exception) as e:
                    print_warning(f"Could not rotate {json_file}: {e}")

def check_disk_usage():
    """Check disk usage of project directories"""
    print_step("Checking disk usage...")
    
    directories = [
        "data",
        "tests",
        "debug", 
        ".venv" if Path(".venv").exists() else None
    ]
    
    total_size = 0
    
    for dir_name in directories:
        if dir_name is None:
            continue
            
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
        
        dir_size = sum(
            f.stat().st_size for f in dir_path.rglob('*') if f.is_file()
        )
        
        size_mb = dir_size / (1024 * 1024)
        total_size += size_mb
        
        print(f"   {dir_name}/: {size_mb:.1f} MB")
    
    print_success(f"Total project size: {total_size:.1f} MB")
    
    if total_size > 1000:  # > 1GB
        print_warning("Project size is getting large. Consider cleaning up.")

def show_statistics():
    """Show project statistics"""
    print_step("Project Statistics:")
    
    # Count files by type
    extensions = {}
    total_files = 0
    
    for file_path in Path(".").rglob("*"):
        if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
            ext = file_path.suffix.lower()
            if not ext:
                ext = "no extension"
            
            extensions[ext] = extensions.get(ext, 0) + 1
            total_files += 1
    
    print(f"   Total files: {total_files}")
    
    # Show top extensions
    sorted_extensions = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
    print("   File types:")
    for ext, count in sorted_extensions[:10]:
        print(f"     {ext}: {count}")

def main():
    """Main maintenance function"""
    if len(sys.argv) < 2:
        print("🧹 Crypto Rebalancer Maintenance")
        print("================================")
        print("\nUsage: python maintenance.py <command>")
        print("\nCommands:")
        print("  clean       - Clean temporary files")
        print("  backups     - Clean old backup files")
        print("  cache       - Clean Python cache files")
        print("  logs        - Rotate large log files")
        print("  disk        - Check disk usage")
        print("  stats       - Show project statistics")
        print("  all         - Run all maintenance tasks")
        return
    
    command = sys.argv[1].lower()
    
    if command == "clean":
        clean_temp_files()
    elif command == "backups":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        clean_old_backups(days)
    elif command == "cache":
        clean_cache()
    elif command == "logs":
        rotate_logs()
    elif command == "disk":
        check_disk_usage()
    elif command == "stats":
        show_statistics()
    elif command == "all":
        clean_temp_files()
        clean_old_backups()
        clean_cache()
        rotate_logs()
        check_disk_usage()
        show_statistics()
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)
    
    print("\n🎉 Maintenance complete!")

if __name__ == "__main__":
    main()