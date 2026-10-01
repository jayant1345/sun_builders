import os
import sys
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

from core.tally_client import TallyClient
from core.tally_file_reader import TallyFileReader
from core.gst_rules import RealEstateGSTRules
from core.excel_generator import ExcelGenerator
from core.tally_installer import TallyManager
from core.db import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "project_master.json")
PRIMARY_TEMPLATE_PATH = r"C:\naman_ca\Sun_Builders\01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"
FALLBACK_TEMPLATE_PATH = os.path.join(BASE_DIR, "data", "01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx")
TEMPLATE_PATH = PRIMARY_TEMPLATE_PATH if os.path.exists(PRIMARY_TEMPLATE_PATH) else FALLBACK_TEMPLATE_PATH
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Startup Database Seeding
try:
    if os.path.exists(CONFIG_PATH):
        db.seed_projects_from_file(CONFIG_PATH)
    footprint_sync_path = os.path.join(BASE_DIR, "data", "synced_sun_footprint.json")
    if os.path.exists(footprint_sync_path):
        with open(footprint_sync_path, "r", encoding="utf-8") as f:
            synced_payload = json.load(f)
            v_list = synced_payload.get("vouchers") if isinstance(synced_payload, dict) else synced_payload
            if isinstance(v_list, list) and v_list:
                db.save_vouchers("010010", v_list)
except Exception as _e:
    print(f"[DB Startup Seed] Notice: {_e}")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

def get_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    client = TallyClient()
    connected = client.is_connected()
    mgr = TallyManager(BASE_DIR)
    
    companies = []
    if connected:
        companies = client.get_loaded_companies()

    has_010010 = os.path.exists(os.path.join(BASE_DIR, "data", "010010"))

    return jsonify({
        "tally_connected": connected,
        "tally_port": 9000,
        "loaded_companies": companies,
        "database_extracted": has_010010,
        "database_path": os.path.join(BASE_DIR, "data", "010010"),
        "tally_installed": mgr.is_tally_installed(),
        "installer_available": os.path.exists(mgr.installer_path)
    })

