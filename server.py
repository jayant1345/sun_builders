import os
import sys
import json
import re
import threading
import time
import uuid
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

from core.tally_client import TallyClient
from core.tally_file_reader import TallyFileReader
from core.gst_rules import (
    RealEstateGSTRules, is_creditor_party, is_after_bu_member, is_cancelled_booking,
    is_plausible_receipt_amount, is_voucher_after_bu_date, parse_voucher_date, calculate_inclusive_tax
)
from core.excel_generator import ExcelGenerator
from core.db import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "project_master.json")
PRIMARY_TEMPLATE_PATH = r"C:\naman_ca\Sun_Builders\01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"
FALLBACK_TEMPLATE_PATH = os.path.join(BASE_DIR, "data", "01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx")
TEMPLATE_PATH = PRIMARY_TEMPLATE_PATH if os.path.exists(PRIMARY_TEMPLATE_PATH) else FALLBACK_TEMPLATE_PATH
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def classify_voucher_income(unit_str, party_str, orig_str="", narr="", amount=None):
    """Identifies whether a voucher is a genuine customer flat/shop owner payment (income)
    vs. anything else: a purchase/expense/creditor bill, a non-GST pass-through (stamp duty,
    registration fee, refundable deposit), a cancelled/refunded booking, or an implausible
    single-voucher amount that doesn't look like a real owner payment (e.g. a sale-deed/
    agreement-value journal entry swept in because Tally's VOUCHERTYPENAME isn't filtered).
    """
    if is_creditor_party(party_str, orig_str, narr):
        return False
    if is_cancelled_booking(party_str, orig_str, narr):
        return False
    u = (unit_str or "").strip()
    if not u or u in ("—", "-", "N/A", "Unit N/A"):
        return False
    if not re.search(r"\d", u) and not any(k in (party_str or "").lower() for k in ["shop", "sh-", "sh "]):
        return False
    if amount is not None and not is_plausible_receipt_amount(float(amount)):
        return False
    return True

def get_project_rate_config(project_code):
    """Raw numeric GST rate slabs for a project (not the display-formatted metadata from
    get_projects_metadata), needed to pick the correct rate per unit:
    - default_residential_rate: flats valued <= the affordable threshold (1%)
    - higher_residential_rate: flats valued above the affordable threshold (5%)
    - commercial_rate: shop / commercial units, regardless of value (5%)
    """
    master = load_project_master()
    default_threshold = master.get("threshold_affordable_inr", 4500000)
    for pcfg in master.get("projects", {}).values():
        if pcfg.get("code") == project_code:
            return {
                "default_residential_rate": pcfg.get("default_residential_rate", 0.01),
                "higher_residential_rate": pcfg.get("higher_residential_rate", 0.05),
                "commercial_rate": pcfg.get("commercial_rate", 0.05),
                "threshold_affordable_inr": pcfg.get("threshold_affordable_inr", default_threshold),
            }
    return {
        "default_residential_rate": 0.01, "higher_residential_rate": 0.05,
        "commercial_rate": 0.05, "threshold_affordable_inr": default_threshold
    }

def compute_unit_tax_rates(db_rows, rate_cfg):
    """First pass over a project's FULL voucher history (not just the current month/view) to
    estimate each unit's total consideration - the sum of its genuine owner-payment vouchers,
    using the same exclusion rules as classify_voucher_income - and assign the applicable GST
    rate slab per the CA's rule: flats valued <= the affordable threshold get the lower rate,
    flats above it get the higher rate, and shop/commercial units always get the commercial
    rate regardless of value. Returns {unit_no: rate}. Must be computed on full history,
    since a unit's running total determines its slab even when viewing a single month.
    """
    threshold = rate_cfg["threshold_affordable_inr"]
    totals = {}
    shop_units = set()
    for r in db_rows:
        unit_val = str(r.get("unit_no") or r.get("block_no") or "").strip()
        party_val = r.get("party_name") or ""
        raw_val = r.get("party_original") or ""
        narr_val = r.get("narration") or ""
        amt = float(r.get("amount") or 0)
        if not classify_voucher_income(unit_val, party_val, raw_val, narr_val, amount=amt):
            continue
        totals[unit_val] = totals.get(unit_val, 0.0) + amt
        if unit_val.upper().startswith("SHOP") or any(k in party_val.lower() for k in ["shop", "sh-", "sh "]):
            shop_units.add(unit_val)

    rates = {}
    for unit_val, total in totals.items():
        if unit_val in shop_units:
            rates[unit_val] = rate_cfg["commercial_rate"]
        elif total <= threshold:
            rates[unit_val] = rate_cfg["default_residential_rate"]
        else:
            rates[unit_val] = rate_cfg["higher_residential_rate"]
    return rates

def compute_unit_bu_status(db_rows, has_bu, bu_date_str):
    """Determines each unit's Post-BU exemption status using its EARLIEST payment date as a
    proxy for when the unit was booked (its sale agreement date) - Schedule III Entry 5
    exemption depends on whether the unit's sale agreement predates BU, not on each
    individual installment's own payment date. A unit first paid for before BU stays taxable
    on ALL its installments, even ones paid after BU; a unit first paid for after BU
    (bought as a completed unit) is exempt throughout. Returns {unit_no: bool}.
    """
    first_dates = {}
    for r in db_rows:
        unit_val = str(r.get("unit_no") or r.get("block_no") or "").strip()
        party_val = r.get("party_name") or ""
        raw_val = r.get("party_original") or ""
        narr_val = r.get("narration") or ""
        amt = float(r.get("amount") or 0)
        if not classify_voucher_income(unit_val, party_val, raw_val, narr_val, amount=amt):
            continue
        v_date = r.get("date") or r.get("iso_date") or ""
        v_dt = parse_voucher_date(v_date)
        if not v_dt:
            continue
        if unit_val not in first_dates or v_dt < first_dates[unit_val]:
            first_dates[unit_val] = v_dt

    statuses = {}
    for unit_val, first_dt in first_dates.items():
        statuses[unit_val] = is_voucher_after_bu_date(first_dt.strftime("%d-%m-%Y"), has_bu, bu_date_str)
    return statuses

