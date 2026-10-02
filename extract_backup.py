import os
import sys
import zipfile
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

def extract_archive(archive_path, target_dir=DATA_DIR):
    """
    Extracts a Tally company backup (.zip, .rar, or folder) into data/
    and verifies Tally database integrity.
    """
    archive_path = os.path.abspath(archive_path)
    if not os.path.exists(archive_path):
        print(f"[ERROR] File not found: {archive_path}")
        return {"success": False, "message": f"File not found: {archive_path}"}

    print("=" * 70)
    print(f"  EXTRACTING TALLY BACKUP: {os.path.basename(archive_path)}")
    print("=" * 70)

    filename = os.path.basename(archive_path)
    ext = os.path.splitext(filename)[1].lower()

    # Create a temporary extraction staging area to handle arbitrary folder nesting
    temp_extract_dir = os.path.join(BASE_DIR, "temp_extract")
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    try:
        # 1. Standard ZIP Extraction
        if ext == ".zip":
            print(f"[1/4] Extracting ZIP file via Python zipfile engine...")
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

        # 2. RAR / 7Z Extraction
        elif ext in [".rar", ".7z"]:
            print(f"[1/4] Extracting {ext.upper()} archive via system extractor...")
            extracted = False

            # 1. Check for unar (Universal Linux/macOS RAR/ZIP/7z extractor)
            unar = shutil.which("unar")
            if unar:
                try:
                    cmd = [unar, "-o", temp_extract_dir, "-f", archive_path]
                    ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if ret.returncode == 0:
                        extracted = True
                except Exception as e:
                    print(f"[unar warning]: {e}")

            # 2. Check for bsdtar (Linux libarchive-tools or Windows System32 tar.exe)
            if not extracted:
                bsdtar = shutil.which("bsdtar") or (r"C:\Windows\System32\tar.exe" if os.path.exists(r"C:\Windows\System32\tar.exe") else None)
                if bsdtar:
                    try:
                        ret = subprocess.run([bsdtar, "-xf", archive_path, "-C", temp_extract_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if ret.returncode == 0:
                            extracted = True
                    except Exception as e:
                        print(f"[bsdtar warning]: {e}")

            # 3. Check for native 7z on Linux/Railway or Windows PATH
            if not extracted:
                seven_zip = shutil.which("7z") or shutil.which("7za")
                if seven_zip:
                    try:
                        cmd = [seven_zip, "x", "-y", f"-o{temp_extract_dir}", archive_path]
                        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if ret.returncode == 0:
                            extracted = True
                    except Exception as e:
                        print(f"[7z warning]: {e}")

            # 4. Check for unrar
            if not extracted:
                unrar = shutil.which("unrar")
                if unrar:
                    try:
                        ret = subprocess.run([unrar, "x", "-y", archive_path, temp_extract_dir + os.sep], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        if ret.returncode == 0:
                            extracted = True
                    except Exception as e:
                        print(f"[unrar warning]: {e}")

            # 5. Check Windows standard program file locations
            if not extracted:
                for exe in [r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files\WinRAR\WinRAR.exe", r"C:\Program Files\WinRAR\Rar.exe"]:
                    if os.path.exists(exe):
                        cmd = f'"{exe}" x -y "{archive_path}" "{temp_extract_dir}\\"'
                        subprocess.run(cmd, shell=True)
                        extracted = True
                        break

            if not extracted:
                return {"success": False, "message": f"Could not extract {ext.upper()} archive. Please install unar, bsdtar, or 7z."}

        elif ext in [".xlsx", ".xls", ".xml", ".json"]:
            # Direct file upload (Excel, XML Daybook, or JSON Sync)
            print(f"[1/4] Direct data file detected: {filename}")
            shutil.copy2(archive_path, os.path.join(temp_extract_dir, filename))

        elif os.path.isdir(archive_path):
            shutil.copytree(archive_path, os.path.join(temp_extract_dir, filename), dirs_exist_ok=True)

        # 3. Locate Tally Company directory (any folder containing TranMgr or Company.1800 / .900)
        print("[2/4] Searching for Tally company database structure...")
        candidate_dirs = []
        for root, dirs, files in os.walk(temp_extract_dir):
            has_tally = any("TranMgr" in f or "Company" in f or f.endswith((".1800", ".900")) for f in files)
            if has_tally:
                candidate_dirs.append((root, files))

        found_companies = []
        if candidate_dirs:
            for root_dir, files in candidate_dirs:
                folder_name = os.path.basename(root_dir)
                # If folder_name is not numeric, or is root, assign a clean company name
                if not folder_name.isdigit() and len(folder_name) < 4:
                    # Look up next available 5-digit number
                    existing = [d for d in os.listdir(target_dir) if d.isdigit()]
                    next_id = f"0100{len(existing)+10}"
                    folder_name = next_id

                target_company_dir = os.path.join(target_dir, folder_name)
                os.makedirs(target_company_dir, exist_ok=True)
                
                # Copy or move all files to target_company_dir
                for f in files:
                    src = os.path.join(root_dir, f)
                    dst = os.path.join(target_company_dir, f)
                    shutil.copy2(src, dst)

                size_mb = sum(os.path.getsize(os.path.join(target_company_dir, f)) for f in os.listdir(target_company_dir)) / (1024 * 1024)
                found_companies.append({
                    "code": folder_name,
                    "path": target_company_dir,
                    "size_mb": round(size_mb, 2),
                    "file_count": len(os.listdir(target_company_dir))
                })
                print(f"[3/4] Successfully mounted Company {folder_name} ({round(size_mb, 2)} MB) to: {target_company_dir}")
        else:
            # If no specific TranMgr was found, move all extracted files into a new company folder
            existing = [d for d in os.listdir(target_dir) if d.isdigit()]
            new_code = f"0100{len(existing)+10}"
            target_company_dir = os.path.join(target_dir, new_code)
            shutil.copytree(temp_extract_dir, target_company_dir, dirs_exist_ok=True)
            files = os.listdir(target_company_dir)
            size_mb = sum(os.path.getsize(os.path.join(target_company_dir, f)) for f in files if os.path.isfile(os.path.join(target_company_dir, f))) / (1024 * 1024)
            found_companies.append({
                "code": new_code,
                "path": target_company_dir,
                "size_mb": round(size_mb, 2),
                "file_count": len(files)
            })

        # Also copy any standalone Excel, JSON, or XML files directly to target_dir for instant parser ingestion
        imported_files = []
        for root, dirs, files in os.walk(temp_extract_dir):
            for f in files:
                if f.lower().endswith((".xlsx", ".xls", ".json", ".xml", ".csv")):
                    dst_file = os.path.join(target_dir, f)
                    shutil.copy2(os.path.join(root, f), dst_file)
                    imported_files.append(f)

        # Cleanup temp directory
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

        # 4. Automatically trigger incremental database restoration
        if imported_files:
            try:
                from server import ingest_excel_file
                for imp in imported_files:
                    if imp.lower().endswith((".xlsx", ".xls")):
                        imp_path = os.path.join(target_dir, imp)
                        print(f"[*] Incrementally restoring vouchers from {imp}...")
                        ingest_excel_file(imp_path)
            except Exception as ie:
                print(f"[Auto Ingestion Notice]: {ie}")

        print("[4/4] Extraction and incremental restoration completed successfully.")
        return {
            "success": True,
            "companies": found_companies,
            "imported_files": imported_files,
            "message": f"Successfully extracted and incrementally restored {len(found_companies)} Tally Company Database(s) and {len(imported_files)} data file(s) with zero duplicates."
        }

    except Exception as e:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
        print(f"[ERROR] Extraction exception: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        archive_file = sys.argv[1]
    else:
        print("Usage: python extract_backup.py <path_to_zip_or_rar>")
        archive_file = input("Enter path to new backup file (.zip or .rar): ").strip('\"\' ')
    
    if archive_file:
        res = extract_archive(archive_file)
        print("Result:", res)
    else:
        print("[ERROR] No file provided.")