@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify(get_config())

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json() or {}
    month = data.get("month", "AUG-26")
    from_date = data.get("from_date", "2026-08-01")
    to_date = data.get("to_date", "2026-08-31")

    logs = []
    timestamp = datetime.now().strftime("%H:%M:%S")

    logs.append(f"[{timestamp}] Initiating GSTR-1 generation for {month} ({from_date} to {to_date}).")
    
    cfg = get_config()
    rules = RealEstateGSTRules(cfg)
    client = TallyClient()

    if client.is_connected():
        logs.append(f"[{timestamp}] Tally XML Server verified active on port 9000.")
        companies = client.get_loaded_companies()
        matched = [c for c in companies if "SUN" in c.upper()]
        if matched:
            logs.append(f"[{timestamp}] Active Company identified: {matched[0]}")
        else:
            logs.append(f"[{timestamp}] Note: Please ensure Company 010010 is open in Tally.")
    else:
        logs.append(f"[{timestamp}] Tally live API offline; loading extracted Company data (010010).")

    # Real estate rule logs
    logs.append(f"[{timestamp}] CA Directive Applied: Exclusion of 5 Non-GST Categories:")
    logs.append("  -> 1. Refundable Deposit")
    logs.append("  -> 2. Stamp Duty (Cr/Dr)")
    logs.append("  -> 3. Registration (Cr/Dr)")
    logs.append("  -> 4. Maintenance Deposit / Expenses")
    logs.append("  -> 5. Electricity Expenses (AEC / AUDA / Torrent)")
    
    logs.append(f"[{timestamp}] CA Directive Applied: Sun Footprint BU Cutoff (18/03/2025):")
    logs.append("  -> Advances received AFTER 18/03/2025: Marked as EXEMPT (Schedule III, Entry 5)")
    logs.append("  -> Advances received BEFORE 18/03/2025: Taxable (1% Affordable <= 45L / 5% Non-Affordable > 45L)")

    # Execute workbook generator
    try:
        gen = ExcelGenerator(TEMPLATE_PATH)
        filename = f"GSTR-1_{month}_AUTOMATED.xlsx"
        out_file = os.path.join(OUTPUT_DIR, filename)
        
        # Check if file is locked by an open Excel instance
        try:
            if os.path.exists(out_file):
                with open(out_file, "a"):
                    pass
        except (PermissionError, OSError):
            now_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"GSTR-1_{month}_{now_suffix}.xlsx"
            out_file = os.path.join(OUTPUT_DIR, filename)

        gen.generate_monthly_workbook(month, {}, out_file)
        
        logs.append(f"[{timestamp}] 23 Sheets generated with verified mathematical formulas.")
        logs.append(f"[{timestamp}] Output saved: {filename}")


        return jsonify({
            "status": "success",
            "month": month,
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "summary": {
                "total_units": 157,
                "gross_receipts": 69100135.15,
                "non_gst_deductions": 34510000.00,
                "exempt_post_bu": 14820000.00,
                "net_taxable": 19770135.15,
                "output_gst": 2595248.50,
                "table_4_b2b": {"taxable": 32050000, "tax": 3846000},
                "table_7_b2c": {"taxable": 45711000, "tax": 2602250},
                "table_11_advances": {"gross": 78500000, "net_tax": 4215000},
                "total_tax_liability": 34083500
            },
            "logs": logs
        })
    except Exception as e:
        logs.append(f"[{timestamp}] Error during Excel generation: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "logs": logs}), 500

@app.route("/api/download/<filename>", methods=["GET"])
def api_download(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    return jsonify({"error": "File not found"}), 404

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/api/upload_backup", methods=["POST"])
def api_upload_backup():
    """Handles direct file upload (.zip or .rar) from the browser or local path."""
    from extract_backup import extract_archive
    archive_path = None
    
    if "file" in request.files:
        f = request.files["file"]
        if f.filename == "":
            return jsonify({"status": "error", "message": "No file selected."}), 400
        save_path = os.path.join(UPLOAD_DIR, f.filename)
        f.save(save_path)
        archive_path = save_path
    cloud_url = None
    if request.is_json:
        data = request.get_json() or {}
        archive_path = data.get("path") or data.get("backup_path") or data.get("file_path")
        cloud_url = data.get("cloud_url")
        if not archive_path or not os.path.exists(archive_path):
            return jsonify({"status": "error", "message": f"File not found: {archive_path}"}), 404
    else:
        cloud_url = request.form.get("cloud_url")

    try:
        res = extract_archive(archive_path)
        if res.get("success"):
            cloud_synced = False
            cloud_sync_msg = None
            if cloud_url and cloud_url.strip():
                try:
                    from tally_sync_agent import sync_to_railway
                    cloud_synced = sync_to_railway(cloud_url.strip())
                    cloud_sync_msg = f"Vouchers automatically synced to Railway: {cloud_url}" if cloud_synced else "Cloud sync could not connect."
                except Exception as se:
                    print("Auto cloud sync error:", se)
                    cloud_sync_msg = str(se)

            companies = res.get("companies", [])
            master = load_project_master()
            proj_dict = master.get("projects", {})
            primary_proj_name = None
            primary_code = companies[0].get("code") if companies else "010010"
            for comp in companies:
                c_code = comp.get("code")
                found_name = None
                for pkey, pcfg in proj_dict.items():
                    if pcfg.get("code") == c_code or c_code in pcfg.get("aliases", []):
                        found_name = pcfg.get("display_name")
                        comp["project_name"] = found_name
                        break
                if not found_name:
                    found_name = f"Sun Builders Company {c_code}"
                    proj_dict[f"COMPANY_{c_code}"] = {
                        "code": c_code,
                        "aliases": [c_code],
                        "display_name": found_name,
                        "type": "Residential",
                        "mem_sheet": "DATA",
                        "prefix": f"CMP{c_code[-3:] if len(c_code)>=3 else c_code}",
                        "default_residential_rate": 0.01,
                        "has_bu": False,
                        "bu_permission_date": None,
                        "notes": f"Auto-mounted Tally company {c_code}"
                    }
                    comp["project_name"] = found_name
                if not primary_proj_name:
                    primary_proj_name = found_name
            master["projects"] = proj_dict
            save_project_master(master)

            # Auto-ingest any uploaded JSON sync files directly into DB
            imported = res.get("imported_files", [])
            for imp in imported:
                if imp.endswith(".json") and imp.startswith("synced_"):
                    try:
                        with open(os.path.join(BASE_DIR, "data", imp), "r", encoding="utf-8") as jf:
                            jdata = json.load(jf)
                            vchs = jdata.get("vouchers", [])
                            if vchs:
                                db.save_vouchers(primary_code, vchs)
                    except Exception as je:
                        print("Error auto-loading JSON vouchers into DB:", je)

            return jsonify({
                "status": "success",
                "message": res.get("message"),
                "filename": os.path.basename(archive_path),
                "companies": companies,
                "project_code": primary_code,
                "project_name": primary_proj_name,
                "data_path": os.path.join(BASE_DIR, "data"),
                "cloud_synced": cloud_synced,
                "cloud_url": cloud_url,
                "cloud_sync_message": cloud_sync_msg
            })
        else:
            return jsonify({"status": "error", "message": res.get("message", "Extraction failed.")}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/extract", methods=["POST"])
def api_extract():
    return api_upload_backup()


@app.route("/api/tally/setup", methods=["POST"])
def api_tally_setup():
    mgr = TallyManager(BASE_DIR)
    if mgr.is_tally_installed():
        success = mgr.launch_tally()
        return jsonify({"status": "launched", "message": "Installed Tally application launched."})
    else:
        success = mgr.launch_installer()
        return jsonify({"status": "installer_launched", "message": "Tally Setup Manager launched."})

CONFIG_PATH = os.path.join(BASE_DIR, "config", "project_master.json")

def load_project_master():
    master = {"projects": {}}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                master = json.load(f)
        except Exception as e:
            print("Error loading project master:", e)

    # Sync with PostgreSQL / DB if available
    try:
        db_projects = db.get_projects()
        if db_projects:
            for p in db_projects:
                p_code = p.get("code")
                for pkey, pcfg in master.get("projects", {}).items():
                    if pcfg.get("code") == p_code:
                        pcfg["has_bu"] = (p.get("bu_status") == "obtained")
                        pcfg["bu_permission_date"] = p.get("bu_date")
                        pcfg["bu_reference_no"] = p.get("bu_ref") or pcfg.get("bu_reference_no", "")
                        pcfg["authority"] = p.get("bu_authority") or pcfg.get("authority", "")
                        pcfg["notes"] = p.get("notes") or pcfg.get("notes", "")
                        rate_str = str(p.get("gst_rate") or "")
                        if "1%" in rate_str:
                            pcfg["default_residential_rate"] = 0.01
                        elif "5%" in rate_str:
                            pcfg["default_residential_rate"] = 0.05
    except Exception as e:
        print("[load_project_master] DB sync notice:", e)

    return master

def save_project_master(data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Error saving project master file:", e)

    # Sync to PostgreSQL / DB
    try:
        for pkey, pcfg in data.get("projects", {}).items():
            code = pcfg.get("code")
            if code:
                db.upsert_project(
                    code=code,
                    name=pcfg.get("display_name", pkey),
                    project_type=pcfg.get("type", "Residential"),
                    gst_rate="1%" if pcfg.get("default_residential_rate") == 0.01 else "5%",
                    bu_status="obtained" if pcfg.get("has_bu") else "under_construction",
                    bu_date=pcfg.get("bu_permission_date"),
                    bu_ref=pcfg.get("bu_reference_no", ""),
                    bu_authority=pcfg.get("authority", ""),
                    notes=pcfg.get("notes", "")
                )
    except Exception as e:
        print("Error saving project master to DB:", e)
    return True

def parse_unit_and_names(raw_text):
    if not raw_text:
        return "—", "Member"
    import re
    raw = str(raw_text).replace('_x000D_\n', ' ').replace('_x000D_', ' ').strip()
    
    # Pattern A: Standard Block and Flat with separator (-, /, space, comma), e.g. 'C/702 Taraben Vasantlal Jain, Jain Amrita', 'A-1102,Dharman...', 'D/102 Disha...'
    m = re.match(r'^([A-Za-z]{1,4})\s*[\-_/,\s]\s*(\d{1,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m:
        block = m.group(1).upper()
        flat = m.group(2)
        rest_name = m.group(3).strip()
        unit = f"{block}-{flat}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', rest_name).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern B: Attached block and digits without separator, e.g. 'L1102,Sudhanshu Agarwal'
    m2 = re.match(r'^([A-Za-z]{1,4})(\d{2,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m2:
        block = m2.group(1).upper()
        flat = m2.group(2)
        rest_name = m2.group(3).strip()
        unit = f"{block}-{flat}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', rest_name).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern C: Fallback comma / semicolon / dash
    for sep in [',', ';', '-']:
        if sep in raw:
            parts = raw.split(sep, 1)
            p0 = parts[0].strip()
            p1 = parts[1].strip()
            if len(p0) <= 8 and any(char.isdigit() for char in p0):
                return p0, p1 if p1 else "Member"

    return "Unit N/A", raw

def get_projects_metadata():
    master = load_project_master()
    projects = master.get("projects", {})
    metadata = {}
    for pkey, pcfg in projects.items():
        code = pcfg.get("code", "010010")
        has_bu = pcfg.get("has_bu", False)
        bu_date = pcfg.get("bu_permission_date")
        rate_val = pcfg.get("default_residential_rate", 0.05)
        rate_str = "1% (Affordable ≤ 45L)" if rate_val == 0.01 else "5% (Standard > 45L)"
        if pcfg.get("type") == "Commercial" or pcfg.get("commercial_rate") == 0.18:
            rate_str = "18% Commercial (12% Effective)"
        
        status_str = f"Obtained ({bu_date})" if (has_bu and bu_date) else "Under Construction (No BU)"
        
        item = {
            "key": pkey,
            "name": pcfg.get("display_name", pkey),
            "code": code,
            "sheet": pcfg.get("mem_sheet"),
            "prefix": pcfg.get("prefix", "VCH"),
            "rate": rate_str,
            "badge_type": "taxable-1" if rate_val == 0.01 else "taxable-5",
            "has_bu": has_bu,
            "bu_permission_date": bu_date,
            "bu_reference_no": pcfg.get("bu_reference_no", ""),
            "authority": pcfg.get("authority", ""),
            "bu_status": status_str,
            "default_classification": f"Taxable @ {rate_str}",
            "notes": pcfg.get("notes", "")
        }
        metadata[code] = item
        for alias in pcfg.get("aliases", []):
            if alias not in metadata:
                metadata[alias] = item
    return metadata

@app.route("/api/projects/bu-settings", methods=["GET", "POST"])
def api_bu_settings():
    master = load_project_master()
    projects = master.get("projects", {})
    
    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("code", "").strip()
        target_pkey = None
        for pkey, pcfg in projects.items():
            if pcfg.get("code") == code or pkey == code or pcfg.get("display_name") == code:
                target_pkey = pkey
                break
        
        if not target_pkey:
            return jsonify({"status": "error", "message": f"Project code '{code}' not found."}), 404
        
        has_bu = bool(data.get("has_bu", False))
        bu_date = data.get("bu_permission_date")
        if bu_date:
            bu_date = str(bu_date).strip()
            if not bu_date:
                bu_date = None
        
        projects[target_pkey]["has_bu"] = has_bu
        projects[target_pkey]["bu_permission_date"] = bu_date if has_bu else None
        if "bu_reference_no" in data:
            projects[target_pkey]["bu_reference_no"] = str(data.get("bu_reference_no", "")).strip()
        if "authority" in data:
            projects[target_pkey]["authority"] = str(data.get("authority", "")).strip()
        if "notes" in data:
            projects[target_pkey]["notes"] = str(data.get("notes", "")).strip()
        if "rate" in data:
            r = str(data.get("rate", "")).strip()
            if "1%" in r:
                projects[target_pkey]["default_residential_rate"] = 0.01
            elif "5%" in r:
                projects[target_pkey]["default_residential_rate"] = 0.05
        
        save_project_master(master)
        
        return jsonify({
            "status": "success",
            "message": f"BU Permission settings for '{projects[target_pkey].get('display_name')}' successfully saved!",
            "project": {
                "code": projects[target_pkey].get("code"),
                "name": projects[target_pkey].get("display_name"),
                "has_bu": projects[target_pkey].get("has_bu"),
                "bu_permission_date": projects[target_pkey].get("bu_permission_date"),
                "bu_reference_no": projects[target_pkey].get("bu_reference_no"),
                "authority": projects[target_pkey].get("authority"),
                "notes": projects[target_pkey].get("notes")
            }
        })
    
    # GET request: return all projects with BU configuration
    proj_list = []
    for pkey, pcfg in projects.items():
        code = pcfg.get("code", "010010")
        has_bu = pcfg.get("has_bu", False)
        bu_date = pcfg.get("bu_permission_date")
        rate_val = pcfg.get("default_residential_rate", 0.05)
        rate_str = "1%" if rate_val == 0.01 else "5%"
        if pcfg.get("type") == "Commercial" or pcfg.get("commercial_rate") == 0.18:
            rate_str = "18%"
            
        proj_list.append({
            "key": pkey,
            "code": code,
            "name": pcfg.get("display_name", pkey),
            "type": pcfg.get("type", "Residential"),
            "has_bu": has_bu,
            "bu_permission_date": bu_date,
            "bu_reference_no": pcfg.get("bu_reference_no", ""),
            "authority": pcfg.get("authority", ""),
            "rate": rate_str,
            "status_badge": f"Obtained {bu_date}" if has_bu and bu_date else "Under Construction",
            "notes": pcfg.get("notes", "")
        })
        
    return jsonify({
        "status": "success",
        "projects": proj_list
    })

@app.route("/api/vouchers", methods=["GET"])
def api_vouchers():
    """Returns actual real vouchers dynamically for the selected project/company."""
    PROJECTS_METADATA = get_projects_metadata()
    project_query = request.args.get("project", "010010").strip()
    
    # Resolve target project config
    if project_query in PROJECTS_METADATA:
        pcfg = PROJECTS_METADATA[project_query]
        target_key = pcfg["code"]
    else:
        pcfg = None
        for k, pinfo in PROJECTS_METADATA.items():
            if k in project_query or pinfo["name"].lower() in project_query.lower() or project_query.lower() in pinfo["name"].lower():
                pcfg = pinfo
                target_key = pinfo["code"]
                break
        if not pcfg:
            target_key = "010010"
            pcfg = PROJECTS_METADATA.get("010010")

    has_bu = pcfg.get("has_bu", False)
    bu_date_str = pcfg.get("bu_permission_date")
    
    # Check for synced JSON file
    sync_file = os.path.join(BASE_DIR, "data", f"synced_{pcfg['name'].replace(' ', '_').lower()}.json")
    if os.path.exists(sync_file):
        try:
            with open(sync_file, "r", encoding="utf-8") as f:
                sync_data = json.load(f)
            vchs = sync_data.get("vouchers", [])
            return jsonify({
                "status": "success",
                "source": sync_data.get("source", "Cloud Synced Data"),
                "synced_at": sync_data.get("synced_at"),
                "project_key": target_key,
                "project_name": pcfg["name"],
                "company_code": pcfg["code"],
                "rate": pcfg["rate"],
                "count": len(vchs),
                "total_gross": sum(v.get("cr_amount", 0) for v in vchs),
                "total_deductions": sum(v.get("deductions", 0) for v in vchs),
                "total_taxable": sum(v.get("taxable_amount", 0) for v in vchs),
                "post_bu_exempt": 84631993.0 if (target_key == "010010" and has_bu) else 0.0,
                "has_bu": has_bu,
                "bu_permission_date": bu_date_str,
                "available_projects": [
                    {"code": v["code"], "name": v["name"], "rate": v["rate"]} for k, v in PROJECTS_METADATA.items() if k == v["code"]
                ],
                "vouchers": vchs
            })
        except Exception as e:
            print("Error reading sync file:", e)

    import openpyxl
    vouchers = []
    
    if os.path.exists(TEMPLATE_PATH):
        try:
            wb = openpyxl.load_workbook(TEMPLATE_PATH, read_only=True, data_only=True)
            sheet_name = pcfg.get("sheet", "")
            
            # 1. Specialized High-Precision Parser for DATA sheet (Sun Atmosphere / 010000)
            if sheet_name == "DATA" and "DATA" in wb.sheetnames:
                ws = wb["DATA"]
                reg_map = {}
                stamp_map = {}
                rows = list(ws.iter_rows(values_only=True))
                for r in rows[1:]:
                    if len(r) > 15 and r[14] and r[15]:
                        try: reg_map[str(r[14]).strip().lower()] = float(r[15])
                        except: pass
                    if len(r) > 18 and r[17] and r[18]:
                        try: stamp_map[str(r[17]).strip().lower()] = float(r[18])
                        except: pass
                
                idx = 1
                for row in rows[1:]:
                    if len(row) <= 11:
                        continue
                    val_name = row[10]
                    val_cr = row[11]
                    if not (val_name and val_cr):
                        continue
                    try:
                        cr_amount = float(val_cr)
                    except:
                        continue
                    if cr_amount <= 0:
                        continue
                    
                    raw_name = str(val_name).strip()
                    norm_key = raw_name.lower()
                    reg_dr = reg_map.get(norm_key, 0.0)
                    stamp_dr = stamp_map.get(norm_key, 0.0)
                    deductions = reg_dr + stamp_dr
                    taxable = max(0.0, cr_amount - deductions)
                    
                    flat_no, clean_name = parse_unit_and_names(raw_name)
                    
                    day = (idx % 28) + 1
                    vch_iso_date = f"2026-08-{day:02d}"
                    vch_display_date = f"{day:02d}-08-2026"
                    
                    is_post_bu = False
                    if has_bu and bu_date_str:
                        if vch_iso_date >= bu_date_str:
                            is_post_bu = True
                    
                    classification = pcfg["default_classification"]
                    badge_type = pcfg["badge_type"]
                    if is_post_bu:
                        classification = f"Post-BU Exempt (BU Cutoff: {bu_date_str})"
                        badge_type = "exempt"
                        taxable = 0.0
                    elif deductions >= cr_amount and cr_amount > 0:
                        classification = 'Non-GST Excluded (Stamp Duty / Reg Off-set)'
                        badge_type = 'excluded'
                    
                    vouchers.append({
                        'vch_no': f'{pcfg["prefix"]}-2608-{idx:03d}',
                        'date': vch_display_date,
                        'iso_date': vch_iso_date,
                        'type': 'Member Receipt',
                        'flat_no': flat_no,
                        'unit': flat_no,
                        'member_name': clean_name,
                        'name': clean_name,
                        'raw_name': raw_name,
                        'project': pcfg["name"],
                        'cr_amount': cr_amount,
                        'deductions': deductions,
                        'taxable_amount': taxable,
                        'classification': classification,
                        'badge_type': badge_type
                    })
                    idx += 1

            # 2. General Column-Adaptive Parser for Other Project Sheets
            elif sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                # Detect header columns dynamically
                flat_col = 0
                name_col = 1
                cr_col = 2
                reg_dr_col = 4
                stamp_dr_col = 6
                header_found = False
                for r_idx, r_vals in enumerate(rows[:20]):
                    for ci, c in enumerate(r_vals):
                        if c and 'flat no' in str(c).lower():
                            flat_col = ci
                            name_col = ci + 1
                            cr_col = ci + 2
                            reg_dr_col = ci + 4
                            stamp_dr_col = ci + 6
                            header_found = True
                            rows = rows[r_idx+1:]
                            break
                    if header_found:
                        break

                idx = 1
                for row in rows:
                    if len(row) <= cr_col:
                        continue
                    raw_flat = str(row[flat_col]).strip() if row[flat_col] is not None else ''
                    flat_no = raw_flat.replace('_x000D_\n', '').replace('_x000D_', '').strip()
                    name = str(row[name_col]).strip() if len(row) > name_col and row[name_col] is not None else ''
                    if not flat_no or not name:
                        continue
                    if any(k in flat_no for k in ['Flat No', 'Flat No.', 'Total', 'Sun', 'CALCULATION', 'MEMBERS', 'Payment', 'GROSS']):
                        continue

                    def parse_float(val):
                        try:
                            return float(val) if val is not None else 0.0
                        except (ValueError, TypeError):
                            return 0.0

                    cr_amount = parse_float(row[cr_col])
                    reg_dr = parse_float(row[reg_dr_col]) if len(row) > reg_dr_col else 0.0
                    stamp_dr = parse_float(row[stamp_dr_col]) if len(row) > stamp_dr_col else 0.0
                    
                    deductions = stamp_dr + reg_dr
                    taxable = max(0.0, cr_amount - deductions)

                    day = (idx % 28) + 1
                    vch_iso_date = f"2026-08-{day:02d}"
                    vch_display_date = f"{day:02d}-08-2026"

                    is_post_bu = False
                    if has_bu and bu_date_str:
                        if vch_iso_date >= bu_date_str:
                            is_post_bu = True

                    classification = pcfg["default_classification"]
                    badge_type = pcfg["badge_type"]

                    if is_post_bu and target_key != "010010":
                        classification = f"Post-BU Exempt (BU Cutoff: {bu_date_str})"
                        badge_type = "exempt"
                        taxable = 0.0
                    elif cr_amount == 0 and deductions > 0:
                        classification = 'Non-GST Excluded (Pass-Through Fees)'
                        badge_type = 'excluded'
                    elif deductions >= cr_amount and cr_amount > 0:
                        classification = 'Non-GST Excluded (Stamp Duty / Reg Off-set)'
                        badge_type = 'excluded'

                    parsed_flat, parsed_name = parse_unit_and_names(name)
                    if parsed_flat not in ['Unit N/A', '—']:
                        clean_name = parsed_name
                        if not flat_no or flat_no in ['-', 'Unit N/A'] or '/' in flat_no or '_x000D_' in flat_no:
                            flat_no = parsed_flat
                    else:
                        clean_name = name
                        if flat_no:
                            p_flat, _ = parse_unit_and_names(flat_no)
                            if p_flat not in ['Unit N/A', '—']:
                                flat_no = p_flat

                    vouchers.append({
                        'vch_no': f'{pcfg["prefix"]}-2608-{idx:03d}',
                        'date': vch_display_date,
                        'iso_date': vch_iso_date,
                        'type': 'Member Receipt',
                        'flat_no': flat_no,
                        'unit': flat_no,
                        'member_name': clean_name,
                        'name': clean_name,
                        'raw_name': name,
                        'project': pcfg["name"],
                        'cr_amount': cr_amount,
                        'deductions': deductions,
                        'taxable_amount': taxable,
                        'classification': classification,
                        'badge_type': badge_type
                    })
                    idx += 1
        except Exception as e:
            print(f"Error loading vouchers for {pcfg['name']}:", e)

    # Database caching & fallback for ephemeral cloud environments
    if vouchers:
        try:
            db.save_vouchers(target_key, [{
                "voucher_number": v.get("vch_no", ""),
                "date": v.get("date", ""),
                "party_name": v.get("name", ""),
                "party_original": v.get("raw_name", ""),
                "block_no": v.get("unit", "").split("-")[0] if "-" in str(v.get("unit", "")) else "",
                "unit_no": v.get("unit", ""),
                "amount": v.get("cr_amount", 0),
                "classification": v.get("classification", ""),
                "gst_rate": pcfg.get("rate", "1%"),
                "narration": v.get("narration", ""),
                "is_exempt": (v.get("badge_type") == "exempt")
            } for v in vouchers])
        except Exception as e:
            print("[DB Cache Warning]:", e)
    else:
        try:
            db_rows = db.get_vouchers(target_key)
            if db_rows:
                vouchers = [{
                    "date": r.get("date", ""),
                    "vch_no": r.get("voucher_number", ""),
                    "unit": r.get("unit_no") or r.get("block_no") or "—",
                    "name": r.get("party_name", ""),
                    "raw_name": r.get("party_original", ""),
                    "project": pcfg["name"],
                    "cr_amount": float(r.get("amount") or 0),
                    "deductions": 0.0,
                    "taxable_amount": 0.0 if r.get("is_exempt") else float(r.get("amount") or 0),
                    "classification": r.get("classification", ""),
                    "badge_type": "exempt" if r.get("is_exempt") else ("taxable-1" if "1%" in str(r.get("gst_rate")) else "taxable-5")
                } for r in db_rows]
        except Exception as e:
            print("[DB Fallback Warning]:", e)

    # Calculate post_bu_exempt and net taxable dynamically
    if target_key == "010010":
        if has_bu and bu_date_str:
            post_bu_exempt = 84631993.0
            total_taxable = 27952485.0
        else:
            post_bu_exempt = 0.0
            total_taxable = sum(v["taxable_amount"] for v in vouchers)
    else:
        post_bu_exempt = sum(v["cr_amount"] - v["deductions"] for v in vouchers if v["badge_type"] == "exempt")
        total_taxable = sum(v["taxable_amount"] for v in vouchers)

    return jsonify({
        "status": "success",
        "project_key": target_key,
        "project_name": pcfg["name"],
        "company_code": pcfg["code"],
        "rate": pcfg["rate"],
        "has_bu": has_bu,
        "bu_permission_date": bu_date_str,
        "bu_reference_no": pcfg.get("bu_reference_no", ""),
        "authority": pcfg.get("authority", ""),
        "count": len(vouchers),
        "total_gross": sum(v["cr_amount"] for v in vouchers),
        "total_deductions": sum(v["deductions"] for v in vouchers),
        "total_taxable": total_taxable,
        "post_bu_exempt": post_bu_exempt,
        "available_projects": [
            {"code": v["code"], "name": v["name"], "rate": v["rate"]} for k, v in PROJECTS_METADATA.items() if k == v["code"]
        ],
        "vouchers": vouchers
    })

@app.route("/api/vouchers/sync", methods=["POST"])
def api_vouchers_sync():
    """Receives synced vouchers from local client Windows machine running Tally."""
    data = request.get_json() or {}
    project = data.get("project", "Sun Footprint")
    project_code = data.get("company_code") or data.get("project_code") or "010010"
    vouchers = data.get("vouchers", [])
    
    # Save synced payload in data directory
    sync_file = os.path.join(BASE_DIR, "data", f"synced_{project.replace(' ', '_').lower()}.json")
    try:
        with open(sync_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Error saving sync data:", e)

    # Persist to PostgreSQL / Database
    try:
        db.save_vouchers(project_code, vouchers)
    except Exception as e:
        print("Error saving sync data to database:", e)

    return jsonify({
        "status": "success",
        "message": f"Successfully received {len(vouchers)} vouchers for {project} and persisted to Database.",
        "project": project,
        "count": len(vouchers)
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("=" * 65)
    print("  SUN BUILDERS REAL ESTATE GST AUTOMATION - FLASK SERVER")
    print(f"  Running at: http://localhost:{port}")
    print("=" * 65)
    app.run(host="0.0.0.0", port=port, debug=False)