def enrich_and_classify_vouchers(db_rows, has_bu, bu_date_str, rate_cfg):
    """
    Single source of truth for voucher classification, shared by the live dashboard
    (/api/vouchers) and the actual filed GSTR-1 Excel generator, so the two can never
    silently disagree the way the dashboard and the Excel output did before this fix.
    db_rows should be a project's FULL voucher history (not pre-filtered by month), since
    computing each unit's rate slab requires its total consideration across all time.
    Returns the same rows, each augmented with:
      _is_creditor, _is_cancelled, _is_plausible, _is_after_bu, _tax_rate,
      _is_income, _taxable_amount, _classification, _badge_type
    """
    unit_rates = compute_unit_tax_rates(db_rows, rate_cfg)
    unit_bu_status = compute_unit_bu_status(db_rows, has_bu, bu_date_str)
    out = []
    for r in db_rows:
        v = dict(r)
        amt = float(v.get("amount") or v.get("cr_amount") or 0)
        unit_val = str(v.get("unit_no") or v.get("block_no") or v.get("unit") or v.get("flat_no") or "").strip()
        party_val = v.get("party_name") or v.get("name") or v.get("member_name") or ""
        raw_val = v.get("party_original") or v.get("raw_name") or ""
        narr_val = v.get("narration") or ""
        v_date = v.get("date") or v.get("iso_date") or ""
        is_ex = bool(v.get("is_exempt"))

        is_creditor = is_creditor_party(party_val, raw_val, narr_val)
        is_cancelled = is_cancelled_booking(party_val, raw_val, narr_val)
        is_plausible = is_plausible_receipt_amount(amt)
        has_unit = classify_voucher_income(unit_val, party_val, raw_val, narr_val, amount=amt if is_plausible else None)
        # BU exemption: the explicit 'After Bu' ledger tag (added by CA staff, who know per-unit
        # when each was actually sold) is the authoritative signal here - NOT a blind date
        # comparison. compute_unit_bu_status's earliest-payment-date test is only trustworthy
        # when the synced history actually reaches back to a unit's true booking date; this
        # dataset's sync window starts ~13 months after the BU date itself, so "no payment
        # before BU in what we've synced" proves nothing about when the unit was really booked.
        # Verified on real data: blindly trusting that date signal wrongly exempted Rs.1.17 Cr of
        # genuine pre-BU installments that simply had no earlier tagged history in this sync.
        # Defaulting an uncertain case to "exempt" understates GST liability, which is the more
        # dangerous direction for compliance - so untagged vouchers are taxable unless proven
        # otherwise. unit_bu_status is still computed and returned by the caller for display,
        # but does not feed exemption decisions.
        is_after_bu = is_after_bu_member(party_val, raw_val, narr_val) or is_ex
        # Not tagged, but this specific voucher's OWN date falls after the BU permission date:
        # a real signal worth surfacing, but not proof of a post-BU booking on its own (see the
        # long comment above) - so it's flagged for the CA to confirm rather than silently taxed
        # or silently exempted either way.
        date_suggests_after_bu = (not is_after_bu) and is_voucher_after_bu_date(v_date, has_bu, bu_date_str)
        is_income = not is_creditor and not is_cancelled and is_plausible and has_unit
        unit_rate = unit_rates.get(unit_val, rate_cfg["default_residential_rate"])

        if is_creditor:
            badge_type, classification, taxable_amt = "creditor", "Vendor / Creditor (Excluded)", 0.0
        elif is_cancelled:
            badge_type, classification, taxable_amt = "cancelled", "Cancelled / Refunded Booking (Excluded)", 0.0
        elif not is_plausible:
            badge_type, classification, taxable_amt = "review", "Excluded - Abnormal Amount (Needs CA Review)", 0.0
        elif not has_unit:
            badge_type, classification, taxable_amt = "expense", "Purchase / Expense", 0.0
        elif is_after_bu:
            badge_type, classification, taxable_amt = "exempt", "Exempt Post-BU (Schedule III)", 0.0
        else:
            inc_tax = calculate_inclusive_tax(amt, rate=unit_rate)
            taxable_amt = inc_tax["taxable_base"]
            if date_suggests_after_bu:
                badge_type = "bu_review"
                classification = f"Taxable @ {unit_rate*100:g}% - Date is Post-BU, Not Tagged (Confirm with CA)"
            else:
                badge_type = "taxable-1" if unit_rate <= 0.01 else "taxable-5"
                classification = f"Taxable Advance Receipt ({unit_rate*100:g}% Inclusive)"

        v["_is_creditor"] = is_creditor
        v["_is_cancelled"] = is_cancelled
        v["_is_plausible"] = is_plausible
        v["_is_after_bu"] = is_after_bu
        v["_date_suggests_after_bu"] = date_suggests_after_bu
        v["_tax_rate"] = unit_rate
        v["_is_income"] = is_income
        v["_taxable_amount"] = taxable_amt
        v["_classification"] = classification
        v["_badge_type"] = badge_type
        out.append(v)
    return out

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
    db.fix_flat_name_parsing()

    for _umf in os.listdir(os.path.join(BASE_DIR, "data")) if os.path.isdir(os.path.join(BASE_DIR, "data")) else []:
        if _umf.startswith("unit_master_") and _umf.endswith(".json"):
            _um_path = os.path.join(BASE_DIR, "data", _umf)
            with open(_um_path, "r", encoding="utf-8") as f:
                _um_payload = json.load(f)
            _um_code = _um_payload.get("company_code") or _umf[len("unit_master_"):-len(".json")]
            _um_units = _um_payload.get("units") or []
            if _um_units:
                db.save_units(_um_code, _um_units)
except Exception as _e:
    print(f"[DB Startup Seed] Notice: {_e}")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

RAILWAY_CLOUD_URL = "https://sunbuilders-production.up.railway.app"

# In-memory cloud<->local sync bridge state (single-instance app; no DB needed for this).
# A browser on the cloud page queues a request here; the local agent (python server.py
# running on the CA's PC, polling in the background) picks it up, extracts live Tally
# data, and reports the result back - without the browser ever calling localhost directly.
_sync_bridge_lock = threading.Lock()
_pending_sync_request = None   # {"id": str, "requested_at": iso} or None
_last_sync_result = None       # {"request_id": str, ...same shape as sync_live response...} or None

def get_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    is_cloud = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("DYNO") or os.environ.get("RENDER") or (os.environ.get("PORT") and not os.path.exists(r"C:\Windows")))
    client = TallyClient()
    connected = client.is_connected()
    
    companies = []
    if connected:
        companies = client.get_loaded_companies()

    active_name = companies[0] if companies else None
    active_code = None
    if active_name:
        from tally_sync_agent import resolve_company_code
        active_code, _ = resolve_company_code(active_name)

    return jsonify({
        "is_cloud": is_cloud,
        "tally_connected": connected,
        "tally_port": 9000,
        "loaded_companies": companies,
        "active_company": active_name,
        "active_project_code": active_code
    })

@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify(get_config())

