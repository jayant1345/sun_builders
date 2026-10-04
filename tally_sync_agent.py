"""
Sun Builders Projects LLP - 1-Click Tally to Railway Cloud Sync Agent
=======================================================================
Extracts 100% authentic vouchers directly from live TallyPrime / Tally.ERP 9 (Port 9000),
sanitizes the Tally XML stream, analyzes member ledger receipts & statutory deductions,
persists locally in data/ and SQLite, and securely transmits everything to Railway Cloud.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_RAILWAY_URL = "https://sunbuilders-production.up.railway.app"

def clean_tally_xml(xml_str: str) -> str:
    """
    Sanitizes raw XML exported by Tally:
    1. Removes non-printable control characters (ASCII 0-31, except 9, 10, 13).
    2. Escapes naked ampersands ('&' not part of standard XML entities).
    3. Cleans invalid numeric character references.
    """
    s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', xml_str)
    s = re.sub(r'&#(?:0?[0-8]|1[1-2]|1[4-9]|2[0-9]|3[0-1]);', '', s)
    s = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', s)
    return s

def parse_unit_and_names(ledger_name: str):
    if not ledger_name:
        return "", ""
    m = re.match(r"^([A-Za-z0-9\/\-\.]+)(?:,|\s\-\s|\s-\s|\s-\s*|;|\s)(.*)$", ledger_name.strip())
    if m:
        flat = m.group(1).strip()
        name = m.group(2).strip()
        return flat, name
    return "", ledger_name.strip()

def extract_from_live_tally(tally_url="http://localhost:9000"):
    import xml.etree.ElementTree as ET
    
    print("=" * 75)
    print("  SUN BUILDERS - TALLY PRIME / ERP 9 LIVE EXTRACTION")
    print(f"  Tally API URL: {tally_url}")
    print("=" * 75)

    # 1. Discover Active Company
    comp_req = """<ENVELOPE>
        <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>List of Companies</ID></HEADER>
        <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
    </ENVELOPE>"""

    try:
        req = urllib.request.Request(tally_url, data=comp_req.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_res = clean_tally_xml(resp.read().decode('utf-8', errors='ignore'))
            root = ET.fromstring(xml_res)
            comps = [elem.text for elem in root.findall(".//COMPANYNAME") if elem.text]
            if not comps:
                comps = [elem.text for elem in root.findall(".//NAME") if elem.text and not elem.text.startswith("$$")]
    except Exception as e:
        print(f"[!] Could not connect to Tally on {tally_url}: {e}")
        return None, []

    if not comps:
        print("[!] Tally is online, but no Company is currently open. Please open your company in Tally.")
        return None, []

    active_company = comps[0]
    print(f"[+] Loaded Company identified: '{active_company}'")
    print("[*] Extracting all historical vouchers via TDL Collection...")

    # 2. Query All Vouchers
    vch_req = f"""<ENVELOPE>
        <HEADER>
            <VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Collection</TYPE>
            <ID>CustomAllVouchers</ID>
        </HEADER>
        <BODY>
            <DESC>
                <STATICVARIABLES>
                    <SVCURRENTCOMPANY>{active_company}</SVCURRENTCOMPANY>
                    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                </STATICVARIABLES>
                <TDL>
                    <TDLMESSAGE>
                        <COLLECTION NAME="CustomAllVouchers" ISINITIALIZE="Yes">
                            <TYPE>Voucher</TYPE>
                            <FETCH>DATE, VOUCHERTYPENAME, VOUCHERNUMBER, NARRATION, ALLLEDGERENTRIES.LIST</FETCH>
                        </COLLECTION>
                    </TDLMESSAGE>
                </TDL>
            </DESC>
        </BODY>
    </ENVELOPE>"""

    try:
        req2 = urllib.request.Request(tally_url, data=vch_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'})
        with urllib.request.urlopen(req2, timeout=180) as resp2:
            raw_xml = resp2.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[!] Tally voucher extraction query failed: {e}")
        return active_company, []

    print(f"[+] Downloaded {len(raw_xml):,} bytes from Tally. Parsing...")
    cleaned_xml = clean_tally_xml(raw_xml)
    root2 = ET.fromstring(cleaned_xml)
    vch_elements = root2.findall(".//VOUCHER")
    print(f"[+] Parsed {len(vch_elements):,} total raw vouchers from Tally.")

    parsed_vouchers = []
    seen_keys = set()

    for idx, v in enumerate(vch_elements, 1):
        v_type = v.findtext("VOUCHERTYPENAME", "")
        v_date_raw = v.findtext("DATE", "")
        v_num = v.findtext("VOUCHERNUMBER", "") or f"VCH-{idx:04d}"
        narr = v.findtext("NARRATION", "") or ""

        v_date = v_date_raw
        if len(v_date_raw) == 8 and v_date_raw.isdigit():
            v_date = f"{v_date_raw[6:8]}-{v_date_raw[4:6]}-{v_date_raw[0:4]}"

        cr_amount = 0.0
        deductions = 0.0
        member_ledger = ""
        bank_cash = ""
        entries = []

        for le in v.findall(".//ALLLEDGERENTRIES.LIST"):
            lname = le.findtext("LEDGERNAME", "") or ""
            amt_str = le.findtext("AMOUNT", "0")
            try:
                amt = float(amt_str)
            except ValueError:
                amt = 0.0
            entries.append({"ledger_name": lname, "amount": amt})

            if amt < 0:
                cr_amount += abs(amt)
                if not member_ledger:
                    member_ledger = lname
            elif amt > 0:
                if any(k in lname.lower() for k in ["stamp", "reg", "maintenance", "electric", "auda", "aec"]):
                    deductions += abs(amt)
                elif not bank_cash:
                    bank_cash = lname

        if cr_amount == 0 and deductions == 0 and not entries:
            continue

        flat_no, member_name = parse_unit_and_names(member_ledger)
        taxable_amt = max(0.0, cr_amount - deductions)

        classification = "Taxable @ 1% (Affordable Residential)"
        badge_type = "taxable-1"
        if cr_amount == 0 and deductions > 0:
            classification = "Non-GST Excluded (Pass-Through Fees)"
            badge_type = "excluded"
        elif deductions >= cr_amount and cr_amount > 0:
            classification = "Non-GST Excluded (Stamp Duty / Reg Off-set)"
            badge_type = "excluded"

        vkey = (v_num, v_date, member_ledger, cr_amount)
        if vkey in seen_keys:
            continue
        seen_keys.add(vkey)

        parsed_vouchers.append({
            "vch_no": v_num,
            "date": v_date,
            "type": v_type,
            "flat_no": flat_no,
            "unit": flat_no,
            "member_name": member_name,
            "name": member_name,
            "raw_name": member_ledger,
            "project": active_company,
            "cr_amount": cr_amount,
            "deductions": deductions,
            "taxable_amount": taxable_amt,
            "bank_cash": bank_cash,
            "narration": narr,
            "classification": classification,
            "badge_type": badge_type
        })

    def date_sort_key(x):
        try:
            return datetime.strptime(x["date"], "%d-%m-%Y")
        except Exception:
            return datetime.min

    parsed_vouchers.sort(key=date_sort_key, reverse=True)
    return active_company, parsed_vouchers

def resolve_company_code(company_name: str):
    c_upper = (company_name or "").upper()
    if "PARK WEST" in c_upper or "010011" in c_upper:
        return "010011", "Sun Park West"
    if "ATMOSPHERE" in c_upper or "010000" in c_upper or "010012" in c_upper:
        return "010000", "Sun Atmosphere"
    if "SILVER SPRING" in c_upper or "010002" in c_upper:
        return "010002", "Sun Silver Spring"
    if "GRAVITAS" in c_upper or "010009" in c_upper:
        return "010009", "Sun Gravitas"
    if "LEKHAMBHA" in c_upper or "010015" in c_upper:
        return "010015", "Lekhambha"
    return "010010", "Sun Footprint"

def sync(destination_url=DEFAULT_RAILWAY_URL):
    company_name, vouchers = extract_from_live_tally()
    target_code, display_name = resolve_company_code(company_name)

    if not vouchers:
        # Fallback to existing saved json if live tally wasn't open
        cached_file = os.path.join(DATA_DIR, f"synced_{display_name.replace(' ', '_').lower()}.json")
        if not os.path.exists(cached_file):
            cached_file = os.path.join(DATA_DIR, "synced_sun_footprint.json")
        if os.path.exists(cached_file):
            print(f"[*] Live Tally not running; loading cached authentic dataset: {cached_file}")
            with open(cached_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                vouchers = data.get("vouchers", [])
                company_name = data.get("project", display_name)

    if not vouchers:
        print("[X] No vouchers could be extracted. Please make sure Tally is open with your company.")
        return False

    print(f"\n[+] Total Authentic Vouchers Ready for Sync: {len(vouchers):,}")
    print(f"    - Loaded Company:   {company_name}")
    print(f"    - Target Project:   {display_name} ({target_code})")
    total_gross = sum(v.get("cr_amount", 0) for v in vouchers)
    total_taxable = sum(v.get("taxable_amount", 0) for v in vouchers)
    print(f"    - Gross Collections: Rs. {total_gross:,.2f}")
    print(f"    - Net Taxable Base:  Rs. {total_taxable:,.2f}")

    # 1. Save Locally
    local_file = os.path.join(DATA_DIR, f"synced_{display_name.replace(' ', '_').lower()}.json")
    with open(local_file, "w", encoding="utf-8") as f:
        json.dump({
            "project": display_name,
            "company_code": target_code,
            "synced_at": datetime.now().isoformat(),
            "source": f"Live Tally - {company_name}",
            "count": len(vouchers),
            "vouchers": vouchers
        }, f, indent=2)

    try:
        from core.db import db
        db.save_vouchers(target_code, vouchers)
    except Exception as dbe:
        print("[DB Notice]:", dbe)

    # 2. Transmit to Railway Cloud
    target_endpoint = f"{destination_url.rstrip('/')}/api/vouchers/sync"
    print(f"\n[*] Transmitting payload to Railway Cloud: {target_endpoint}...")

    payload = {
        "project": display_name,
        "company_code": target_code,
        "synced_at": datetime.now().isoformat(),
        "source": "1-Click Tally Sync Agent",
        "count": len(vouchers),
        "vouchers": vouchers
    }

    try:
        req = urllib.request.Request(
            target_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            print("=" * 75)
            print(f"  [SUCCESS] {res.get('message', 'Cloud database synchronized!')}")
            print(f"  Periods Synchronized: {res.get('periods', [])}")
            print(f"  Live Dashboard: {destination_url}")
            print("=" * 75)
            return True
    except Exception as e:
        print(f"[!] Warning: Cloud transmission failed ({e}). Data saved locally at {local_file}.")
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RAILWAY_URL
    sync(target)
