"""
Sun Builders Projects LLP - 1-Click Tally to Railway Cloud Sync Agent
=======================================================================
Extracts 100% authentic vouchers directly from live TallyPrime / Tally.ERP 9 (Port 9000),
sanitizes the Tally XML stream, analyzes member ledger receipts & statutory deductions,
persists locally in data/ and SQLite, and securely transmits everything to Railway Cloud.

Supports Progressive Monthly Sync:
- Sync only next monthly progressive vouchers (e.g. SEP-26, OCT-26) once past vouchers are checked.
- Prevents re-auditing or overwriting verified historical periods.
"""

import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.error
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_RAILWAY_URL = "https://sunbuilders-production.up.railway.app"

PASS_THROUGH_KEYWORDS = [
    r'\bstamp duty\b', r'\bstamp\b', r'\bregistration\b', r'\breg\.?\s*fee\b',
    r'\brefund', r'\bsecurity deposit\b', r'\bmember deposit\b',
    r'\belectric\b', r'\belectricity\b', r'\blight bill\b', r'\bauda\b', r'\baec\b', r'\btorrent\b',
    r'\bpgvcl\b', r'\bgeb\b', r'\bugvcl\b', r'\bdgvcl\b', r'\bpower deposit\b',
    r'\bmaintenance\b', r'\bmaintanance\b', r'\bsociety\b', r'\bsociety deposit\b',
    r'\bsociety maintenance\b', r'\bsinking fund\b'
]

def is_valid_unit_code(unit_str: str) -> bool:
    """Returns True ONLY if unit_str is an authentic real estate block/unit/flat code.
    Rejects person names (Sonal, Hemil, Subhash), banks, deposits, expenses, and words without digits."""
    if not unit_str:
        return False
    u = str(unit_str).strip().upper()
    if u in ("", "—", "-", "N/A", "UNIT N/A", "UNDEFINED", "NONE", "NULL"):
        return False
    if not re.search(r'\d', u):
        return False
    blacklisted = [
        "BANK", "HDFC", "AXIS", "ICICI", "SBI", "CASH", "DEPOSIT", "AUDA", "PGVCL",
        "GEB", "EXPENSE", "PURCHASE", "CHEQUE", "RETURN", "BROKERAGE", "COMMISSION",
        "SOCIETY", "KASAR", "DISCOUNT", "ROUND"
    ]
    if any(b in u for b in blacklisted):
        return False
    patterns = [
        r'^[A-Z]{1,2}[\-_/\s]?\d{1,5}[A-Z]?$',
        r'^(?:SHOP|SH|OFF|OFFICE|PLOT|FLAT|UNIT)[\-_/\s]?\d{1,5}[A-Z]?$',
        r'^\d{1,5}[A-Z]?$'
    ]
    return any(re.match(p, u) for p in patterns)

def is_pass_through_ledger(name: str) -> bool:
    if not name:
        return False
    nl = name.lower()
    return any(re.search(kw, nl) for kw in PASS_THROUGH_KEYWORDS)

def clean_tally_xml(xml_str: str) -> str:
    """
    Sanitizes raw XML exported by Tally:
    1. Removes non-printable control characters (ASCII 0-31, except 9, 10, 13).
    2. Escapes naked ampersands ('&' not part of standard XML entities).
    3. Cleans invalid numeric character references.
    4. Removes namespace prefix colons in tag names.
    """
    s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', xml_str)
    s = re.sub(r'&#(?:0?[0-8]|1[1-2]|1[4-9]|2[0-9]|3[0-1]);', '', s)
    s = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', s)
    s = re.sub(r'<(/?[a-zA-Z0-9_\-]+):([a-zA-Z0-9_\-]+)', r'<\1_\2', s)
    return s