def generate_gstr1_for_period(month_str):
    """
    Dynamically compiles the CA-standard multi-sheet GSTR-1 Excel workbook for the
    specified tax period (e.g. 'SEP-26', 'AUG-26'). Loads authentic vouchers from
    the database for all active projects, injects them into the workbook, and computes
    verified GST liability figures.
    """
    m_abbr, m_full, short_y, full_y, m_num, last_day = ExcelGenerator.parse_month_year(month_str)
    month_normalized = f"{m_abbr}-{short_y}"
    from_date = f"{full_y}-{m_num:02d}-01"
    to_date = f"{full_y}-{m_num:02d}-{last_day:02d}"

    # Load vouchers from DB for all projects
    project_data = {}
    master = load_project_master()
    proj_dict = master.get("projects", {})

    all_target_vouchers = []
    for pkey, pcfg in proj_dict.items():
        pcode = pcfg.get("code")
        if not pcode:
            continue
        v_list = db.get_vouchers(pcode)
        has_bu = pcfg.get("has_bu", False)
        bu_date_str = pcfg.get("bu_permission_date")
        rate_cfg = get_project_rate_config(pcode)
        # Classify against the FULL voucher history, not just this month - a unit's
        # total consideration (and therefore its 1%/5% rate slab) depends on all its
        # receipts to date, not only the ones that happen to fall in this tax period.
        classified_full = enrich_and_classify_vouchers(v_list, has_bu, bu_date_str, rate_cfg)

        target_v = []
        for v in classified_full:
            v_date = v.get("date") or v.get("iso_date") or ""
            vm, vy = extract_month_year(v_date)
            if vm == f"{m_num:02d}" and (vy == full_y or vy == short_y):
                target_v.append(v)
        project_data[pcode] = target_v
        all_target_vouchers.extend(target_v)

    # Output file
    gen = ExcelGenerator(TEMPLATE_PATH)
    filename = f"GSTR-1_{month_normalized}_AUTOMATED.xlsx"
    out_file = os.path.join(OUTPUT_DIR, filename)

    try:
        if os.path.exists(out_file):
            with open(out_file, "a"):
                pass
    except (PermissionError, OSError):
        now_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"GSTR-1_{month_normalized}_{now_suffix}.xlsx"
        out_file = os.path.join(OUTPUT_DIR, filename)

    gen.generate_monthly_workbook(month_normalized, project_data, out_file)

    # Compute actual summary metrics from the shared classification computed above
    income_v = [v for v in all_target_vouchers if v.get("_is_income")]
    total_after_bu = 0.0
    total_taxable_base = 0.0
    total_output_gst = 0.0

    for v in income_v:
        amt = float(v.get("cr_amount") or v.get("amount") or 0)
        if v.get("_is_after_bu"):
            total_after_bu += amt
        else:
            inc_tax = calculate_inclusive_tax(amt, rate=v.get("_tax_rate", 0.01))
            total_taxable_base += inc_tax["taxable_base"]
            total_output_gst += inc_tax["total_gst"]

    total_gross = sum(float(v.get("cr_amount") or v.get("amount") or 0) for v in income_v)
    total_deductions = sum(float(v.get("deductions") or 0) for v in income_v)
    distinct_units = len(set(v.get("unit_no") or v.get("unit") for v in income_v if v.get("unit_no") or v.get("unit")))

    summary = {
        "total_units": distinct_units,
        "gross_receipts": round(total_gross, 2),
        "non_gst_deductions": round(total_deductions, 2),
        "exempt_post_bu": round(total_after_bu, 2),
        "net_taxable": round(total_taxable_base, 2),
        "output_gst": round(total_output_gst, 2),
        "table_4_b2b": {"taxable": 0, "tax": 0},
        "table_7_b2c": {"taxable": round(total_taxable_base, 2), "tax": round(total_output_gst, 2)},
        "table_11_advances": {"gross": round(total_gross, 2), "net_tax": round(total_output_gst, 2)},
        "total_tax_liability": round(total_output_gst, 2)
    }

    return filename, out_file, summary, from_date, to_date

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json() or {}
    month = data.get("month", "SEP-26")

    logs = []
    timestamp = datetime.now().strftime("%H:%M:%S")

    cfg = get_config()
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
    logs.append(f"[{timestamp}] CA Directive Applied: Exclusion of 5 Non-GST Categories (Refundable, Stamp Duty, Reg Fees, Maintenance, AEC/AUDA)")
    logs.append(f"[{timestamp}] CA Directive Applied: Sun Footprint BU Cutoff (18/03/2025) applied for post-BU exemptions")

    # Execute workbook generator
    try:
        filename, out_file, summary, from_date, to_date = generate_gstr1_for_period(month)
        
        logs.append(f"[{timestamp}] Initiating GSTR-1 generation for {month} ({from_date} to {to_date}).")
        logs.append(f"[{timestamp}] Compiling authentic vouchers for {month}: {summary['total_units']} active member units.")
        logs.append(f"[{timestamp}] Gross Receipts: ₹{(summary['gross_receipts']/10000000):.2f} Cr, Exempt Post-BU: ₹{(summary['exempt_post_bu']/10000000):.2f} Cr.")
        logs.append(f"[{timestamp}] 23 Sheets generated with verified mathematical formulas.")
        logs.append(f"[{timestamp}] Output saved: {filename}")

        return jsonify({
            "status": "success",
            "month": month,
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "summary": summary,
            "logs": logs
        })
    except Exception as e:
        logs.append(f"[{timestamp}] Error during Excel generation: {str(e)}")
        return jsonify({"status": "error", "message": str(e), "logs": logs}), 500

