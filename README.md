# Sun Builders Projects LLP - Real Estate GST Automation System

## Overview
This system automates the creation of the CA-standard multi-sheet GSTR-1 calculation and accounting journal entries workbook for **Sun Builders Projects LLP (formerly Sun Realty)** directly from Tally company data (`010010`).

---

## 1. Statutory Real Estate GST Rules Implemented

| Rule | Legal Basis | Implementation |
| :--- | :--- | :--- |
| **Post-BU Collections (Exempt)** | Schedule III, Entry 5 of CGST Act | If installment payment date $\ge$ BU Permission date, consideration is marked as **Exempt Income** on `FINAL CALC` (e.g. Footprint Exempt Income ₹8.46 Cr). |
| **Affordable Residential ($\le$ ₹45L)** | Notification 03/2019-CT(R) | Taxed at **1% GST** (0.5% CGST + 0.5% SGST) without ITC. |
| **Non-Affordable Residential (> ₹45L)** | Notification 03/2019-CT(R) | Taxed at **5% GST** (2.5% CGST + 2.5% SGST) without ITC. |
| **Commercial Shops in Residential (RREP)** | Notification 03/2019-CT(R) | Taxed at **5% GST** (2.5% CGST + 2.5% SGST) without ITC. |
| **Pure Commercial (Sun Gravitas)** | Notification 11/2017-CT(R) | Taxed at **18% with 1/3rd Land Abatement** (Effective 12% on Gross). |
| **Pure Agent Deductions** | Rule 33 of CGST Rules | Stamp Duty (Cr/Dr) and Sub-Registrar Registration Fees (Cr/Dr) are contra-deducted before tax. |
| **Non-Taxable Deposits** | Contract Act & GST Valuation | Refundable Maintenance Deposits are excluded from construction consideration. |
| **Cheque Returns & Cancellations** | Section 34 of CGST Act | Dishonoured cheques and booking refunds are deducted to adjust net tax liability. |

---

## 2. Directory Structure

```text
c:\Project_AI\sun_builders\
├── data\
│   └── 010010\                      <- Extracted Tally Database (96MB TranMgr.1800, Manager.1800)
├── downloads\
│   └── setup_tally_7.1_gold.exe     <- Official Tally Installer ready to install
├── config\
│   └── project_master.json          <- Project BU dates, tax rates, and deduction keywords
├── core\
│   ├── tally_client.py              <- Live Tally XML API over port 9000
│   ├── tally_file_reader.py         <- Offline Daybook XML / Excel reader fallback
│   ├── gst_rules.py                 <- Real estate GST legal classification engine
│   └── excel_generator.py           <- Multi-sheet workbook builder with live formulas
├── templates\
│   └── index.html                   <- Google Stitch Ultra-Modern Executive Dashboard UI
├── static\
│   └── js\app.js                    <- Real-time client JS (AJAX generation, status polling, logs)
├── output\
│   └── GSTR-1_AUG-26_AUTOMATED.xlsx <- Finalized GST workbook
├── server.py                        <- Flask Web Application Server (REST API on port 5050)
├── run_app.bat                      <- One-click launcher for Windows
└── app.py                           <- CLI runner
```

---

## 3. How to Launch the Web Application

### Option A: One-Click Startup (Recommended)
Double-click `run_app.bat` in the project root. It will:
1. Start the Flask Application Server on `http://localhost:5050`.
2. Automatically launch your default browser showing the Google Stitch executive dashboard.

