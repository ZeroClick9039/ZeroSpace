import os
import urllib.request
import zipfile
import shutil
import logging
from urllib.parse import urlparse
from zerospace.config import get_tools_dir

logger = logging.getLogger("zerospace.downloader")

def is_safe_path(base_dir: str, path: str) -> bool:
    """Check if the path resolves inside base_dir to prevent Zip Slip directory traversal."""
    abs_base = os.path.realpath(base_dir)
    abs_path = os.path.realpath(path)
    return abs_path.startswith(abs_base + os.sep) or abs_path == abs_base

def convert_github_url(url: str) -> list:
    """Convert a GitHub repo URL into potential ZIP download URLs.
    e.g. https://github.com/owner/repo -> [
        https://github.com/owner/repo/archive/refs/heads/main.zip,
        https://github.com/owner/repo/archive/refs/heads/master.zip,
        https://github.com/owner/repo/zipball/main
    ]
    """
    url = url.rstrip("/")
    parsed = urlparse(url)
    
    if parsed.netloc != "github.com":
        return [url]
        
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return [url]
        
    owner, repo = parts[0], parts[1]
    # Re-assemble standard github URL
    base_url = f"https://github.com/{owner}/{repo}"
    
    # Try different branches and formats
    urls = [
        f"{base_url}/archive/refs/heads/main.zip",
        f"{base_url}/archive/refs/heads/master.zip",
        f"{base_url}/archive/master.zip",
        f"{base_url}/zipball/main"
    ]
    return urls

def download_file(url: str, dest_path: str) -> bool:
    """Download a file from a URL to a local destination path."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        logger.warning(f"Failed download from {url}: {e}")
        return False

def extract_zip(zip_path: str, extract_to: str) -> bool:
    """Extract a ZIP archive safely with path verification."""
    os.makedirs(extract_to, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Avoid malicious paths
                target_path = os.path.join(extract_to, member)
                if not is_safe_path(extract_to, target_path):
                    logger.error(f"Security Alert: Path traversal attempt blocked in zip: {member}")
                    return False
            
            # If all files are safe, extract
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return False

def download_and_extract_tool(source: str, tool_id: str) -> str:
    """Downloads a tool from github/web or copies from local filesystem, then extracts it.
    Returns the path to the tool's source code.
    """
    tool_dir = os.path.join(get_tools_dir(), tool_id)
    src_dir = os.path.join(tool_dir, "src")
    
    if os.path.exists(tool_dir):
        shutil.rmtree(tool_dir)
        
    os.makedirs(src_dir, exist_ok=True)
    temp_dir = os.path.join(tool_dir, "temp_download")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 1. Local path
        if os.path.isdir(source) or (os.path.isfile(source) and not source.startswith(("http://", "https://"))):
            if os.path.isdir(source):
                shutil.rmtree(src_dir)
                shutil.copytree(source, src_dir)
            else:
                shutil.copy2(source, os.path.join(src_dir, os.path.basename(source)))
            shutil.rmtree(temp_dir, ignore_errors=True)
            return src_dir

        # 2. Remote URL
        download_urls = []
        if "github.com" in source:
            download_urls = convert_github_url(source)
        else:
            download_urls = [source]

        downloaded = False
        zip_temp_path = os.path.join(temp_dir, "archive.zip")
        
        for url in download_urls:
            logger.info(f"Attempting to download tool from: {url}")
            if download_file(url, zip_temp_path):
                downloaded = True
                break
                
        if not downloaded:
            raise Exception("All download URLs failed.")
            
        # Extract to temp directory first
        extract_temp = os.path.join(temp_dir, "extracted")
        if not extract_zip(zip_temp_path, extract_temp):
            raise Exception("Safe zip extraction failed.")
            
        # Clean up zip
        os.remove(zip_temp_path)
        
        # GitHub ZIP archives contain a root subfolder like 'repo-main'.
        # Move files from the subfolder directly to src_dir.
        contents = os.listdir(extract_temp)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_temp, contents[0])):
            nested_dir = os.path.join(extract_temp, contents[0])
            for item in os.listdir(nested_dir):
                shutil.move(os.path.join(nested_dir, item), os.path.join(src_dir, item))
        else:
            for item in contents:
                shutil.move(os.path.join(extract_temp, item), os.path.join(src_dir, item))
                
        shutil.rmtree(temp_dir, ignore_errors=True)
        return src_dir

    except Exception as e:
        shutil.rmtree(tool_dir, ignore_errors=True)
        raise e