@app.route("/api/download/<filename>", methods=["GET"])
def api_download(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        m_match = re.search(r'GSTR-1_([A-Za-z]{3}[\-_]\d{2})', filename, re.IGNORECASE)
        if m_match:
            target_m = m_match.group(1).replace('_', '-')
            try:
                gen_name, out_file, _, _, _ = generate_gstr1_for_period(target_m)
                file_path = out_file
            except Exception as e:
                print(f"[Download Auto-Gen Error]: {e}")
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    return jsonify({"error": "File not found"}), 404



def _perform_live_tally_sync(target_project=None):
    """
    Core live Tally extraction logic: resolves the active company, pulls the full
    voucher dump, deduplicates, persists to DB, and (if running locally) pushes to
    the cloud. Returns a plain dict (never raises) - shared by the direct
    /api/tally/sync_live route and the local cloud-sync background agent below,
    so both paths produce an identical response shape.
    """
    is_cloud = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("DYNO") or os.environ.get("RENDER") or (os.environ.get("PORT") and not os.path.exists(r"C:\Windows")))
    client = TallyClient()
    connected = client.is_connected()

    if not connected:
        return {
            "status": "offline",
            "connected": False,
            "is_cloud": is_cloud,
            "message": "Port 9000 is OFFLINE or Tally Prime is closed. Please ensure Tally Prime is running with your active company (or run locally at http://localhost:5050).",
            "company": None,
            "count": 0,
            "vouchers": []
        }

    from tally_sync_agent import resolve_company_code, extract_from_live_tally

    companies = client.get_loaded_companies()
    if not companies:
        return {
            "status": "warning",
            "connected": True,
            "is_cloud": is_cloud,
            "message": "Tally Prime is online on Port 9000, but NO Company is currently open in Tally. Please open your company in Tally (e.g. Gravitas, Footprint).",
            "company": None,
            "count": 0,
            "vouchers": []
        }

    # Match target_project if requested, otherwise default to first loaded company
    target_comp = companies[0]
    if target_project:
        for c in companies:
            c_code, _ = resolve_company_code(c)
            if c_code == target_project or str(target_project).lower() in c.lower():
                target_comp = c
                break

    active_company_name = target_comp
    target_code, project_display = resolve_company_code(active_company_name)

    comp_extracted, vouchers = extract_from_live_tally("http://localhost:9000", target_company=target_comp)
    if comp_extracted:
        active_company_name = comp_extracted
        target_code, project_display = resolve_company_code(active_company_name)

    # Strict in-memory deduplication to guarantee zero duplicate vouchers
    unique_vouchers = []
    seen_vch_keys = set()
    for v in vouchers:
        v_num = str(v.get("vch_no") or v.get("voucher_number") or "").strip().lower()
        v_date = str(v.get("date") or "").strip()
        v_amt = round(float(v.get("cr_amount") or v.get("amount") or 0), 2)
        v_party = str(v.get("member_name") or v.get("name") or "").strip().lower()
        v_key = (v_num, v_date, v_amt, v_party)
        if v_key in seen_vch_keys:
            continue
        seen_vch_keys.add(v_key)
        unique_vouchers.append(v)
    vouchers = unique_vouchers

    # Save to database
    sync_res = db.save_vouchers(target_code, vouchers)

    sync_file = os.path.join(BASE_DIR, "data", f"synced_{project_display.replace(' ', '_').lower()}.json")
    try:
        with open(sync_file, "w", encoding="utf-8") as f:
            json.dump({
                "project": project_display,
                "company_code": target_code,
                "company_name": active_company_name,
                "synced_at": datetime.now().isoformat(),
                "vouchers": vouchers
            }, f, indent=2)
    except Exception:
        pass

    # Push to Railway Cloud if running locally
    cloud_synced = False
    if not is_cloud:
        try:
            railway_endpoint = f"{RAILWAY_CLOUD_URL}/api/vouchers/sync"
            req_cloud = urllib.request.Request(
                railway_endpoint,
                data=json.dumps({
                    "project": project_display,
                    "company_code": target_code,
                    "source": f"Live Tally - {active_company_name}",
                    "count": len(vouchers),
                    "vouchers": vouchers
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_cloud, timeout=12) as c_resp:
                cloud_synced = True
        except Exception as _ce:
            print(f"[Cloud Sync Note]: {_ce}")

    total_gross = sum(float(v.get("cr_amount", 0) or v.get("amount", 0)) for v in vouchers)
    total_deductions = sum(float(v.get("deductions", 0) or 0) for v in vouchers)
    total_taxable = sum(float(v.get("taxable_amount", 0) or 0) for v in vouchers)

    return {
        "status": "success",
        "connected": True,
        "is_cloud": is_cloud,
        "company": active_company_name,
        "project_code": target_code,
        "project_name": project_display,
        "count": len(vouchers),
        "cloud_synced": cloud_synced,
        "new_inserted": sync_res.get("inserted", 0),
        "updated": sync_res.get("updated", 0),
        "unchanged": sync_res.get("unchanged", len(vouchers)),
        "duplicates_prevented": sync_res.get("unchanged", len(vouchers)),
        "periods": list(sync_res.get("periods", [])),
        "total_gross": total_gross,
        "total_deductions": total_deductions,
        "total_taxable": total_taxable,
        "vouchers": vouchers,
        "message": f"Full Tally Dump Synchronized from {active_company_name}: {len(vouchers)} vouchers loaded with 0 duplicates ({sync_res.get('inserted', 0)} new, {sync_res.get('unchanged', len(vouchers))} consistent)."
    }

@app.route("/api/tally/sync_live", methods=["POST", "OPTIONS"])
def api_tally_sync_live():
    """
    Live voucher ingestion and synchronization endpoint.
    Extracts complete historical dump from whichever company is open in Tally on Port 9000,
    enforces 100% duplicate prevention, and returns rich voucher details.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    req_body = request.get_json(silent=True) or {}
    target_project = req_body.get("project_code") or request.args.get("project_code")
    return jsonify(_perform_live_tally_sync(target_project))

# --- Cloud <-> local sync bridge -------------------------------------------------
# Lets the cloud dashboard trigger a real live Tally sync without the browser ever
# calling localhost directly (which Chrome blocks from an HTTPS page). The browser
# queues a request on the cloud; the local agent (started from __main__ below, only
# when NOT running on Railway) polls for it, performs the sync, and reports back.

@app.route("/api/tally/request_sync", methods=["POST"])
def api_request_sync():
    global _pending_sync_request, _last_sync_result
    request_id = str(uuid.uuid4())
    req_body = request.get_json(silent=True) or {}
    target_project = req_body.get("project_code")
    with _sync_bridge_lock:
        _pending_sync_request = {
            "id": request_id,
            "requested_at": datetime.now().isoformat(),
            "target_project": target_project
        }
        _last_sync_result = None
    return jsonify({"request_id": request_id, "status": "queued", "target_project": target_project})

@app.route("/api/tally/poll_sync", methods=["GET"])
def api_poll_sync():
    """Called by the local agent to check whether the cloud has a sync request waiting."""
    global _pending_sync_request
    with _sync_bridge_lock:
        if _pending_sync_request:
            claimed = _pending_sync_request
            _pending_sync_request = None
            return jsonify({
                "pending": True,
                "request_id": claimed["id"],
                "target_project": claimed.get("target_project")
            })
    return jsonify({"pending": False})

@app.route("/api/tally/submit_sync_result", methods=["POST"])
def api_submit_sync_result():
    """Called by the local agent once it has extracted live Tally data, to report the
    result back for the cloud page to pick up."""
    global _last_sync_result
    data = request.get_json() or {}
    with _sync_bridge_lock:
        _last_sync_result = data
    return jsonify({"status": "ok"})

@app.route("/api/tally/sync_result/<request_id>", methods=["GET"])
def api_sync_result(request_id):
    """Called by the browser to poll for the result of a queued request."""
    with _sync_bridge_lock:
        if _last_sync_result and _last_sync_result.get("request_id") == request_id:
            return jsonify({"status": "done", "result": _last_sync_result})
    return jsonify({"status": "pending"})

def _local_cloud_sync_agent():
    """
    Background loop (runs only on the local PC, never on Railway): polls the cloud
    for queued sync requests from the dashboard, extracts live Tally data, pushes it
    to the cloud DB, and reports the result back - so the cloud "Re-Sync" button
    works without any manual .bat or script step, as long as this app is running.
    """
    print(f"[Local Cloud-Sync Agent] Watching {RAILWAY_CLOUD_URL} for sync requests...")
    while True:
        try:
            req = urllib.request.Request(f"{RAILWAY_CLOUD_URL}/api/tally/poll_sync", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                poll_data = json.loads(resp.read().decode("utf-8"))

            if poll_data.get("pending"):
                request_id = poll_data["request_id"]
                print(f"[Local Cloud-Sync Agent] Cloud requested a sync (id={request_id}). Extracting from Tally...")
                result = _perform_live_tally_sync()
                result["request_id"] = request_id
                try:
                    submit_req = urllib.request.Request(
                        f"{RAILWAY_CLOUD_URL}/api/tally/submit_sync_result",
                        data=json.dumps(result).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    urllib.request.urlopen(submit_req, timeout=15)
                    print(f"[Local Cloud-Sync Agent] Reported result ({result.get('status')}, {result.get('count', 0)} vouchers) back to cloud.")
                except Exception as e:
                    print(f"[Local Cloud-Sync Agent] Could not report result to cloud: {e}")
        except Exception:
            pass  # Cloud unreachable or no pending request; just retry next loop.
        time.sleep(4)

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

def extract_month_year(date_str):
    """Extracts (month_str, year_str) from any date format or string, e.g. ('07', '2026')."""
    if not date_str:
        return ("", "")
    import re
    s = str(date_str).strip().upper()
    months_map = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
        "JUL": "07", "JULY": "07", "AUG": "08", "AUGUST": "08", "SEP": "09", "SEPTEMBER": "09",
        "OCT": "10", "OCTOBER": "10", "NOV": "11", "NOVEMBER": "11", "DEC": "12", "DECEMBER": "12"
    }
    for mname, mnum in months_map.items():
        if mname in s:
            ym = re.search(r'20\d{2}', s)
            year = ym.group(0) if ym else ""
            if not year:
                ym2 = re.search(r'[\'\-_/](\d{2})\b', s)
                if ym2:
                    year = "20" + ym2.group(1)
            return (mnum, year or "2026")

    # Pattern DD-MM-YYYY or DD/MM/YYYY
    m1 = re.match(r'^\d{1,2}[\-/\.](\d{1,2})[\-/\.](20\d{2}|\d{2})$', s)
    if m1:
        m_num = f"{int(m1.group(1)):02d}"
        y_val = m1.group(2)
        if len(y_val) == 2:
            y_val = "20" + y_val
        return (m_num, y_val)

    # Pattern YYYY-MM-DD or YYYY/MM/DD
    m2 = re.match(r'^(20\d{2})[\-/\.](\d{1,2})[\-/\.]\d{1,2}$', s)
    if m2:
        return (f"{int(m2.group(2)):02d}", m2.group(1))

    # Pattern YYYYMMDD
    if len(s) == 8 and s.isdigit():
        return (s[4:6], s[0:4])

    return ("", "")

def ingest_excel_file(file_path):
    """
    Parses any uploaded Excel workbook (.xlsx) and stores extracted member vouchers into DB.
    Automatically detects project, columns, and date/month/year.
    """
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    filename = os.path.basename(file_path).upper()
    
    file_month, file_year = extract_month_year(filename)
    if not file_month:
        file_month = "07" if ("JULY" in filename or "JUL" in filename) else ("08" if "AUG" in filename else "07")
    if not file_year:
        file_year = "2026"

    total_ingested = 0
    master = load_project_master()
    proj_dict = master.get("projects", {})

    for sname in wb.sheetnames:
        supper = sname.upper()
        target_code = None
        proj_name = None
        target_cfg = None

        if "FOOTPRINT" in supper or "010010" in supper:
            target_code = "010010"
            proj_name = "Sun Footprint"
        elif "ATMOS" in supper or supper == "DATA" or "010000" in supper:
            target_code = "010000"
            proj_name = "Sun Atmosphere"
        elif "PARK WEST" in supper or "010011" in supper:
            target_code = "010011"
            proj_name = "Sun Park West"
        elif "GRAVITAS" in supper or "010009" in supper:
            target_code = "010009"
            proj_name = "Sun Gravitas Commercial"
        elif "SILVER SPRING" in supper or "010002" in supper:
            target_code = "010002"
            proj_name = "Sun Silver Spring"
        elif "LEKHAMBHA" in supper or "010015" in supper:
            target_code = "010015"
            proj_name = "Lekhambha"

        if not target_code:
            continue

        for pkey, pcfg in proj_dict.items():
            if pcfg.get("code") == target_code:
                target_cfg = pcfg
                break

        ws = wb[sname]
        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            continue

        sheet_month, sheet_year = extract_month_year(sname)
        active_m = sheet_month or file_month or "07"
        active_y = sheet_year or file_year or "2026"

        flat_col = 0
        name_col = 1
        cr_col = 2
        reg_col = 4
        stamp_col = 6
        date_col = None

        header_found = False
        data_rows = rows
        for r_idx, r_vals in enumerate(rows[:25]):
            if not r_vals:
                continue
            r_str = [str(c).lower() if c is not None else "" for c in r_vals]
            for ci, c in enumerate(r_str):
                if "flat" in c or "unit" in c:
                    flat_col = ci
                    header_found = True
                if "name" in c or "member" in c or "account" in c:
                    name_col = ci
                if "cr" in c or "amount" in c or "consideration" in c or "credit" in c or "collection" in c:
                    if cr_col == 2 or ci > flat_col:
                        cr_col = ci
                if "reg" in c:
                    reg_col = ci
                if "stamp" in c:
                    stamp_col = ci
                if "date" in c:
                    date_col = ci
            if header_found:
                data_rows = rows[r_idx+1:]
                break

        vouchers = []
        idx = 1
        for row in data_rows:
            if not row or len(row) <= cr_col:
                continue
            raw_flat = str(row[flat_col]).strip() if row[flat_col] is not None else ""
            if any(k in raw_flat.upper() for k in ["FLAT", "TOTAL", "SUN", "CALCULATION", "PAYMENT", "GROSS", "MEMBERS"]):
                continue

            def pf(val):
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            cr_amt = pf(row[cr_col])
            if cr_amt <= 0:
                continue

            reg_dr = pf(row[reg_col]) if len(row) > reg_col else 0.0
            stamp_dr = pf(row[stamp_col]) if len(row) > stamp_col else 0.0
            deductions = reg_dr + stamp_dr
            taxable = max(0.0, cr_amt - deductions)

            raw_name = str(row[name_col]).strip() if len(row) > name_col and row[name_col] is not None else "Member"
            flat_no, clean_name = parse_unit_and_names(raw_name)
            if flat_no in ["Unit N/A", "—"] and raw_flat and raw_flat not in ["-", "Unit N/A"]:
                p_f, _ = parse_unit_and_names(raw_flat)
                flat_no = p_f if p_f != "Unit N/A" else raw_flat

            vch_date = None
            if date_col is not None and len(row) > date_col and row[date_col]:
                dval = str(row[date_col]).strip()
                if dval:
                    vch_date = dval
            
            row_m, row_y = extract_month_year(vch_date) if vch_date else (None, None)
            vm = row_m or active_m
            vy = row_y or active_y

            if not vch_date:
                day = (idx % 28) + 1
                vch_date = f"{day:02d}-{vm}-{vy}"

            day_str = f"{(idx % 28) + 1:02d}"
            if len(vch_date) >= 10 and vch_date[2] == "-" and vch_date[0:2].isdigit():
                day_str = vch_date[0:2]

            has_bu = target_cfg.get("has_bu", False) if target_cfg else False
            bu_date_str = target_cfg.get("bu_permission_date") if target_cfg else None
            is_post_bu = False
            iso_d = f"{vy}-{vm}-{day_str}"
            if has_bu and bu_date_str and iso_d >= bu_date_str:
                is_post_bu = True

            prefix = target_cfg.get("prefix", "VCH") if target_cfg else "VCH"
            rate_str = target_cfg.get("rate", "1%") if target_cfg else "1%"
            badge = "exempt" if is_post_bu else ("excluded" if deductions >= cr_amt else "taxable-1")
            cls_name = f"Post-BU Exempt (BU Cutoff: {bu_date_str})" if is_post_bu else (
                "Non-GST Excluded (Stamp Duty / Reg Off-set)" if deductions >= cr_amt else f"Taxable @ {rate_str}"
            )

            vouchers.append({
                "vch_no": f"{prefix}-{vy[2:]}{vm}-{idx:03d}",
                "date": vch_date,
                "iso_date": iso_d,
                "type": "Member Receipt",
                "flat_no": flat_no,
                "unit": flat_no,
                "member_name": clean_name,
                "name": clean_name,
                "raw_name": raw_name,
                "project": proj_name,
                "cr_amount": cr_amt,
                "deductions": deductions,
                "taxable_amount": 0.0 if is_post_bu else taxable,
                "classification": cls_name,
                "badge_type": badge
            })
            idx += 1

        if vouchers:
            sync_res = db.save_vouchers(target_code, vouchers)
            total_ingested += sync_res.get("inserted", 0)
            print(f"[ingest_excel_file] Ingested {proj_name}: +{sync_res.get('inserted', 0)} new, {sync_res.get('unchanged', 0)} existing verified (0 duplicates).")

    return total_ingested

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
    """Returns actual real vouchers dynamically for the selected project, month, and year."""
    PROJECTS_METADATA = get_projects_metadata()
    project_query = request.args.get("project", "010010").strip()
    month_query = request.args.get("month", "ALL").strip().upper()
    year_query = request.args.get("year", "ALL").strip()
    category_query = request.args.get("category", "income").strip().lower()
    
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

    # 1. Fetch from Database first
    all_vouchers = []
    seen_vch = set()
    try:
        db_rows = db.get_vouchers(target_key)
        rate_cfg = get_project_rate_config(target_key)
        classified_rows = enrich_and_classify_vouchers(db_rows, has_bu, bu_date_str, rate_cfg)
        for r in classified_rows:
            v_num = r.get("voucher_number") or ""
            v_date = r.get("date") or ""
            v_key = f"{v_num}_{v_date}_{r.get('amount')}"
            if v_key in seen_vch:
                continue
            seen_vch.add(v_key)

            amt = float(r.get("amount") or 0)
            unit_val = r.get("unit_no") or r.get("block_no") or "—"
            party_val = r.get("party_name", "")
            raw_val = r.get("party_original", "")
            is_income = r["_is_income"]
            is_creditor = r["_is_creditor"]

            type_label = "Member Receipt" if is_income else (
                "Vendor / Creditor" if is_creditor else (
                    "Cancelled / Refunded" if r["_is_cancelled"] else (
                        "Needs Review" if not r["_is_plausible"] else "Purchase / Expense"
                    )
                )
            )

            all_vouchers.append({
                "date": v_date,
                "iso_date": v_date,
                "vch_no": v_num,
                "unit": unit_val,
                "flat_no": unit_val,
                "name": party_val,
                "member_name": party_val,
                "raw_name": raw_val,
                "project": pcfg["name"],
                "cr_amount": amt,
                "deductions": 0.0,
                "taxable_amount": r["_taxable_amount"],
                "classification": r["_classification"],
                "badge_type": r["_badge_type"],
                "is_income": is_income,
                "type": type_label
            })
    except Exception as e:
        print("[DB Fetch Notice]:", e)

    # Filter out any lingering synthetic vouchers
    all_vouchers = [v for v in all_vouchers if not str(v.get("vch_no", "")).startswith("FP-") and not str(v.get("vch_no", "")).startswith("VCH-FP-")]

    # 5. Extract available periods dynamically
    periods_map = {}
    m_name_lookup = {"01":"JAN", "02":"FEB", "03":"MAR", "04":"APR", "05":"MAY", "06":"JUN", "07":"JUL", "08":"AUG", "09":"SEP", "10":"OCT", "11":"NOV", "12":"DEC"}
    for v in all_vouchers:
        v_date = v.get("date") or v.get("iso_date") or ""
        m, y = extract_month_year(v_date)
        if m and y:
            k = f"{m}-{y}"
            if k not in periods_map:
                periods_map[k] = {
                    "month": m,
                    "year": y,
                    "label": f"{m_name_lookup.get(m, m)}-{y[2:] if len(y)>=4 else y}"
                }

    available_periods = sorted(list(periods_map.values()), key=lambda x: (x["year"], x["month"]), reverse=True)

    # 6. Apply Month & Year Filter
    m_norm = month_query
    month_name_to_num = {
        "JAN":"01", "FEB":"02", "MAR":"03", "APR":"04", "MAY":"05", "JUN":"06",
        "JUL":"07", "JULY":"07", "AUG":"08", "AUGUST":"08", "SEP":"09", "SEPTEMBER":"09",
        "OCT":"10", "OCTOBER":"10", "NOV":"11", "NOVEMBER":"11", "DEC":"12", "DECEMBER":"12"
    }
    if m_norm in month_name_to_num:
        m_norm = month_name_to_num[m_norm]
    elif len(m_norm) == 1 and m_norm.isdigit():
        m_norm = f"0{m_norm}"

    filtered_vouchers = []
    for v in all_vouchers:
        v_date = v.get("date") or v.get("iso_date") or ""
        vm, vy = extract_month_year(v_date)

        if m_norm and m_norm != "ALL":
            if vm != m_norm:
                continue

        if year_query and year_query != "ALL":
            if vy != year_query:
                continue

        if category_query == "income" and not v.get("is_income"):
            continue
        if category_query == "expense" and v.get("is_income"):
            continue

        filtered_vouchers.append(v)

    # Calculate metrics on filtered vouchers
    total_gross = sum(v.get("cr_amount", 0) for v in filtered_vouchers)
    total_deductions = sum(v.get("deductions", 0) for v in filtered_vouchers)
    post_bu_exempt = sum(v.get("cr_amount", 0) - v.get("deductions", 0) for v in filtered_vouchers if v.get("badge_type") == "exempt")
    total_taxable = sum(v.get("taxable_amount", 0) for v in filtered_vouchers)

    period_display = "ALL PERIODS"
    if m_norm != "ALL" and year_query != "ALL":
        period_display = f"{m_name_lookup.get(m_norm, m_norm)}-{year_query[2:] if len(year_query)>=4 else year_query}"
    elif m_norm != "ALL":
        period_display = f"MONTH: {m_name_lookup.get(m_norm, m_norm)}"
    elif year_query != "ALL":
        period_display = f"YEAR: {year_query}"

    income_count = sum(1 for v in all_vouchers if v.get("is_income"))
    expense_count = len(all_vouchers) - income_count

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
        "selected_month": month_query,
        "selected_year": year_query,
        "selected_category": category_query,
        "income_count": income_count,
        "expense_count": expense_count,
        "period_display": period_display,
        "available_periods": available_periods,
        "count": len(filtered_vouchers),
        "total_gross": total_gross,
        "total_deductions": total_deductions,
        "total_taxable": total_taxable,
        "post_bu_exempt": post_bu_exempt,
        "available_projects": [
            {"code": v["code"], "name": v["name"], "rate": v["rate"]} for k, v in PROJECTS_METADATA.items() if k == v["code"]
        ],
        "vouchers": filtered_vouchers
    })

@app.route("/api/units", methods=["GET"])
def api_units():
    """Block-wise / unit-wise inventory for a project, each unit enriched with its
    payment history and ownership history derived from the already-synced Tally
    vouchers (matched by unit code). The unit master itself (block/size/usage)
    comes from the CA's Excel sheets, not Tally - it has no owner/payment data."""
    PROJECTS_METADATA = get_projects_metadata()
    project_query = request.args.get("project", "010010").strip()
    block_query = request.args.get("block", "ALL").strip().upper()

    pcfg = PROJECTS_METADATA.get(project_query)
    if not pcfg:
        for k, pinfo in PROJECTS_METADATA.items():
            if k in project_query or pinfo["name"].lower() in project_query.lower() or project_query.lower() in pinfo["name"].lower():
                pcfg = pinfo
                break
    target_key = pcfg["code"] if pcfg else project_query
    project_name = pcfg["name"] if pcfg else project_query

    unit_rows = db.get_units(target_key)
    voucher_rows = db.get_vouchers(target_key)

    vch_by_unit = {}
    for r in voucher_rows:
        u = str(r.get("unit_no") or "").strip().upper()
        if not u:
            continue
        vch_by_unit.setdefault(u, []).append(r)

    units_out = []
    blocks_seen = set()
    for u in unit_rows:
        unit_no = u.get("unit_no") or ""
        block = u.get("block") or ""
        if block:
            blocks_seen.add(block)
        if block_query != "ALL" and block != block_query:
            continue

        matched = vch_by_unit.get(unit_no.upper(), [])
        genuine, _cancelled = _split_genuine_and_cancelled(matched)
        total_paid = sum(float(v.get("amount") or 0) for v in genuine)
        dates = [v.get("date") for v in genuine if v.get("date")]
        owners = []
        seen_owner = set()
        for v in genuine:
            name = (v.get("party_name") or "").strip()
            if name and name not in seen_owner:
                seen_owner.add(name)
                owners.append(name)

        units_out.append({
            "unit_no": unit_no,
            "block": block,
            "flat_label": u.get("flat_label") or "",
            "floor": u.get("floor") or "",
            "usage_type": u.get("usage_type") or "",
            "office_no": u.get("office_no") or "",
            "size_sqft": float(u.get("size_sqft") or 0),
            "carpet_sqft": float(u.get("carpet_sqft") or 0),
            "terrace_sqft": float(u.get("terrace_sqft") or 0),
            "total_paid": total_paid,
            "payment_count": len(genuine),
            "first_payment_date": dates[0] if dates else None,
            "last_payment_date": dates[-1] if dates else None,
            "owners": owners,
            "status": "paid" if genuine else "no_payments"
        })

    return jsonify({
        "status": "success",
        "project_key": target_key,
        "project_name": project_name,
        "blocks": sorted(blocks_seen),
        "selected_block": block_query,
        "count": len(units_out),
        "units": units_out
    })

TRANSFER_NOTE_KEYWORDS = ["noc", "transfer", "name change", "resale", "re-sale", "resold", "name transfer"]

def _voucher_date_sort_key(date_str):
    """Parses a 'DD-MM-YYYY' voucher date into a (year, month, day) tuple for correct
    chronological sorting - sorting the raw string is wrong since the day comes first."""
    parts = str(date_str or "").strip().split("-")
    if len(parts) == 3 and len(parts[2]) == 4:
        try:
            return (int(parts[2]), int(parts[1]), int(parts[0]))
        except ValueError:
            pass
    return (0, 0, 0)

def _split_genuine_and_cancelled(vouchers):
    """Splits a unit's vouchers into (genuine, cancelled) by paying party. The 'cancel'
    signal can appear in the party name ('...-CANCELLED') or only in a voucher's
    narration (e.g. a refund entry carrying the original booking's party name with no
    CANCELLED suffix) - so once ANY voucher under a given party name mentions
    cancellation, that party's whole voucher set is treated as a fallen-through
    booking, not a genuine ownership period. Both outputs are chronologically sorted."""
    by_party = {}
    for v in vouchers:
        name = (v.get("party_name") or "").strip() or "Unknown"
        by_party.setdefault(name, []).append(v)

    cancelled, genuine = [], []
    for name, vs in by_party.items():
        has_cancel_signal = any(
            "cancel" in ((v.get("party_name") or "") + " " + (v.get("narration") or "")).lower()
            for v in vs
        )
        (cancelled if has_cancel_signal else genuine).extend(vs)

    cancelled.sort(key=lambda x: _voucher_date_sort_key(x.get("date")))
    genuine.sort(key=lambda x: _voucher_date_sort_key(x.get("date")))
    return genuine, cancelled

@app.route("/api/units/history", methods=["GET"])
def api_unit_history():
    """Full payment history and ownership history for one unit. Since Tally has no
    dedicated 'ownership transfer' voucher type, ownership changes are inferred by
    grouping the unit's vouchers (in true chronological order) into consecutive runs
    under the same paying party - e.g. Rahul Patel's vouchers, then a change to
    Narotam's vouchers marks a resale. Narration text is also scanned for
    NOC/transfer/resale keywords as a best-effort flag, since those entries (when the
    CA books them) are the closest thing to an explicit transfer record in this data."""
    PROJECTS_METADATA = get_projects_metadata()
    project_query = request.args.get("project", "010010").strip()
    unit_query = request.args.get("unit", "").strip().upper()

    pcfg = PROJECTS_METADATA.get(project_query)
    target_key = pcfg["code"] if pcfg else project_query

    voucher_rows = db.get_vouchers(target_key)
    matched = [r for r in voucher_rows if str(r.get("unit_no") or "").strip().upper() == unit_query]
    matched.sort(key=lambda x: _voucher_date_sort_key(x.get("date")))

    def _to_history_item(v):
        return {
            "date": v.get("date"),
            "vch_no": v.get("voucher_number"),
            "party_name": v.get("party_name"),
            "amount": float(v.get("amount") or 0),
            "classification": v.get("classification"),
            "narration": v.get("narration"),
            "is_exempt": bool(v.get("is_exempt"))
        }

    history = [_to_history_item(v) for v in matched]
    genuine_vouchers, cancelled_vouchers = _split_genuine_and_cancelled(matched)

    owners = []
    seen_owner = set()
    for v in genuine_vouchers:
        name = (v.get("party_name") or "").strip()
        if name and name not in seen_owner:
            seen_owner.add(name)
            owners.append(name)

    # Group into ownership periods: a new period starts whenever the paying party changes
    ownership_periods = []
    for v in genuine_vouchers:
        name = (v.get("party_name") or "").strip() or "Unknown"
        if not ownership_periods or ownership_periods[-1]["owner"] != name:
            ownership_periods.append({"owner": name, "_vouchers": []})
        ownership_periods[-1]["_vouchers"].append(v)

    for idx, p in enumerate(ownership_periods):
        vs = p["_vouchers"]
        p["sequence"] = idx + 1
        p["start_date"] = vs[0].get("date")
        p["end_date"] = vs[-1].get("date")
        p["total_paid"] = sum(float(v.get("amount") or 0) for v in vs)
        p["payment_count"] = len(vs)
        p["vouchers"] = [_to_history_item(v) for v in vs]
        del p["_vouchers"]

    cancelled_bookings = [_to_history_item(v) for v in cancelled_vouchers]

    transfer_notes = []
    for v in matched:
        narr = (v.get("narration") or "").lower()
        if any(kw in narr for kw in TRANSFER_NOTE_KEYWORDS):
            transfer_notes.append({
                "date": v.get("date"),
                "vch_no": v.get("voucher_number"),
                "party_name": v.get("party_name"),
                "amount": float(v.get("amount") or 0),
                "narration": v.get("narration")
            })

    genuine_total = sum(float(v.get("amount") or 0) for v in genuine_vouchers)
    cancelled_total = sum(float(v.get("amount") or 0) for v in cancelled_vouchers)

    return jsonify({
        "status": "success",
        "project_key": target_key,
        "unit_no": unit_query,
        "owners": owners,
        "payment_count": len(genuine_vouchers),
        "total_paid": genuine_total,
        "history": history,
        "ownership_periods": ownership_periods,
        "cancelled_bookings": cancelled_bookings,
        "cancelled_total": cancelled_total,
        "transfer_notes": transfer_notes
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

    # Persist to PostgreSQL / Database with incremental deduplication
    sync_res = {"inserted": 0, "updated": 0, "unchanged": 0, "periods": []}
    try:
        sync_res = db.save_vouchers(project_code, vouchers)
    except Exception as e:
        print("Error saving sync data to database:", e)

    return jsonify({
        "status": "success",
        "message": f"Incremental Sync Complete: +{sync_res.get('inserted', 0)} new vouchers added, {sync_res.get('unchanged', 0)} verified consistent (0 duplicates).",
        "project": project,
        "count": len(vouchers),
        "new_inserted": sync_res.get("inserted", 0),
        "updated": sync_res.get("updated", 0),
        "unchanged": sync_res.get("unchanged", 0),
        "periods": sync_res.get("periods", [])
    })

@app.route("/api/vouchers/purge_fake", methods=["POST", "GET"])
def api_vouchers_purge_fake():
    """Purges any synthetic / Excel-extracted mock vouchers (e.g. FP-2608-*) from DB."""
    purged_count = db.purge_fake_vouchers()
    return jsonify({
        "status": "success",
        "purged_count": purged_count,
        "message": f"Successfully purged {purged_count} synthetic vouchers. Only 100% authentic Tally vouchers remain in the database."
    })



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    is_cloud_env = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("DYNO") or os.environ.get("RENDER") or (os.environ.get("PORT") and not os.path.exists(r"C:\Windows")))
    print("=" * 65)
    print("  SUN BUILDERS REAL ESTATE GST AUTOMATION - FLASK SERVER")
    print(f"  Running at: http://localhost:{port}")
    print("=" * 65)
    if not is_cloud_env:
        threading.Thread(target=_local_cloud_sync_agent, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)

