#!/usr/bin/env python3
"""
Build script for AFBench Admin UI

Builds a static Streamlit site in the /site directory from data in /data.
Rebuilds everything from scratch, no caching, aggressive error handling.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def validate_data_directory():
    """Validate that required data files exist."""
    data_dir = Path("data")

    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' does not exist")

    required_files = [
        "skill_ratings.json",
        "tournament_summaries.json",
        "loaded_models.json",
        "loaded_judges.json",
        "loaded_skills.json",
    ]

    missing_files = []
    for file in required_files:
        if not (data_dir / file).exists():
            missing_files.append(file)

    if missing_files:
        raise FileNotFoundError(f"Missing required data files: {missing_files}")

    # Validate JSON structure
    for file in required_files:
        try:
            with open(data_dir / file) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file}: {e}")

    print(f"✅ Data validation passed - {len(required_files)} files verified")


def clean_site_directory():
    """Remove existing site directory and create fresh one."""
    site_dir = Path("site")

    if site_dir.exists():
        shutil.rmtree(site_dir)
        print(f"🗑️  Removed existing site directory")

    site_dir.mkdir()
    print(f"📁 Created fresh site directory")


def check_dependencies():
    """Check that required Python packages are installed."""
    required_packages = ["streamlit", "pandas", "plotly", "numpy"]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"❌ Missing required packages: {missing_packages}")
        print("Install with: pip install " + " ".join(missing_packages))
        sys.exit(1)

    print(f"✅ Dependencies verified - {len(required_packages)} packages available")


def copy_admin_ui():
    """Copy admin UI script to site directory."""
    admin_ui_path = Path("admin_ui.py")

    if not admin_ui_path.exists():
        raise FileNotFoundError("admin_ui.py not found in project root")

    site_dir = Path("site")
    shutil.copy2(admin_ui_path, site_dir / "app.py")
    print("📋 Copied admin_ui.py to site/app.py")


def create_streamlit_config():
    """Create Streamlit configuration in project root."""
    config_dir = Path(".streamlit")
    config_dir.mkdir(exist_ok=True)

    config_content = """
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
fileWatcherType = "auto"
runOnSave = true

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[logger]
level = "error"

[global]
developmentMode = true
"""

    with open(config_dir / "config.toml", "w") as f:
        f.write(config_content.strip())

    print("⚙️  Created Streamlit configuration in project root")


def create_data_access():
    """Set up data access for the site."""
    site_dir = Path("site")

    # Remove any existing data symlink
    data_link = site_dir / "data"
    if data_link.exists():
        if data_link.is_symlink():
            data_link.unlink()
        elif data_link.is_dir():
            shutil.rmtree(data_link)

    # Copy data directory instead of symlinking to avoid getcwd issues
    data_source = Path("data")
    if data_source.exists():
        shutil.copytree(data_source, data_link)
        print("📁 Copied data directory to site")
    else:
        print("⚠️  Data directory not found - site will not have data access")


def test_streamlit_app():
    """Test that the Streamlit app can start without errors."""
    site_dir = Path("site")

    # Change to site directory
    original_cwd = os.getcwd()
    os.chdir(site_dir)

    try:
        # Test app can import without errors
        result = subprocess.run(
            [sys.executable, "-c", "import app; print('✅ App imports successfully')"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ App import failed:")
            print(result.stderr)
            sys.exit(1)

        print(result.stdout.strip())

    except subprocess.TimeoutExpired:
        print("❌ App test timed out")
        sys.exit(1)
    finally:
        os.chdir(original_cwd)


def create_run_script():
    """Create script to run the admin UI from project root."""
    # Create run script in project root instead of site subdirectory
    run_script = Path("run_admin_ui.sh")
    script_content = """#!/bin/bash
set -e

echo "🚀 Starting AFBench Admin UI..."
echo "📍 Navigate to: http://localhost:8501"
echo "🛑 Press Ctrl+C to stop"

# Run from project root to avoid directory issues
streamlit run admin_ui.py
"""

    with open(run_script, "w") as f:
        f.write(script_content)

    # Make executable
    os.chmod(run_script, 0o755)
    print("📜 Created run_admin_ui.sh script in project root")


def main():
    """Main build process."""
    print("🔨 Building AFBench Admin UI")
    print("=" * 50)

    try:
        # Step 1: Validate data
        validate_data_directory()

        # Step 2: Check dependencies
        check_dependencies()

        # Step 3: Clean and prepare site directory
        clean_site_directory()

        # Step 4: Copy application files
        copy_admin_ui()

        # Step 5: Create configuration
        create_streamlit_config()

        # Step 6: Set up data access
        create_data_access()

        # Step 7: Test the application
        test_streamlit_app()

        # Step 8: Create run script
        create_run_script()

        print("=" * 50)
        print("✅ Build completed successfully!")
        print()
        print("To run the admin UI:")
        print("  ./run_admin_ui.sh")
        print()
        print("Or manually:")
        print("  streamlit run admin_ui.py")

    except Exception as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