def parse_unit_and_names(ledger_name: str):
    """Splits a Tally ledger name into (flat/unit code, owner name(s)).
    Enforces authentic block/unit codes (A-101, SHOP-118, O-1401).
    Rejects names (Sonal, Hemil, Subhash), banks, and words without digits.
    """
    if not ledger_name:
        return "", ""
    raw = ledger_name.replace('_x000D_\n', ' ').replace('_x000D_', ' ').strip()

    # Pattern 1: Explicit Shop / Office / Plot / Flat prefix: e.g. 'Shop 118 Amit Bhavsar', 'SH-403 Nehal Parikh'
    m_pref = re.match(r'^(SHOP|SH|OFF|OFFICE|PLOT|FLAT|UNIT)\s*[\-_/,\s]?\s*(\d{1,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw, re.IGNORECASE)
    if m_pref:
        pref = m_pref.group(1).upper()
        if pref in ["SH", "SHOP"]:
            unit = f"SHOP-{m_pref.group(2)}"
        elif pref in ["OFF", "OFFICE"]:
            unit = f"OFF-{m_pref.group(2)}"
        elif pref == "PLOT":
            unit = f"PLOT-{m_pref.group(2)}"
        else:
            unit = f"{pref}-{m_pref.group(2)}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m_pref.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern 2: Single or 2-letter Tower/Block + Flat digits: e.g. 'A-101', 'O-1401', 'I/1403', 'K-603'
    # Towers in real estate are 1-2 letters (A, B, C, ... AA, etc.), NOT names like 'Sonal' (5 letters)!
    m = re.match(r'^([A-Za-z]{1,2})\s*[\-_/,\s]\s*(\d{1,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m:
        unit = f"{m.group(1).upper()}-{m.group(2)}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern 3: Block + digits glued without separator: e.g. 'L1102,Sudhanshu Agarwal'
    m2 = re.match(r'^([A-Za-z]{1,2})(\d{2,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m2:
        unit = f"{m2.group(1).upper()}-{m2.group(2)}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m2.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern 4: Fallback comma / semicolon / dash ONLY IF the first part is a valid unit code
    for sep in [',', ';', '-']:
        if sep in raw:
            p0, p1 = raw.split(sep, 1)
            p0, p1 = p0.strip(), p1.strip()
            if is_valid_unit_code(p0):
                return p0, p1 if p1 else "Member"

    return "", raw

def extract_from_live_tally(tally_url="http://localhost:9000", target_company=None, target_month=None, target_year=None):
    import xml.etree.ElementTree as ET
    
    print("=" * 75)
    print("  SUN BUILDERS - TALLY PRIME / ERP 9 LIVE EXTRACTION")
    print(f"  Tally API URL: {tally_url}")
    if target_month:
        print(f"  Target Progressive Month: {target_month}" + (f"-{target_year}" if target_year else ""))
    print("=" * 75)

    if target_company:
        active_company = target_company
        print(f"[+] Targeting Loaded Company: '{active_company}'")
    else:
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

    print("[*] Extracting vouchers via TDL Collection...")

    # 2. Query Vouchers
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

    # Normalize target month for progressive filtering
    m_filter = None
    y_filter = str(target_year).strip() if target_year else None
    if target_month:
        tm = str(target_month).strip().upper()
        month_map = {
            "01":"01", "1":"01", "JAN":"01", "02":"02", "2":"02", "FEB":"02",
            "03":"03", "3":"03", "MAR":"03", "04":"04", "4":"04", "APR":"04",
            "05":"05", "5":"05", "MAY":"05", "06":"06", "6":"06", "JUN":"06",
            "07":"07", "7":"07", "JUL":"07", "08":"08", "8":"08", "AUG":"08",
            "09":"09", "9":"09", "SEP":"09", "10":"10", "OCT":"10",
            "11":"11", "NOV":"11", "12":"12", "DEC":"12"
        }
        m_filter = month_map.get(tm, tm)

    for idx, v in enumerate(vch_elements, 1):
        v_type = v.findtext("VOUCHERTYPENAME", "")
        v_date_raw = v.findtext("DATE", "")
        v_num = v.findtext("VOUCHERNUMBER", "") or f"VCH-{idx:04d}"
        narr = v.findtext("NARRATION", "") or ""

        v_date = v_date_raw
        v_month = ""
        v_year = ""
        if len(v_date_raw) == 8 and v_date_raw.isdigit():
            v_year = v_date_raw[0:4]
            v_month = v_date_raw[4:6]
            v_date = f"{v_date_raw[6:8]}-{v_month}-{v_year}"
        elif "-" in v_date_raw:
            parts = v_date_raw.split("-")
            if len(parts) == 3:
                v_month = parts[1]
                v_year = parts[2] if len(parts[2]) == 4 else parts[0]

        # Apply progressive month filtering if specified
        if m_filter:
            if v_month != m_filter:
                continue
            if y_filter and v_year != y_filter:
                continue

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
                if is_pass_through_ledger(lname):
                    deductions += abs(amt)
                elif not bank_cash:
                    bank_cash = lname

        if cr_amount == 0 and deductions == 0 and not entries:
            continue

        flat_no, member_name = parse_unit_and_names(member_ledger)
        taxable_amt = max(0.0, cr_amount - deductions)

        # Exclude pass-throughs from income
        is_pass_through = is_pass_through_ledger(member_ledger) or is_pass_through_ledger(narr)
        if is_pass_through:
            classification = "Non-GST Excluded (Pass-Through Fees / Deposits)"
            badge_type = "excluded"
            taxable_amt = 0.0
        elif cr_amount == 0 and deductions > 0:
            classification = "Non-GST Excluded (Pass-Through Fees)"
            badge_type = "excluded"
        elif deductions >= cr_amount and cr_amount > 0:
            classification = "Non-GST Excluded (Stamp Duty / Reg Off-set)"
            badge_type = "excluded"
        elif not is_valid_unit_code(flat_no):
            classification = "Excluded - No Valid Unit Code"
            badge_type = "excluded"
            taxable_amt = 0.0
        else:
            classification = "Taxable @ 1% (Affordable Residential)"
            badge_type = "taxable-1"

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

def sync(destination_url=DEFAULT_RAILWAY_URL, target_month=None, target_year=None, progressive=False):
    if progressive and not target_month:
        target_month = "09"
        target_year = target_year or "2026"

    sync_mode = "Progressive Monthly" if (target_month or progressive) else "Full Inception"
    print(f"[*] Starting {sync_mode} Sync...")

    company_name, vouchers = extract_from_live_tally(target_month=target_month, target_year=target_year)
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
                all_cached = data.get("vouchers", [])
                company_name = data.get("project", display_name)
                if target_month:
                    m_norm = f"{int(target_month):02d}" if target_month.isdigit() else target_month
                    vouchers = [v for v in all_cached if f"-{m_norm}-" in v.get("date", "")]
                else:
                    vouchers = all_cached

    if not vouchers:
        print("[X] No vouchers found to sync. Please make sure Tally is open with your company.")
        return False

    print(f"\n[+] Total Authentic Vouchers Ready for Sync: {len(vouchers):,}")
    print(f"    - Loaded Company:   {company_name}")
    print(f"    - Target Project:   {display_name} ({target_code})")
    print(f"    - Sync Type:        {sync_mode} ({target_month or 'ALL'}-{target_year or 'ALL'})")
    total_gross = sum(v.get("cr_amount", 0) for v in vouchers)
    total_taxable = sum(v.get("taxable_amount", 0) for v in vouchers)
    print(f"    - Gross Collections: Rs. {total_gross:,.2f}")
    print(f"    - Net Taxable Base:  Rs. {total_taxable:,.2f}")

    # 1. Save Locally
    local_file = os.path.join(DATA_DIR, f"synced_{display_name.replace(' ', '_').lower()}.json")
    try:
        if (target_month or progressive) and os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            old_list = old_data.get("vouchers", [])
            v_map = {(v.get("vch_no"), v.get("date")): v for v in old_list}
            for v in vouchers:
                v_map[(v.get("vch_no"), v.get("date"))] = v
            merged = list(v_map.values())
            with open(local_file, "w", encoding="utf-8") as f:
                json.dump({
                    "project": display_name,
                    "company_code": target_code,
                    "synced_at": datetime.now().isoformat(),
                    "source": f"Live Tally - {company_name}",
                    "count": len(merged),
                    "vouchers": merged
                }, f, indent=2)
        else:
            with open(local_file, "w", encoding="utf-8") as f:
                json.dump({
                    "project": display_name,
                    "company_code": target_code,
                    "synced_at": datetime.now().isoformat(),
                    "source": f"Live Tally - {company_name}",
                    "count": len(vouchers),
                    "vouchers": vouchers
                }, f, indent=2)
    except Exception as e:
        print("[Local Save Notice]:", e)

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
        "sync_type": "progressive" if (target_month or progressive) else "full",
        "target_period": f"{target_month}-{target_year}" if target_month else "ALL",
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
            print(f"  Mode:                {sync_mode}")
            print(f"  Periods Ingested:    {res.get('periods', [])}")
            print(f"  Live Dashboard:      {destination_url}")
            print("=" * 75)
            return True
    except Exception as e:
        print(f"[!] Warning: Cloud transmission failed ({e}). Data saved locally at {local_file}.")
        return False

def interactive_menu():
    print("=" * 75)
    print("  SUN BUILDERS - TALLY TO RAILWAY SYNC AGENT (PORT 9000)")
    print("=" * 75)
    print("  [1] Progressive Sync - Next Monthly Vouchers Only (SEP-26) [RECOMMENDED]")
    print("  [2] Full Inception Sync - All Historical Vouchers (Inception to Date)")
    print("  [3] Custom Month Sync (e.g. Enter 09-2026 or 10-2026)")
    print("=" * 75)

    try:
        choice = input("Enter choice [1/2/3] (Default: 1): ").strip()
    except Exception:
        choice = "1"

    if choice == "2":
        return None, None, False
    elif choice == "3":
        try:
            m_input = input("Enter Month-Year (MM-YYYY or MON-YY, e.g. 09-2026): ").strip()
            if "-" in m_input:
                parts = m_input.split("-")
                return parts[0], parts[1], True
            return m_input, "2026", True
        except Exception:
            return "09", "2026", True
    else:
        # Default is Progressive Month (SEP-26)
        return "09", "2026", True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sun Builders Tally Sync Agent")
    parser.add_argument("url", nargs="?", default=DEFAULT_RAILWAY_URL, help="Railway Cloud Destination URL")
    parser.add_argument("--progressive", action="store_true", help="Sync next monthly progressive vouchers only")
    parser.add_argument("--month", type=str, default=None, help="Target month (e.g. 09, SEP, 09-2026)")
    parser.add_argument("--year", type=str, default="2026", help="Target year (default: 2026)")
    parser.add_argument("--all", action="store_true", help="Sync all historical vouchers from inception")

    args = parser.parse_args()

    t_month = args.month
    t_year = args.year
    is_prog = args.progressive

    # If run in terminal without arguments, show friendly interactive menu
    if sys.stdin.isatty() and not args.all and not args.month and not args.progressive and len(sys.argv) <= 1:
        t_month, t_year, is_prog = interactive_menu()

    if t_month and "-" in t_month:
        p = t_month.split("-")
        t_month = p[0]
        t_year = p[1]

    sync(destination_url=args.url, target_month=t_month, target_year=t_year, progressive=is_prog or bool(t_month))
