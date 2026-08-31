import os
import shutil
import tarfile
import tempfile
import time

def make_ar_header(name: str, size: int) -> bytes:
    header = (
        f"{name:<16}"
        f"{int(time.time()):<12}"
        f"{'0':<6}"
        f"{'0':<6}"
        f"{'100644':<8}"
        f"{size:<10}"
        f"`\n"
    )
    return header.encode("ascii")

def main():
    print("ZeroSpace Linux Debian Package Build Script")
    print("==========================================")
    
    # Create dist folder if it doesn't exist
    os.makedirs("dist", exist_ok=True)
    
    # We will build control.tar.gz and data.tar.gz in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Working in temporary folder: {tmpdir}")
        
        # --- 1. Prepare CONTROL files ---
        control_dir = os.path.join(tmpdir, "control_dir")
        os.makedirs(control_dir, exist_ok=True)
        
        control_content = (
            "Package: zerospace\n"
            "Version: 1.0.0\n"
            "Section: utils\n"
            "Priority: optional\n"
            "Architecture: all\n"
            "Depends: python3, python3-pip, python3-venv\n"
            "Maintainer: ZeroSpace Team <maintainer@zerospace.local>\n"
            "Description: ZeroSpace Multi-Language Cybersecurity Tool Manager\n"
            " ZeroSpace is an isolated sandbox environment tool manager that runs Python, C/C++, and Rust cybersecurity tools safely.\n"
        )
        
        control_file = os.path.join(control_dir, "control")
        with open(control_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(control_content)
            
        postinst_content = (
            "#!/bin/sh\n"
            "set -e\n"
            "chmod +x /usr/bin/zerospace\n"
            "echo \"==================================================\"\n"
            "echo \" ZeroSpace Cybersecurity Tool Manager Installed! \"\n"
            "echo \"==================================================\"\n"
            "echo \"To launch ZeroSpace, simply run:\"\n"
            "echo \"  zerospace\"\n"
            "echo \"\"\n"
            "echo \"Note: ZeroSpace runs in your user context. Sandbox\"\n"
            "echo \"environments, logs, and database will be stored in\"\n"
            "echo \"your home directory under ~/.zerospace.\"\n"
            "echo \"==================================================\"\n"
            "exit 0\n"
        )
        
        postinst_file = os.path.join(control_dir, "postinst")
        with open(postinst_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(postinst_content)
            
        # Compress control files
        control_tar = os.path.join(tmpdir, "control.tar.gz")
        with tarfile.open(control_tar, "w:gz", format=tarfile.GNU_FORMAT) as tar:
            def control_filter(tarinfo):
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = "root"
                tarinfo.gname = "root"
                if tarinfo.name.endswith("postinst"):
                    tarinfo.mode = 0o755
                else:
                    tarinfo.mode = 0o644
                return tarinfo
            
            tar.add(control_file, arcname="./control", filter=control_filter)
            tar.add(postinst_file, arcname="./postinst", filter=control_filter)
            
        # --- 2. Prepare DATA files ---
        data_dir = os.path.join(tmpdir, "data_dir")
        
        # Binary destination
        bin_dest = os.path.join(data_dir, "usr", "bin")
        os.makedirs(bin_dest, exist_ok=True)
        shutil.copy2("zerospace_wrapper.sh", os.path.join(bin_dest, "zerospace"))
        
        # App share destination
        app_dest = os.path.join(data_dir, "usr", "share", "zerospace")
        os.makedirs(app_dest, exist_ok=True)
        
        # Copy app files
        shutil.copy2("main.py", os.path.join(app_dest, "main.py"))
        shutil.copytree("zerospace", os.path.join(app_dest, "zerospace"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree("mock_tools", os.path.join(app_dest, "mock_tools"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        
        # Compress data files
        data_tar = os.path.join(tmpdir, "data.tar.gz")
        with tarfile.open(data_tar, "w:gz", format=tarfile.GNU_FORMAT) as tar:
            def data_filter(tarinfo):
                tarinfo.uid = 0
                tarinfo.gid = 0
                tarinfo.uname = "root"
                tarinfo.gname = "root"
                if tarinfo.isdir():
                    tarinfo.mode = 0o755
                elif tarinfo.name.endswith("usr/bin/zerospace"):
                    tarinfo.mode = 0o755
                else:
                    tarinfo.mode = 0o644
                return tarinfo
                
            tar.add(data_dir, arcname=".", filter=data_filter)
            
        # --- 3. Build debian-binary ---
        deb_binary_content = b"2.0\n"
        
        # --- 4. Package as .deb (ar archive) ---
        deb_path = os.path.join("dist", "zerospace.deb")
        with open(deb_path, "wb") as deb:
            # write ar global header
            deb.write(b"!<arch>\n")
            
            # 1. debian-binary
            deb.write(make_ar_header("debian-binary", len(deb_binary_content)))
            deb.write(deb_binary_content)
            # odd size padding
            if len(deb_binary_content) % 2 != 0:
                deb.write(b"\n")
                
            # 2. control.tar.gz
            with open(control_tar, "rb") as f:
                content = f.read()
                deb.write(make_ar_header("control.tar.gz", len(content)))
                deb.write(content)
                if len(content) % 2 != 0:
                    deb.write(b"\n")
                    
            # 3. data.tar.gz
            with open(data_tar, "rb") as f:
                content = f.read()
                deb.write(make_ar_header("data.tar.gz", len(content)))
                deb.write(content)
                if len(content) % 2 != 0:
                    deb.write(b"\n")
                    
    print("\nSUCCESS: Linux Debian package built at: dist/zerospace.deb")

if __name__ == "__main__":
    main()
