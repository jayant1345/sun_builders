"""
Sun Builders - Local Tally to Railway Cloud Sync Agent
======================================================
Runs on the CA Office local Windows PC.
1. Connects to local Tally running in Education Mode / Licensed Mode (Port 9000).
2. Extracts daybook and member collection vouchers for selected project.
3. Securely pushes the data to the Railway cloud web application.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.tally_client import TallyClient

def check_tally(tally_url="http://localhost:9000"):
    req_xml = """<ENVELOPE>
        <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>List of Companies</ID></HEADER>
        <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
    </ENVELOPE>"""
    try:
        req = urllib.request.Request(tally_url, data=req_xml.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def extract_from_local_files():
    """Fallback: reads local Excel master if Tally live port is offline."""
    import openpyxl
    excel_candidates = [
        os.path.join(BASE_DIR, "data", "01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"),
        r"C:\naman_ca\Sun_Builders\01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"
    ]
    target_path = None
    for p in excel_candidates:
        if os.path.exists(p):
            target_path = p
            break
            
    if not target_path:
        return []

    print(f"[*] Extracting member vouchers from local file: {os.path.basename(target_path)}")
    wb = openpyxl.load_workbook(target_path, read_only=True, data_only=True)
    vouchers = []
    
    if "SUN REALTY FOOTPRINT- MEMBERS" in wb.sheetnames:
        ws = wb["SUN REALTY FOOTPRINT- MEMBERS"]
        idx = 1
        for row in ws.iter_rows(values_only=True):
            flat_no = str(row[0]).strip() if row[0] is not None else ""
            name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            if not flat_no or not name:
                continue
            if any(k in flat_no for k in ["Flat No.", "Total", "Sun", "CALCULATION", "MEMBERS", "Payment"]):
                continue

            def parse_float(val):
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            cr_amount = parse_float(row[2])
            reg_dr = parse_float(row[4]) if len(row) > 4 else 0.0
            stamp_dr = parse_float(row[6]) if len(row) > 6 else 0.0
            deductions = stamp_dr + reg_dr
            taxable = max(0.0, cr_amount - deductions)

            clean_name = name
            m = re.match(r"^[A-Za-z0-9\/\-\.]+(?:,|;|\s\-|\s)\s*(.+)$", name)
            if m:
                clean_name = m.group(1).strip()

            classification = "Taxable @ 1% (Affordable Residential)"
            badge_type = "taxable-1"
            if cr_amount == 0 and deductions > 0:
                classification = "Non-GST Excluded (Pass-Through Fees)"
                badge_type = "excluded"
            elif deductions >= cr_amount and cr_amount > 0:
                classification = "Non-GST Excluded (Stamp Duty / Reg Off-set)"
                badge_type = "excluded"

            day = (idx % 28) + 1
            vouchers.append({
                "vch_no": f"FP-2608-{idx:03d}",
                "date": f"{day:02d}-08-2026",
                "type": "Member Receipt",
                "flat_no": flat_no,
                "member_name": clean_name,
                "raw_name": name,
                "project": "Sun Footprint",
                "cr_amount": cr_amount,
                "deductions": deductions,
                "taxable_amount": taxable,
                "classification": classification,
                "badge_type": badge_type
            })
            idx += 1
            
    return vouchers

def sync_to_railway(railway_url="http://localhost:5050", project_name="Sun Footprint"):
    print("=" * 65)
    print("      SUN BUILDERS - LOCAL TALLY TO RAILWAY SYNC AGENT")
    print(f"      Cloud Destination: {railway_url}")
    print("=" * 65)

    vouchers = []
    tally_online = check_tally()

    if tally_online:
        print("[OK] Local Tally connection established on Port 9000.")
        client = TallyClient()
        companies = client.get_loaded_companies()
        print(f"[OK] Active Loaded Companies in Tally: {companies}")
        
        # If companies loaded, extract live vouchers
        if companies:
            comp_name = companies[0]
            project_name = comp_name
            print(f"[*] Querying live Tally Daybook for '{comp_name}'...")
            try:
                xml_data = client.export_vouchers_xml(comp_name, "20000101", "20991231")
                raw_vchs = client.parse_vouchers(xml_data)
                print(f"[OK] Extracted {len(raw_vchs)} live vouchers from Tally.")
                if raw_vchs:
                    from server import parse_unit_and_names
                    idx = 1
                    for vch in raw_vchs:
                        vnum = vch.get("voucher_number") or f"VCH-{idx:03d}"
                        vdate = vch.get("date") or "01-08-2026"
                        if len(vdate) == 8 and vdate.isdigit():
                            vdate = f"{vdate[6:8]}-{vdate[4:6]}-{vdate[0:4]}"
                        cr_amount = 0.0
                        deductions = 0.0
                        member_ledger = ""
                        for ent in vch.get("entries", []):
                            amt = ent.get("amount", 0.0)
                            lname = ent.get("ledger_name", "")
                            if amt < 0:
                                cr_amount = abs(amt)
                                member_ledger = lname
                            elif any(k in lname.lower() for k in ["stamp", "reg"]):
                                deductions += abs(amt)
                        if cr_amount > 0:
                            flat_no, clean_name = parse_unit_and_names(member_ledger)
                            taxable = max(0.0, cr_amount - deductions)
                            vouchers.append({
                                "vch_no": vnum,
                                "date": vdate,
                                "type": "Member Receipt",
                                "flat_no": flat_no,
                                "unit": flat_no,
                                "member_name": clean_name,
                                "name": clean_name,
                                "raw_name": member_ledger,
                                "project": project_name,
                                "cr_amount": cr_amount,
                                "deductions": deductions,
                                "taxable_amount": taxable,
                                "classification": "Taxable @ 1% (Affordable Residential)",
                                "badge_type": "taxable-1"
                            })
                            idx += 1
            except Exception as e:
                print(f"[!] Warning reading live XML: {e}")
                
        # If live XML is empty or education mode restriction, fallback to local parsed records
        if not vouchers:
            vouchers = extract_from_local_files()
    else:
        print("[!] Local Tally (Port 9000) not responding. Reading local company database/files...")
        vouchers = extract_from_local_files()

    if not vouchers:
        print("[X] No vouchers found to sync.")
        return False

    print(f"[OK] Prepared {len(vouchers)} vouchers for project '{project_name}'.")
    total_gross = sum(v.get("cr_amount", 0) for v in vouchers)
    total_taxable = sum(v.get("taxable_amount", 0) for v in vouchers)
    print(f"    - Gross Collections: Rs. {total_gross:,.2f}")
    print(f"    - Net Taxable Base:  Rs. {total_taxable:,.2f}")

    # Push to Railway Cloud
    payload = {
        "project": project_name,
        "synced_at": datetime.now().isoformat(),
        "source": "Local Windows PC Tally Agent",
        "count": len(vouchers),
        "vouchers": vouchers
    }

    try:
        url = f"{railway_url.rstrip('/')}/api/vouchers/sync"
        print(f"[*] Transmitting data payload to: {url}...")
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            print("=" * 65)
            print(f" [SUCCESS] {res.get('message')}")
            print(f" Cloud Dashboard updated for project '{project_name}'!")
            print(f" Open your Railway app: {railway_url}")
            print("=" * 65)
            return True
    except Exception as e:
        print(f"[X] Cloud sync failed: {e}")
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://sunbuilders-production.up.railway.app"
    sync_to_railway(target)
