# Sun Builders - Tally Cloud Bridge Setup (CA Office Guide)

This guide explains how to connect **TallyPrime / Tally.ERP 9 (Port 9000)** on the CA Office PC with the Sun Builders Railway Cloud App:
**`https://sunbuilders-production.up.railway.app/`**

---

## 🔍 Root Cause of Yesterday's Screenshots

1. **Screenshot 1 (`Python isn't installed...`)**:
   `Start_Tally_Agent.bat` could not detect a working Python runtime in the PC's system `PATH`.
2. **Screenshot 2 (`Python installation manager configuration helper`)**:
   Windows opened the default Microsoft Store App Execution Alias (`WindowsApps\python.exe` / `py.exe`).
   - The user accepted long path support and shortcut path prompts.
   - At the bottom, it prompted: `Install the current latest version of CPython? If not, you can use 'py install default' later to install.`
   - Because `CPython` runtime itself was never installed, the script could not run.

---

## 🚀 Two Solutions Provided

### Solution 1: Zero-Install Standalone EXE (Recommended)
**No Python installation, no PATH settings, and no admin rights needed.**

1. Send the folder `dist_bridge\SunBuilders_Tally_Agent` (or a zip of it) to the CA Office.
2. In the CA Office, open Tally with the relevant company loaded (Port 9000).
3. Double-click **`SunBuilders_Tally_Agent.exe`** (or `Start_Tally_Agent.bat`).
4. That's it! It runs instantly and connects directly to Railway Cloud.

---

### Solution 2: 1-Click Automated Python Setup (`Install_Python_And_Setup.bat`)
If you prefer running the Python script directly:

1. Copy **`Install_Python_And_Setup.bat`** and **`Start_Tally_Agent.bat`** to the CA Office PC.
2. Double-click **`Install_Python_And_Setup.bat`** (or choose Option `1` inside `Start_Tally_Agent.bat`).
3. The script automatically:
   - Disables the Windows Store popup trap.
   - Downloads official Python 3.12 64-bit installer from `python.org`.
   - Installs Python silently for the user (no admin password needed).
   - Configures the Windows `PATH` environment variable permanently.
   - Automatically launches the Tally Cloud Bridge Agent!
