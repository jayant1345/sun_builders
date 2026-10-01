import os
import subprocess
import urllib.request
from typing import Callable, Optional

TALLY_INSTALLER_URL = "https://tallymirror.tallysolutions.com/download_centre/Rel.7.1_gold/TP/Full/setup.exe"

class TallyManager:
    """
    Manages automated downloading, installation, and data configuration for Tally 7.1 / TallyPrime.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.downloads_dir = os.path.join(base_dir, "downloads")
        self.data_dir = os.path.join(base_dir, "data")
        self.installer_path = os.path.join(self.downloads_dir, "setup_tally_7.1_gold.exe")
        os.makedirs(self.downloads_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def is_tally_installed(self) -> bool:
        """Checks standard directories for tally.exe"""
        check_paths = [
            r"C:\Program Files\TallyPrime\tally.exe",
            r"C:\Program Files\Tally.ERP9\tally.exe",
            r"C:\TallyPrime\tally.exe",
            r"C:\Tally.ERP9\tally.exe",
            r"C:\Tally\tally.exe"
        ]
        return any(os.path.exists(p) for p in check_paths)

    def get_tally_exe_path(self) -> Optional[str]:
        check_paths = [
            r"C:\Program Files\TallyPrime\tally.exe",
            r"C:\Program Files\Tally.ERP9\tally.exe",
            r"C:\TallyPrime\tally.exe",
            r"C:\Tally.ERP9\tally.exe",
            r"C:\Tally\tally.exe"
        ]
        for p in check_paths:
            if os.path.exists(p):
                return p
        return None

    def download_tally_installer(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
        """Downloads Tally installer if not already present."""
        if os.path.exists(self.installer_path) and os.path.getsize(self.installer_path) > 10_000_000:
            return self.installer_path

        def reporthook(blocknum, blocksize, totalsize):
            if progress_callback:
                progress_callback(blocknum * blocksize, totalsize)

        urllib.request.urlretrieve(TALLY_INSTALLER_URL, self.installer_path, reporthook=reporthook)
        return self.installer_path

    def launch_installer(self) -> bool:
        """Launches the Tally Setup Manager for installation."""
        if os.path.exists(self.installer_path):
            try:
                import subprocess
                subprocess.Popen([self.installer_path], shell=True)
                return True
            except Exception:
                try:
                    os.startfile(self.installer_path)
                    return True
                except Exception as e:
                    print(f"[TallyManager] Error launching installer: {e}")
                    return False
        return False

    def launch_tally(self) -> bool:
        """Launches the installed Tally executable."""
        exe = self.get_tally_exe_path()
        if exe:
            try:
                import subprocess
                subprocess.Popen([exe], shell=True)
                return True
            except Exception:
                try:
                    os.startfile(exe)
                    return True
                except Exception as e:
                    print(f"[TallyManager] Error launching Tally: {e}")
                    return False
        return False


    def get_company_data_path(self) -> str:
        """Returns the absolute path to the extracted 010010 database."""
        return os.path.join(self.data_dir)
