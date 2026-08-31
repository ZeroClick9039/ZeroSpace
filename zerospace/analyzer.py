import os
import json
import re
from typing import Dict, Any, List

def analyze_source_directory(src_dir: str) -> Dict[str, Any]:
    """Analyzes the tool source files recursively and returns runtime, dependencies, and metadata."""
    findings = {
        "language": "unknown",
        "entrypoint": "",
        "dependencies": [],
        "description": "",
        "dependencies_file": ""
    }
    
    detected_langs = []
    py_files = []
    c_files = []
    cpp_files = []
    rust_files = []
    
    has_requirements = False
    has_pyproject = False
    has_setup_py = False
    has_makefile = False
    has_cmake = False
    has_cargo = False
    
    # Recursively scan source directory, skipping build/dependency artifacts
    for root, dirs, filenames in os.walk(src_dir):
        # Prevent walking into container/rust build output or venvs
        for d in ["venv", "target", "cargo_home", ".git", "__pycache__", "node_modules", "build", "dist"]:
            if d in dirs:
                dirs.remove(d)
                
        is_root = (root == src_dir)
        
        for f in filenames:
            if is_root:
                if f == "requirements.txt":
                    has_requirements = True
                elif f == "pyproject.toml":
                    has_pyproject = True
                elif f == "setup.py":
                    has_setup_py = True
                elif f == "Makefile":
                    has_makefile = True
                elif f == "CMakeLists.txt":
                    has_cmake = True
                elif f == "Cargo.toml":
                    has_cargo = True
            
            f_lower = f.lower()
            if f_lower.endswith(".py"):
                py_files.append(os.path.join(root, f))
            elif f_lower.endswith(".c"):
                c_files.append(os.path.join(root, f))
            elif f_lower.endswith(".cpp") or f_lower.endswith(".cc") or f_lower.endswith(".cxx"):
                cpp_files.append(os.path.join(root, f))
            elif f_lower.endswith(".rs"):
                rust_files.append(os.path.join(root, f))
                
    # Detect active languages
    if has_requirements or has_pyproject or has_setup_py or len(py_files) > 0:
        detected_langs.append("python")
    if has_makefile or has_cmake or len(c_files) > 0 or len(cpp_files) > 0:
        detected_langs.append("c")
    if has_cargo or len(rust_files) > 0:
        detected_langs.append("rust")
        
    findings["language"] = ",".join(detected_langs) if detected_langs else "python"
    
    # Parse dependencies and configuration files
    all_deps = []
    dep_files = []
    
    if "python" in detected_langs:
        if has_requirements:
            dep_files.append("requirements.txt")
            all_deps.extend(parse_requirements(os.path.join(src_dir, "requirements.txt")))
        elif has_setup_py:
            dep_files.append("setup.py")
            all_deps.append("setup.py install")
        elif has_pyproject:
            dep_files.append("pyproject.toml")
            all_deps.extend(parse_pyproject_toml(os.path.join(src_dir, "pyproject.toml")))
            
    if "rust" in detected_langs:
        if has_cargo:
            dep_files.append("Cargo.toml")
            all_deps.extend(parse_cargo_toml(os.path.join(src_dir, "Cargo.toml")))
            
    if "c" in detected_langs:
        if has_makefile:
            dep_files.append("Makefile")
        if has_cmake:
            dep_files.append("CMakeLists.txt")
            
    findings["dependencies_file"] = ", ".join(dep_files)
    findings["dependencies"] = all_deps

    # Determine entrypoint with priority: Python -> Rust -> C/C++
    if "python" in detected_langs:
        entrypoint_candidates = ["main.py", "app.py", "run.py", "cli.py"]
        py_filenames = [os.path.basename(p) for p in py_files]
        for candidate in entrypoint_candidates:
            if candidate in py_filenames:
                findings["entrypoint"] = candidate
                break
        if not findings["entrypoint"] and py_files:
            findings["entrypoint"] = os.path.basename(py_files[0])
            
    elif "rust" in detected_langs:
        if has_cargo:
            pkg_name = parse_cargo_package_name(os.path.join(src_dir, "Cargo.toml"))
            findings["entrypoint"] = f"{pkg_name}.exe"
        else:
            findings["entrypoint"] = "main.exe"
            
    elif "c" in detected_langs:
        c_entrypoint = "main.exe"
        all_c_sources = c_files + cpp_files
        if all_c_sources:
            # Check if there is a file containing "main"
            main_src = next((f for f in all_c_sources if "main" in os.path.basename(f).lower()), None)
            if main_src:
                c_entrypoint = os.path.splitext(os.path.basename(main_src))[0] + ".exe"
            else:
                c_entrypoint = os.path.splitext(os.path.basename(all_c_sources[0]))[0] + ".exe"
        findings["entrypoint"] = c_entrypoint
        
    if not findings["entrypoint"]:
        findings["entrypoint"] = "main.py"

    # Try parsing README.md for description
    readme_path = next((os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.lower() == "readme.md"), None)
    if readme_path:
        findings["description"] = extract_description_from_readme(readme_path)
        
    return findings

def parse_requirements(filepath: str) -> List[str]:
    """Parse dependencies from requirements.txt."""
    dependencies = []
    if not os.path.exists(filepath):
        return dependencies
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r"):
                    continue
                parts = re.split(r'[=<>~!]', line)
                pkg = parts[0].strip()
                if pkg:
                    dependencies.append(pkg)
    except Exception:
        pass
    return dependencies

def parse_pyproject_toml(filepath: str) -> List[str]:
    """Parse dependencies from pyproject.toml project.dependencies block."""
    dependencies = []
    if not os.path.exists(filepath):
        return dependencies
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if match:
                deps_block = match.group(1)
                items = re.findall(r'["\']([^"\']+)["\']', deps_block)
                for item in items:
                    parts = re.split(r'[=<>~!]', item)
                    pkg = parts[0].strip()
                    if pkg:
                        dependencies.append(pkg)
    except Exception:
        pass
    return dependencies

def parse_cargo_toml(filepath: str) -> List[str]:
    """Parse dependencies from Cargo.toml."""
    dependencies = []
    if not os.path.exists(filepath):
        return dependencies
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            in_deps = False
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    if section == "dependencies" or section.startswith("dependencies."):
                        in_deps = True
                    else:
                        in_deps = False
                    continue
                if in_deps:
                    if "=" in line:
                        parts = line.split("=")
                        pkg = parts[0].strip().strip('"').strip("'").strip()
                        if pkg:
                            dependencies.append(f"{pkg} (Rust)")
    except Exception:
        pass
    return dependencies

def parse_cargo_package_name(filepath: str) -> str:
    """Parse package name from Cargo.toml."""
    if not os.path.exists(filepath):
        return "main"
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            in_package = False
            for line in f:
                line = line.strip()
                if line.startswith("[package]"):
                    in_package = True
                    continue
                elif line.startswith("[") and line.endswith("]"):
                    in_package = False
                if in_package and line.startswith("name"):
                    parts = line.split("=")
                    name = parts[1].strip().strip('"').strip("'").strip()
                    return name
    except Exception:
        pass
    return "main"

def extract_description_from_readme(filepath: str) -> str:
    """Extract a brief description from README.md (usually first non-header paragraph)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        paragraph = []
        started = False
        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                if started and paragraph:
                    break
                started = True
                continue
            if line:
                paragraph.append(line)
            elif paragraph:
                break
                
        desc = " ".join(paragraph)
        desc = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', desc)
        desc = desc.replace("**", "").replace("__", "")
        return desc[:200] + "..." if len(desc) > 200 else desc
    except Exception:
        return ""