### Option B: Command Line
```bash
python server.py
```
Then navigate to: **[http://localhost:5050](http://localhost:5050)**

---

## 4. Key Statutory Real Estate Compliance Rules Enforced

1. **Sun Footprint BU Permission Cutoff (18/03/2025):**
   - Per CA directive, BU permission for **Sun Footprint** was granted as on **18/03/2025**.
   - Any member advances or installment receipts received **strictly after 18th March 2025** are classified as **100% EXEMPT** from GST under Schedule III, Entry 5 of the CGST Act (Sale of Land & Completed Building).
   - Member advances received **before 18th March 2025** remain **Taxable** (1% for Affordable $\le$ ₹45L, 5% for Non-Affordable > ₹45L).

2. **5 Mandatory Non-GST Excluded Categories:**
   GST is strictly **NOT** calculated on the following 5 ancillary collections:
   - **Refundable Security Deposit**
   - **Stamp Duty (Cr/Dr)**
   - **Registration Fees (Cr/Dr)**
   - **Maintenance Deposit / Expenses**
   - **Electricity Expenses (AEC / AUDA / Torrent)**

3. **Tax Rate Hierarchy:**
   - **Residential $\le$ ₹45 Lakhs:** **1% GST** (0.5% CGST + 0.5% SGST) without ITC.
   - **Residential > ₹45 Lakhs:** **5% GST** (2.5% CGST + 2.5% SGST) without ITC.
   - **Commercial Shops in RREP:** **5% GST** (2.5% CGST + 2.5% SGST) without ITC.
   - **Pure Commercial (Sun Gravitas):** **18% GST** with **1/3rd Land Abatement** (Effective 12% on Gross).

---

## 5. How to Install and Run Tally on This Laptop

1. **Run the Installer:**
   - Double-click `c:\Project_AI\sun_builders\downloads\setup_tally_7.1_gold.exe` or click **"Launch Tally Setup"** on the Web Dashboard.
   - Click **Install**.
2. **Open in Educational Mode (Free):**
   - Launch Tally and select **Continue in Educational Mode**.
3. **Open Company 010010:**
   - In Tally, press **Alt + F3** $\rightarrow$ **Select Company**.
   - Set the company path to:
     `c:\Project_AI\sun_builders\data`
   - Select **010010 (SUN BUILDERS PROJECTS LLP)**.
4. **Ensure Port 9000 is Active:**
   - By default, Tally listens on port 9000.
   - You can verify via: **F1: Help $\rightarrow$ Settings $\rightarrow$ Connectivity $\rightarrow$ Client/Server configuration $\rightarrow$ Tally acts as 'Both', Port 9000**.

---

## 6. Procedure to Extract Another Project / Company Backup (.zip / .rar)

When the CA office receives another `.zip` or `.rar` backup file for another company or project of Sun Builders, you can use any of the methods below:

### Method 1: Ingest via Web Dashboard (Recommended & Aesthetic)
1. Open the dashboard at **[http://localhost:5050](http://localhost:5050)**.
2. Click the **"Ingest Backup (.zip / .rar)"** button in the top navigation bar, or open the **Voucher Ingestion** tab.
3. **Drag & drop** your `.zip` or `.rar` file into the glowing dropzone (or enter the path).
4. Click **Start Automated Extraction & Database Mount**.
5. Watch the real-time glowing progress bar and multi-step checklist (*Unpacking archive &rarr; Scanning database &rarr; Mounting to data/ &rarr; Linking Tally Port 9000*).
6. Once complete, click **View Vouchers & Prepare GSTR-1** to start preparing returns!

### Method 2: Automated CLI Script
Run `extract_backup.py` with the path to the received file:
```bash
# For a .zip file
python extract_backup.py "C:\path\to\another_project.zip"

# For a .rar file
python extract_backup.py "C:\path\to\010011.rar"
```

### Method 3: Manual Drag & Drop Extraction
1. Right-click the `.zip` or `.rar` file $\rightarrow$ **Extract All** (or extract using WinRAR / 7-Zip).
2. Look inside the extracted folder for the **5-digit or 6-digit numeric folder** (e.g., `010011` or `10002`). This folder contains files like `Company.1800`, `TranMgr.1800`, and `Manager.1800`.
3. Copy or move that numeric folder into:
   ```text
   c:\Project_AI\sun_builders\data\<company_folder>\
   ```
   *Example:* `c:\Project_AI\sun_builders\data\010011\`

### Method 4: REST API Endpoint
```bash
curl -X POST http://localhost:5050/api/upload_backup -H "Content-Type: application/json" -d "{\"path\": \"C:\\path\\to\\another_project.zip\"}"
```

### Loading the New Company in Tally:
1. In Tally, press **Alt + F3** $\rightarrow$ **Select Company**.
2. Set path to: `c:\Project_AI\sun_builders\data`.
3. The new company will immediately appear in the company list with its official name and company number.
4. Select and press Enter to open it. Tally will serve its vouchers through Port 9000 to the web application automatically.


