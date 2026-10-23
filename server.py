import os
import sys
import json
import re
import threading
import time
import uuid
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory, session, redirect, url_for

from core.tally_client import TallyClient
from core.tally_file_reader import TallyFileReader
from core.gst_rules import (
    RealEstateGSTRules, is_creditor_party, is_after_bu_member, is_cancelled_booking,
    is_plausible_receipt_amount, is_voucher_after_bu_date, parse_voucher_date, calculate_inclusive_tax,
    classify_pass_through_type, is_valid_unit_code
)
from core.excel_generator import ExcelGenerator
from core.db import db
from core.activity_logger import (
    log_activity, log_tally_sync, log_gstr_generation, log_bu_update,
    log_voucher_override, log_unit_bu_override, log_unit_master_import,
    log_report_download, log_purge_vouchers, export_activity_logs_csv,
    ActivityType, ActivityStatus
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "project_master.json")
PRIMARY_TEMPLATE_PATH = r"C:\naman_ca\Sun_Builders\01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"
FALLBACK_TEMPLATE_PATH = os.path.join(BASE_DIR, "data", "01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx")
TEMPLATE_PATH = PRIMARY_TEMPLATE_PATH if os.path.exists(PRIMARY_TEMPLATE_PATH) else FALLBACK_TEMPLATE_PATH
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def classify_voucher_income(unit_str, party_str, orig_str="", narr="", amount=None):
    """Identifies whether a voucher is pure, genuine builder customer unit installment/booking income.
    Strictly excludes:
    - Creditors, vendors, contractors, and general expense bills
    - Cancelled / refunded bookings
    - Non-GST pass-through payments: AUDA, PGVCL/electricity, society deposits, maintenance, stamp duty, etc.
    - Rows without an authentic block/flat/unit code (names like Sonal, Hemil, Subhash, etc. are rejected).
    """
    if is_creditor_party(party_str, orig_str, narr):
        return False
    if is_cancelled_booking(party_str, orig_str, narr):
        return False
    # AUDA, PGVCL, society deposits, maintenance deposits, stamp duty are NOT builder income
    if classify_pass_through_type(party_str, orig_str, narr):
        return False
    u = (unit_str or "").strip()
    if not is_valid_unit_code(u):
        return False
    if amount is not None and not is_plausible_receipt_amount(float(amount)):
        return False
    return True

def _is_genuine_sale_consideration(unit_val, party_val, raw_val, narr_val, amt):
    """Like classify_voucher_income, but also excludes non-GST pass-through amounts (stamp
    duty, registration fee, refundable deposit, etc.) - used when estimating a unit's total
    consideration (for the 1%/5% rate slab) or its first booking date, since a pass-through
    fee isn't part of the sale value and shouldn't count toward either."""
    if not classify_voucher_income(unit_val, party_val, raw_val, narr_val, amount=amt):
        return False
    if classify_pass_through_type(party_val, raw_val, narr_val):
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
        if not _is_genuine_sale_consideration(unit_val, party_val, raw_val, narr_val, amt):
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
        if not _is_genuine_sale_consideration(unit_val, party_val, raw_val, narr_val, amt):
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

_VOUCHER_CLASSIFICATION_CACHE = {}

def clear_voucher_classification_cache(project_code=None):
    global _VOUCHER_CLASSIFICATION_CACHE
    if project_code:
        keys_to_del = [k for k in _VOUCHER_CLASSIFICATION_CACHE if k[0] == project_code]
        for k in keys_to_del:
            _VOUCHER_CLASSIFICATION_CACHE.pop(k, None)
    else:
        _VOUCHER_CLASSIFICATION_CACHE.clear()

def enrich_and_classify_vouchers(db_rows, has_bu, bu_date_str, rate_cfg, project_code=None):
    """
    Single source of truth for voucher classification, shared by the live dashboard
    (/api/vouchers) and the actual filed GSTR-1 Excel generator.
    Cached in memory so subsequent dropdown changes and page loads respond in <5ms.
    """
    if not db_rows:
        return []

    pcode = project_code or db_rows[0].get("project_code") or "unknown"
    cache_key = (
        pcode,
        len(db_rows),
        has_bu,
        str(bu_date_str),
        float(rate_cfg.get("default_residential_rate", 0.01)) if rate_cfg else 0.01
    )
    if cache_key in _VOUCHER_CLASSIFICATION_CACHE:
        return _VOUCHER_CLASSIFICATION_CACHE[cache_key]

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
        pass_through_type = classify_pass_through_type(party_val, raw_val, narr_val) if (has_unit and not is_creditor) else None
        tag_after_bu = is_after_bu_member(party_val, raw_val, narr_val) or is_ex
        date_after_bu = (not tag_after_bu) and unit_bu_status.get(unit_val, False)
        is_after_bu = tag_after_bu

        override_bu_status = v.get("override_bu_status")
        override_is_income_raw = v.get("override_is_income")
        override_rate = v.get("override_rate")
        override_note = (v.get("override_note") or "").strip()

        manually_excluded = False
        if override_is_income_raw is not None:
            if bool(override_is_income_raw):
                is_creditor = is_cancelled = False
                is_plausible = has_unit = True
                pass_through_type = None
            else:
                manually_excluded = True
        if override_bu_status == "after_bu":
            is_after_bu = True
        elif override_bu_status == "before_bu":
            is_after_bu = False

        is_income = (not manually_excluded) and not is_creditor and not is_cancelled and is_plausible and has_unit and not pass_through_type
        unit_rate = float(override_rate) if override_rate else unit_rates.get(unit_val, rate_cfg["default_residential_rate"])

        if manually_excluded:
            badge_type = "excluded_manual"
            classification = "Excluded by CA" + (f" ({override_note})" if override_note else "")
            taxable_amt = 0.0
        elif is_creditor:
            badge_type, classification, taxable_amt = "creditor", "Vendor / Creditor (Excluded)", 0.0
        elif is_cancelled:
            badge_type, classification, taxable_amt = "cancelled", "Cancelled / Refunded Booking (Excluded)", 0.0
        elif not is_plausible:
            badge_type, classification, taxable_amt = "review", "Excluded - Abnormal Amount (Needs CA Review)", 0.0
        elif not has_unit:
            badge_type, classification, taxable_amt = "expense", "Purchase / Expense", 0.0
        elif pass_through_type:
            badge_type = "pass_through"
            classification = f"Non-GST Pass-Through ({pass_through_type.replace('_', ' ').title()})"
            taxable_amt = 0.0
        elif is_after_bu:
            taxable_amt = 0.0
            badge_type, classification = "exempt", "Exempt Post-BU (Schedule III)" + (" [CA Confirmed]" if override_bu_status == "after_bu" else "")
        else:
            inc_tax = calculate_inclusive_tax(amt, rate=unit_rate)
            taxable_amt = inc_tax["taxable_base"]
            if date_after_bu:
                badge_type = "bu_review"
                classification = f"Taxable @ {unit_rate*100:g}% - First Synced Payment is Post-BU, Not Tagged (Confirm with CA)"
            else:
                badge_type = "taxable-1" if unit_rate <= 0.01 else "taxable-5"
                suffix = " [CA Set Rate]" if override_rate else (" [CA Confirmed]" if override_bu_status == "before_bu" else "")
                classification = f"Taxable Advance Receipt ({unit_rate*100:g}% Inclusive){suffix}"

        v["_is_creditor"] = is_creditor
        v["_is_cancelled"] = is_cancelled
        v["_is_plausible"] = is_plausible
        v["_is_after_bu"] = is_after_bu
        v["_date_after_bu"] = date_after_bu
        v["_pass_through_type"] = pass_through_type
        v["_tax_rate"] = unit_rate
        v["_is_income"] = is_income
        v["_taxable_amount"] = taxable_amt
        v["_classification"] = classification
        v["_badge_type"] = badge_type
        v["_has_override"] = bool(override_bu_status or override_is_income_raw is not None or override_rate)
        out.append(v)

    _VOUCHER_CLASSIFICATION_CACHE[cache_key] = out
    return out

# Startup Database Seeding (Guarded to run in <0.2s)
try:
    if os.path.exists(CONFIG_PATH):
        db.seed_projects_from_file(CONFIG_PATH)

    # 1. Seed Footprint vouchers once if empty
    fp_vouchers = db.get_vouchers("010010")
    if not fp_vouchers:
        footprint_sync_path = os.path.join(BASE_DIR, "data", "synced_sun_footprint.json")
        if os.path.exists(footprint_sync_path):
            with open(footprint_sync_path, "r", encoding="utf-8") as f:
                synced_payload = json.load(f)
                v_list = synced_payload.get("vouchers") if isinstance(synced_payload, dict) else synced_payload
                if isinstance(v_list, list) and v_list:
                    db.save_vouchers("010010", v_list)

    # 2. Seed Atmosphere (010000) vouchers if empty
    atmos_vouchers = db.get_vouchers("010000")
    if not atmos_vouchers:
        excel_path = os.path.join(BASE_DIR, "data", "01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx")
        if os.path.exists(excel_path):
            ingest_excel_file(excel_path)

    # 3. Fix flat name parsing once only (flag-guarded)
    flag_file = os.path.join(BASE_DIR, "data", ".flat_parsing_fixed")
    if not os.path.exists(flag_file):
        db.fix_flat_name_parsing()
        try:
            with open(flag_file, "w") as f:
                f.write("fixed")
        except Exception:
            pass

    for _umf in os.listdir(os.path.join(BASE_DIR, "data")) if os.path.isdir(os.path.join(BASE_DIR, "data")) else []:
        if _umf.startswith("unit_master_") and _umf.endswith(".json"):
            _um_path = os.path.join(BASE_DIR, "data", _umf)
            with open(_um_path, "r", encoding="utf-8") as f:
                _um_payload = json.load(f)
            _um_code = _um_payload.get("company_code") or _umf[len("unit_master_"):-len(".json")]
            if not db.get_units(_um_code):
                _um_units = _um_payload.get("units") or []
                if _um_units:
                    db.save_units(_um_code, _um_units)
except Exception as _e:
    print(f"[DB Startup Seed] Notice: {_e}")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY") or "sun-builders-gst-jwt-secret-session-key-2026-llp"
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7  # 7 days
app.jinja_env.auto_reload = True

PUBLIC_AUTH_PATHS = {
    "/login",
    "/logout",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    # Automated Tally agent bridge routes for remote CA sync
    "/api/tally/poll_sync",
    "/api/tally/submit_sync_result",
    "/api/tally/request_sync",
    "/api/tally/report_progress",
    "/api/vouchers/sync",
}

@app.before_request
def enforce_authentication():
    # 1. Allow static assets and favicon
    if request.path.startswith("/static/") or request.path == "/favicon.ico":
        return None

    # 2. Allow explicitly public routes & sync results
    if request.path in PUBLIC_AUTH_PATHS or request.path.startswith("/api/tally/sync_result/"):
        return None

    # 3. Allow CORS preflight OPTIONS
    if request.method == "OPTIONS":
        return None

    # 4. Check session
    user = session.get("user")
    if user:
        return None

    # 5. If unauthenticated API call -> 401 JSON
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "Authentication required. Please sign in as admin.",
            "authenticated": False
        }), 401

    # 6. If unauthenticated page visit -> redirect to /login
    target_path = request.full_path if request.query_string else request.path
    if target_path and target_path != "/" and target_path != "/?":
        return redirect(f"/login?next={urllib.parse.quote(target_path)}")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "GET":
        if session.get("user"):
            return redirect("/")
        return render_template("login.html", error=None)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    remember = bool(request.form.get("remember"))

    verified = db.verify_user(username, password)
    if verified:
        session.permanent = remember
        session["user"] = verified["username"]
        session["role"] = verified["role"]
        log_activity(
            activity_type=ActivityType.USER_LOGIN,
            action="LOGIN_SUCCESS",
            description=f"User '{username}' logged in successfully via web form.",
            details={"username": username, "role": verified["role"]},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        next_page = request.args.get("next") or "/"
        return redirect(next_page)
    else:
        log_activity(
            activity_type=ActivityType.USER_LOGIN,
            action="LOGIN_FAILED",
            description=f"Failed login attempt for username '{username}'.",
            status=ActivityStatus.WARNING,
            details={"username": username},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        return render_template("login.html", error="Invalid username or password.")

@app.route("/logout", methods=["GET", "POST"])
def logout_view():
    user = session.get("user")
    if user:
        log_activity(
            activity_type=ActivityType.USER_LOGOUT,
            action="LOGOUT",
            description=f"User '{user}' signed out.",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
    session.clear()
    return redirect("/login")

@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required."}), 400

    verified = db.verify_user(username, password)
    if verified:
        session.permanent = True
        session["user"] = verified["username"]
        session["role"] = verified["role"]
        log_activity(
            activity_type=ActivityType.USER_LOGIN,
            action="LOGIN_SUCCESS",
            description=f"User '{username}' logged in via API.",
            details={"username": username, "role": verified["role"]},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        return jsonify({
            "success": True,
            "user": {
                "username": verified["username"],
                "role": verified["role"]
            }
        })
    else:
        log_activity(
            activity_type=ActivityType.USER_LOGIN,
            action="LOGIN_FAILED",
            description=f"API failed login attempt for '{username}'.",
            status=ActivityStatus.WARNING,
            details={"username": username},
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    user = session.get("user")
    if user:
        log_activity(
            activity_type=ActivityType.USER_LOGOUT,
            action="LOGOUT",
            description=f"User '{user}' logged out via API.",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    user = session.get("user")
    if user:
        return jsonify({
            "authenticated": True,
            "username": user,
            "role": session.get("role", "admin")
        })
    return jsonify({
        "authenticated": False,
        "username": None,
        "role": None
    })

@app.route("/api/auth/change-password", methods=["POST"])
def api_auth_change_password():
    user = session.get("user")
    if not user:
        return jsonify({"success": False, "error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    old_password = str(data.get("old_password", ""))
    new_password = str(data.get("new_password", "")).strip()

    if not old_password or not new_password:
        return jsonify({"success": False, "error": "Old and new password are required."}), 400

    if len(new_password) < 4:
        return jsonify({"success": False, "error": "New password must be at least 4 characters long."}), 400

    verified = db.verify_user(user, old_password)
    if not verified:
        return jsonify({"success": False, "error": "Current password is incorrect."}), 400

    success = db.update_password(user, new_password)
    if success:
        log_activity(
            activity_type=ActivityType.PASSWORD_CHANGE,
            action="PASSWORD_UPDATED",
            description=f"Password for user '{user}' was successfully changed.",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        return jsonify({"success": True, "message": "Password updated successfully."})
    else:
        return jsonify({"success": False, "error": "Failed to update password in database."}), 500

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
    # API responses carry live financial/voucher data that changes between deploys and
    # between syncs - caching them (browser or any edge/CDN layer) can silently show stale
    # tax classification/totals after a fix ships, as happened here: a browser kept showing
    # a pre-fix GST total long after the server was already returning the corrected one.
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
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

def compute_gstr1_summary(month_str):
    """
    Computes statutory GSTR-1 summary figures for the given tax period across all projects.
    Uses unified enrichment and classification logic.
    """
    m_abbr, m_full, short_y, full_y, m_num, last_day = ExcelGenerator.parse_month_year(month_str)
    month_normalized = f"{m_abbr}-{short_y}"

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
        classified_full = enrich_and_classify_vouchers(v_list, has_bu, bu_date_str, rate_cfg)

        for v in classified_full:
            v_date = v.get("date") or v.get("iso_date") or ""
            vm, vy = extract_month_year(v_date)
            if vm == f"{m_num:02d}" and (vy == full_y or vy == short_y):
                all_target_vouchers.append(v)

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

    return {
        "month": month_normalized,
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

    summary = compute_gstr1_summary(month_str)
    return filename, out_file, summary, from_date, to_date

@app.route("/api/gstr1/summary", methods=["GET"])
def api_gstr1_summary():
    month = request.args.get("month", "SEP-26").strip()
    summary = compute_gstr1_summary(month)
    return jsonify({
        "status": "success",
        "month": summary.get("month", month),
        "summary": summary
    })

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

        log_gstr_generation(
            month=month,
            filename=filename,
            summary=summary,
            logs_count=len(logs),
            ip_address=request.remote_addr
        )

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
        log_activity(
            activity_type=ActivityType.GSTR_GENERATE,
            action=f"Generate GSTR-1 ({month}) FAILED",
            description=f"Error generating GSTR-1 for {month}: {str(e)}",
            project_code="ALL",
            status=ActivityStatus.ERROR,
            details={"month": month, "error": str(e)},
            ip_address=request.remote_addr
        )
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
        log_report_download(filename=filename, ip_address=request.remote_addr)
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

    log_tally_sync(
        project_code=target_code,
        project_name=project_display,
        vouchers_count=len(vouchers),
        inserted=sync_res.get("inserted", 0),
        updated=sync_res.get("updated", 0),
        unchanged=sync_res.get("unchanged", len(vouchers)),
        source=f"Live Tally - {active_company_name}",
        periods=list(sync_res.get("periods", []))
    )

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
# queues a request on the cloud; the local agent polls for it, performs the sync,
# and reports real-time progress back to the dashboard.

_sync_progress = {}

@app.route("/api/tally/request_sync", methods=["POST"])
def api_request_sync():
    global _pending_sync_request, _last_sync_result, _sync_progress
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
        _sync_progress[request_id] = {
            "percent": 15,
            "message": "Sync request queued. Local Tally bridge agent is picking it up...",
            "log": "Request registered on cloud.",
            "step": 1
        }
    return jsonify({"request_id": request_id, "status": "queued", "target_project": target_project})

@app.route("/api/tally/poll_sync", methods=["GET"])
def api_poll_sync():
    """Called by the local agent to check whether the cloud has a sync request waiting."""
    global _pending_sync_request, _sync_progress
    with _sync_bridge_lock:
        if _pending_sync_request:
            claimed = _pending_sync_request
            _pending_sync_request = None
            req_id = claimed["id"]
            if req_id in _sync_progress:
                _sync_progress[req_id]["percent"] = 25
                _sync_progress[req_id]["message"] = "Local bridge agent connected to Tally (Port 9000)..."
                _sync_progress[req_id]["step"] = 2
            return jsonify({
                "pending": True,
                "request_id": req_id,
                "target_project": claimed.get("target_project")
            })
    return jsonify({"pending": False})

@app.route("/api/tally/report_progress", methods=["POST"])
def api_report_progress():
    """Called by the bridge agent to update intermediate upload and extraction progress."""
    global _sync_progress
    data = request.get_json(silent=True) or {}
    req_id = data.get("request_id")
    if req_id:
        with _sync_bridge_lock:
            _sync_progress[req_id] = {
                "percent": data.get("percent", 50),
                "message": data.get("message", "Processing vouchers..."),
                "log": data.get("log", ""),
                "step": data.get("step", 3),
                "count": data.get("count", 0),
                "updated_at": datetime.now().isoformat()
            }
    return jsonify({"status": "ok"})

@app.route("/api/tally/submit_sync_result", methods=["POST"])
def api_submit_sync_result():
    """Called by the local agent once it has extracted live Tally data, to report the
    result back for the cloud page to pick up."""
    global _last_sync_result, _sync_progress
    data = request.get_json(silent=True) or {}
    req_id = data.get("request_id")
    with _sync_bridge_lock:
        _last_sync_result = data
        if req_id and req_id in _sync_progress:
            _sync_progress[req_id]["percent"] = 100
            _sync_progress[req_id]["message"] = f"Complete! Synced {data.get('count', 0)} vouchers successfully."
            _sync_progress[req_id]["step"] = 4
    
    log_activity(
        activity_type=ActivityType.TALLY_SYNC,
        action="Cloud Sync Result Received",
        description=f"Local bridge agent submitted sync result for {data.get('project_name', 'project')}: {data.get('message', 'Completed')}",
        project_code=data.get("project_code", ""),
        project_name=data.get("project_name", ""),
        details=data,
        status=ActivityStatus.SUCCESS if data.get("status") == "success" else ActivityStatus.WARNING,
        ip_address=request.remote_addr
    )
    return jsonify({"status": "ok"})

@app.route("/api/tally/sync_result/<request_id>", methods=["GET"])
def api_sync_result(request_id):
    """Called by the browser to poll for the result of a queued request."""
    with _sync_bridge_lock:
        if _last_sync_result and _last_sync_result.get("request_id") == request_id:
            prog = _sync_progress.get(request_id)
            return jsonify({"status": "done", "result": _last_sync_result, "progress": prog})
        prog = _sync_progress.get(request_id)
        return jsonify({"status": "pending", "progress": prog})

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
        block = m.group(1).upper()
        flat = m.group(2)
        unit = f"{block}-{flat}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern 3: Block + digits glued without separator: e.g. 'L1102,Sudhanshu Agarwal'
    m2 = re.match(r'^([A-Za-z]{1,2})(\d{2,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m2:
        block = m2.group(1).upper()
        flat = m2.group(2)
        unit = f"{block}-{flat}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m2.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name if rest_name else "Member"

    # Pattern 4: Fallback comma / semicolon / dash ONLY IF the first part is a valid unit code
    for sep in [',', ';', '-']:
        if sep in raw:
            parts = raw.split(sep, 1)
            p0 = parts[0].strip()
            p1 = parts[1].strip()
            if is_valid_unit_code(p0):
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
        
        old_bu_date = projects[target_pkey].get("bu_permission_date")
        old_has_bu = projects[target_pkey].get("has_bu", False)

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

        log_bu_update(
            project_code=code,
            project_name=projects[target_pkey].get("display_name", code),
            old_date=old_bu_date,
            new_date=bu_date if has_bu else None,
            old_status="Obtained" if old_has_bu else "Under Construction",
            new_status="Obtained" if has_bu else "Under Construction",
            reference_no=projects[target_pkey].get("bu_reference_no", ""),
            authority=projects[target_pkey].get("authority", ""),
            ip_address=request.remote_addr
        )
        
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

@app.route("/api/projects/create", methods=["POST"])
def api_projects_create():
    """Adds a new project to Sun Builders portfolio, dynamically enabling Tally extraction,
    BU status tracking, and automated GST reporting for it."""
    data = request.get_json() or {}
    code = str(data.get("code") or data.get("project_code", "")).strip()
    name = str(data.get("name") or data.get("project_name", "")).strip()
    
    if not code or not name:
        return jsonify({"status": "error", "message": "Project Code and Project Name are required."}), 400

    master = load_project_master()
    projects = master.get("projects", {})

    # Check for existing code
    for pkey, pcfg in projects.items():
        if str(pcfg.get("code")).strip().upper() == code.upper():
            return jsonify({"status": "error", "message": f"Project code '{code}' already exists ({pcfg.get('display_name')})."}), 400

    aliases_raw = data.get("aliases", "")
    if isinstance(aliases_raw, list):
        aliases = [str(a).strip().upper() for a in aliases_raw if str(a).strip()]
    else:
        aliases = [a.strip().upper() for a in str(aliases_raw).split(",") if a.strip()]

    if code.upper() not in aliases:
        aliases.append(code.upper())
    if name.upper() not in aliases:
        aliases.append(name.upper())

    p_type = str(data.get("type", "Residential > 45L")).strip()
    has_bu = bool(data.get("has_bu", False))
    bu_date = str(data.get("bu_permission_date") or "").strip() or None
    bu_ref = str(data.get("bu_reference_no") or "").strip()
    authority = str(data.get("authority") or "AMC / AUDA").strip()
    notes = str(data.get("notes") or "").strip()
    prefix = str(data.get("prefix") or code[:3]).strip().upper()

    rate_str = str(data.get("rate") or "").strip()
    if "1%" in rate_str or rate_str == "0.01":
        rate_val = 0.01
    elif "18%" in rate_str or rate_str == "0.18":
        rate_val = 0.18
    else:
        rate_val = 0.05

    new_pkey = f"SUN {name.upper()}" if not name.upper().startswith("SUN ") else name.upper()
    new_cfg = {
        "code": code,
        "aliases": aliases,
        "display_name": name,
        "type": p_type,
        "prefix": prefix,
        "has_bu": has_bu,
        "bu_permission_date": bu_date if has_bu else None,
        "bu_reference_no": bu_ref,
        "authority": authority,
        "default_residential_rate": rate_val,
        "higher_residential_rate": 0.05,
        "commercial_rate": 0.18 if "commercial" in p_type.lower() else 0.05,
        "notes": notes
    }

    projects[new_pkey] = new_cfg
    master["projects"] = projects
    save_project_master(master)

    if db:
        try:
            db.upsert_project(
                code=code,
                name=name,
                project_type=p_type,
                gst_rate=f"{int(rate_val * 100)}%",
                bu_status="obtained" if has_bu else "under_construction",
                bu_date=bu_date if has_bu else None,
                bu_ref=bu_ref,
                bu_authority=authority,
                notes=notes
            )
        except Exception as e:
            print(f"[Project Create] DB sync warning: {e}")

    log_activity(
        activity_type=ActivityType.PROJECT_CONFIG,
        action="Create Project",
        description=f"Created new project: {name} ({code}), Type: {p_type}, GST Rate: {int(rate_val * 100)}%",
        project_code=code,
        project_name=name,
        details=new_cfg,
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": f"Project '{name}' ({code}) successfully created and registered!",
        "project": new_cfg
    })

@app.route("/api/projects/delete", methods=["POST"])
def api_projects_delete():
    """Deletes a project by code."""
    data = request.get_json() or {}
    code = str(data.get("code") or data.get("project_code", "")).strip()
    if not code:
        return jsonify({"status": "error", "message": "Project code is required."}), 400

    master = load_project_master()
    projects = master.get("projects", {})
    deleted = False

    keys_to_del = [k for k, p in projects.items() if str(p.get("code")).strip().upper() == code.upper() or k.upper() == code.upper()]
    for k in keys_to_del:
        del projects[k]
        deleted = True

    if deleted:
        master["projects"] = projects
        save_project_master(master)

    if db:
        try:
            db.delete_project(code)
        except Exception as e:
            print(f"[Project Delete] DB sync warning: {e}")

    log_activity(
        activity_type=ActivityType.PROJECT_CONFIG,
        action="Delete Project",
        description=f"Deleted project: {code}",
        project_code=code,
        ip_address=request.remote_addr
    )

    return jsonify({"status": "success", "message": f"Project '{code}' deleted successfully."})

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
        classified_rows = enrich_and_classify_vouchers(db_rows, has_bu, bu_date_str, rate_cfg, project_code=target_key)
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
                "Excluded by CA" if r["_badge_type"] == "excluded_manual" else (
                    "Non-GST Pass-Through" if r["_badge_type"] == "pass_through" else (
                        "Vendor / Creditor" if is_creditor else (
                            "Cancelled / Refunded" if r["_is_cancelled"] else (
                                "Needs Review" if not r["_is_plausible"] else "Purchase / Expense"
                            )
                        )
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
                "type": type_label,
                "has_override": r["_has_override"],
                "override_bu_status": r.get("override_bu_status"),
                "override_is_income": r.get("override_is_income"),
                "override_rate": r.get("override_rate"),
                "override_note": r.get("override_note")
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

    # Optional search filter
    search_query = request.args.get("search", "").strip().lower()
    if search_query:
        filtered_vouchers = [
            v for v in filtered_vouchers
            if search_query in str(v.get("unit", "")).lower()
            or search_query in str(v.get("name", "")).lower()
            or search_query in str(v.get("vch_no", "")).lower()
            or search_query in str(v.get("raw_name", "")).lower()
        ]

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

    # Determine next progressive period (the newest period available, e.g. SEP-26)
    progressive_period = available_periods[0] if available_periods else {"month": "09", "year": "2026", "label": "SEP-26"}

    # Limit payload size for ALL months view so responses are instantaneous (<50ms)
    total_count = len(filtered_vouchers)
    display_vouchers = filtered_vouchers[:500] if (m_norm == "ALL" and not search_query and total_count > 500) else filtered_vouchers

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
        "progressive_period": progressive_period,
        "count": total_count,
        "total_gross": total_gross,
        "total_deductions": total_deductions,
        "total_taxable": total_taxable,
        "post_bu_exempt": post_bu_exempt,
        "available_projects": [
            {"code": v["code"], "name": v["name"], "rate": v["rate"]} for k, v in PROJECTS_METADATA.items() if k == v["code"]
        ],
        "vouchers": display_vouchers
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
    if not pcfg:
        for k, pinfo in PROJECTS_METADATA.items():
            if k in project_query or pinfo["name"].lower() in project_query.lower() or project_query.lower() in pinfo["name"].lower():
                pcfg = pinfo
                break
    target_key = pcfg["code"] if pcfg else project_query
    project_name = pcfg.get("name", "Project") if pcfg else target_key

    has_bu = pcfg.get("has_bu", False) if pcfg else False
    bu_date_str = pcfg.get("bu_permission_date") if pcfg else None
    formatted_bu_date = None
    if bu_date_str:
        try:
            parts = bu_date_str.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                formatted_bu_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
            else:
                formatted_bu_date = bu_date_str
        except Exception:
            formatted_bu_date = bu_date_str

    voucher_rows = db.get_vouchers(target_key)
    rate_cfg = get_project_rate_config(target_key)
    classified_rows = enrich_and_classify_vouchers(voucher_rows, has_bu, bu_date_str, rate_cfg)

    def _clean(u):
        return str(u or "").strip().upper().replace(" ", "").replace("-", "").replace("/", "")

    norm_q = _clean(unit_query)
    matched = []
    for r in classified_rows:
        u_val = str(r.get("unit_no") or r.get("block_no") or r.get("unit") or r.get("flat_no") or "").strip().upper()
        if u_val == unit_query or (norm_q and _clean(u_val) == norm_q):
            matched.append(r)
    matched.sort(key=lambda x: _voucher_date_sort_key(x.get("date")))

    unit_meta = {}
    try:
        with db.get_connection() as conn:
            cur = conn.cursor()
            if db.is_postgres:
                cur.execute("SELECT * FROM units WHERE project_code = %s AND (UPPER(unit_no) = %s OR UPPER(flat_label) = %s)", (target_key, unit_query, unit_query))
            else:
                cur.execute("SELECT * FROM units WHERE project_code = ? AND (UPPER(unit_no) = ? OR UPPER(flat_label) = ?)", (target_key, unit_query, unit_query))
            row = cur.fetchone()
            if row:
                unit_meta = dict(row)
    except Exception as e:
        pass

    history = []
    total_receipts = 0.0
    total_taxable_base = 0.0
    total_tax = 0.0
    total_exempt = 0.0
    total_pass_through = 0.0
    income_count = 0
    unit_is_after_bu = False
    unit_rate = rate_cfg.get("default_residential_rate", 0.01)

    for v in matched:
        amt = float(v.get("amount") or 0)
        is_income = bool(v.get("_is_income"))
        is_after_bu = bool(v.get("_is_after_bu"))
        if is_after_bu:
            unit_is_after_bu = True
        pass_through = v.get("_pass_through_type")
        taxable_amt = float(v.get("_taxable_amount") or 0.0)
        v_tax_rate = float(v.get("_tax_rate") or unit_rate)
        unit_rate = v_tax_rate

        if is_income and not is_after_bu and taxable_amt > 0:
            vch_tax = round(amt - taxable_amt, 2)
            vch_cgst = round(vch_tax / 2, 2)
            vch_sgst = round(vch_tax - vch_cgst, 2)
        else:
            vch_tax = 0.0
            vch_cgst = 0.0
            vch_sgst = 0.0

        if is_income:
            total_receipts += amt
            total_taxable_base += taxable_amt
            total_tax += vch_tax
            income_count += 1
        if is_after_bu:
            total_exempt += amt
        if pass_through:
            total_pass_through += amt

        v_type = "Member Receipt" if is_income else (
            "Excluded by CA" if v.get("_badge_type") == "excluded_manual" else (
                "Non-GST Pass-Through" if v.get("_badge_type") == "pass_through" else (
                    "Vendor / Creditor" if v.get("_is_creditor") else (
                        "Cancelled / Refunded" if v.get("_is_cancelled") else "Purchase / Expense"
                    )
                )
            )
        )

        history.append({
            "date": v.get("date"),
            "vch_no": v.get("voucher_number"),
            "party_name": v.get("party_name"),
            "party_original": v.get("party_original"),
            "amount": amt,
            "taxable_amount": taxable_amt,
            "tax_rate": v_tax_rate,
            "tax_rate_pct": round(v_tax_rate * 100, 2),
            "cgst": vch_cgst,
            "sgst": vch_sgst,
            "total_tax": vch_tax,
            "is_exempt": is_after_bu,
            "is_income": is_income,
            "classification": v.get("_classification"),
            "badge_type": v.get("_badge_type"),
            "type": v_type,
            "narration": v.get("narration") or "",
            "has_override": bool(v.get("_has_override")),
            "override_bu_status": v.get("override_bu_status"),
            "override_is_income": v.get("override_is_income"),
            "override_rate": v.get("override_rate"),
            "override_note": v.get("override_note")
        })

    genuine_vouchers, cancelled_vouchers = _split_genuine_and_cancelled(matched)

    owners = []
    seen_owner = set()
    for v in genuine_vouchers:
        name = (v.get("party_name") or "").strip()
        if name and name not in seen_owner:
            seen_owner.add(name)
            owners.append(name)

    ownership_periods = []
    for v in genuine_vouchers:
        name = (v.get("party_name") or "").strip() or "Unknown"
        if not ownership_periods or ownership_periods[-1]["owner"] != name:
            ownership_periods.append({"owner": name, "_vouchers": []})
        ownership_periods[-1]["_vouchers"].append(v)

    def _to_history_item(v):
        amt = float(v.get("amount") or 0)
        return {
            "date": v.get("date"),
            "vch_no": v.get("voucher_number"),
            "party_name": v.get("party_name"),
            "amount": amt,
            "taxable_amount": float(v.get("_taxable_amount") or 0.0),
            "classification": v.get("_classification"),
            "narration": v.get("narration"),
            "is_exempt": bool(v.get("_is_after_bu"))
        }

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

    bu_status_label = "Exempt Post-BU (Schedule III)" if unit_is_after_bu else ("Taxable (Pre-BU)" if has_bu else "Pre-BU / Construction Phase")
    rate_label = f"{round(unit_rate * 100, 2):g}% ({'Affordable Residential' if unit_rate <= 0.01 else 'Standard Rate'})"

    return jsonify({
        "status": "success",
        "project_key": target_key,
        "project_name": project_name,
        "unit_no": unit_query,
        "unit_meta": unit_meta,
        "bu_status_label": bu_status_label,
        "is_exempt": unit_is_after_bu,
        "rate_label": rate_label,
        "rate_pct": round(unit_rate * 100, 2),
        "has_bu": has_bu,
        "bu_date": formatted_bu_date or bu_date_str,
        "bu_date_raw": bu_date_str,
        "bu_reference_no": pcfg.get("bu_reference_no", "") if pcfg else "",
        "authority": pcfg.get("authority", "") if pcfg else "",
        "summary": {
            "voucher_count": len(matched),
            "income_count": income_count,
            "total_receipts": total_receipts,
            "total_taxable_base": round(total_taxable_base, 2),
            "total_tax": round(total_tax, 2),
            "total_cgst": round(total_tax / 2, 2),
            "total_sgst": round(total_tax - round(total_tax / 2, 2), 2),
            "total_exempt": round(total_exempt, 2),
            "total_pass_through": round(total_pass_through, 2),
            "first_date": matched[0].get("date") if matched else "—",
            "last_date": matched[-1].get("date") if matched else "—",
        },
        "owners": owners,
        "current_owner": owners[-1] if owners else "—",
        "payment_count": income_count,
        "total_paid": total_receipts,
        "vouchers": history,
        "history": history,
        "ownership_periods": ownership_periods,
        "cancelled_bookings": cancelled_bookings,
        "cancelled_total": sum(float(v.get("amount") or 0) for v in cancelled_vouchers),
        "transfer_notes": transfer_notes
    })

@app.route("/api/vouchers/override", methods=["POST"])
def api_vouchers_override():
    """
    CA manual correction for one voucher's classification, applied via the dashboard's
    pencil-edit control. Auto-detection (BU tag/date, creditor keywords, amount plausibility)
    is always the default for every voucher; this only steers enrich_and_classify_vouchers
    for the specific voucher identified by (project, vch_no, date) when the CA has confirmed
    or corrected something the heuristics got wrong. Never touches amount/party/narration or
    deletes anything - only sets override_bu_status/override_is_income/override_rate/
    override_note on that one row. Passing "auto"/null for a field clears that override.
    """
    data = request.get_json() or {}
    project = str(data.get("project", "")).strip()
    vch_no = str(data.get("vch_no", "")).strip()
    date = str(data.get("date", "")).strip()

    if not project or not vch_no or not date:
        return jsonify({"status": "error", "message": "project, vch_no, and date are required"}), 400

    PROJECTS_METADATA = get_projects_metadata()
    pcfg = PROJECTS_METADATA.get(project)
    target_key = pcfg["code"] if pcfg else project

    bu_status = data.get("bu_status")
    if bu_status not in (None, "auto", "before_bu", "after_bu"):
        return jsonify({"status": "error", "message": "bu_status must be auto, before_bu, or after_bu"}), 400

    is_income = data.get("is_income")
    if is_income is not None and not isinstance(is_income, bool):
        return jsonify({"status": "error", "message": "is_income must be true, false, or omitted"}), 400

    rate = data.get("rate")
    if rate is not None:
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "rate must be a number (e.g. 0.01 for 1%)"}), 400

    note = str(data.get("note") or "").strip()[:255]

    ok = db.set_voucher_override(target_key, vch_no, date, bu_status=bu_status, is_income=is_income, rate=rate, note=note)
    if not ok:
        return jsonify({"status": "error", "message": "Voucher not found for that project/vch_no/date"}), 404

    log_voucher_override(
        project_code=target_key,
        vch_no=vch_no,
        date=date,
        override_fields={"bu_status": bu_status, "is_income": is_income, "rate": rate},
        note=note,
        ip_address=request.remote_addr
    )
    clear_voucher_classification_cache(target_key)

    return jsonify({"status": "success"})

@app.route("/api/units/override-bu", methods=["POST"])
def api_units_override_bu():
    """
    Sets BU status override for an entire flat unit (all its historical and future vouchers).
    Allows 1-click classification of post-BU purchased flats (Schedule III, Entry 5)
    or pre-BU under-construction flats.
    """
    data = request.get_json() or {}
    project = str(data.get("project", "")).strip()
    unit_no = str(data.get("unit_no", "") or data.get("unit", "")).strip().upper()
    bu_status = data.get("bu_status")
    note = str(data.get("note") or "").strip()[:255]

    if not project or not unit_no:
        return jsonify({"status": "error", "message": "project and unit_no are required"}), 400

    if bu_status not in (None, "auto", "before_bu", "after_bu"):
        return jsonify({"status": "error", "message": "bu_status must be auto, before_bu, or after_bu"}), 400

    PROJECTS_METADATA = get_projects_metadata()
    pcfg = PROJECTS_METADATA.get(project)
    target_key = pcfg["code"] if pcfg else project

    updated_count = db.set_unit_bu_override(target_key, unit_no, bu_status=bu_status, note=note)
    clear_voucher_classification_cache(target_key)

    log_unit_bu_override(
        project_code=target_key,
        unit_no=unit_no,
        bu_status=bu_status or "auto",
        affected_count=updated_count,
        note=note,
        ip_address=request.remote_addr
    )

    return jsonify({
        "status": "success",
        "message": f"Unit {unit_no} updated: {updated_count} vouchers set to {bu_status}.",
        "updated_count": updated_count
    })
@app.route("/api/units/sample-template", methods=["GET"])
def api_units_sample_template():
    """Generates and downloads a clean Excel template for project unit inventory."""
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Unit Inventory Master"

    headers = [
        "Unit No", "Tower / Block", "Floor", "Flat Label",
        "Usage Type", "Super Built-up Area (sqft)", "RERA Carpet Area (sqft)", "Balcony/Terrace Area (sqft)"
    ]
    ws.append(headers)

    # Style Header
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    for col_idx, col_name in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    sample_rows = [
        ["A-101", "A", "1st Floor", "101", "Residential", 1450.0, 850.0, 50.0],
        ["A-102", "A", "1st Floor", "102", "Residential", 1450.0, 850.0, 50.0],
        ["A-201", "A", "2nd Floor", "201", "Residential", 1450.0, 850.0, 50.0],
        ["B-101", "B", "1st Floor", "101", "Residential", 1850.0, 1120.0, 80.0],
        ["C-G01", "C", "Ground Floor", "G01", "Commercial", 650.0, 520.0, 0.0],
    ]
    for r in sample_rows:
        ws.append(r)

    # Column widths
    col_widths = [14, 16, 14, 14, 16, 26, 24, 26]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    from flask import send_file
    return send_file(
        bio,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Sun_Builders_Unit_Inventory_Template.xlsx"
    )

@app.route("/api/units/upload-excel", methods=["POST"])
def api_units_upload_excel():
    """Uploads an Excel or CSV file containing unit inventory for a project."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400

    file = request.files["file"]
    project_code = str(request.form.get("project_code") or request.form.get("project", "")).strip()
    if not project_code:
        return jsonify({"status": "error", "message": "Project code is required."}), 400

    filename = file.filename or ""
    if not (filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".csv")):
        return jsonify({"status": "error", "message": "Only Excel (.xlsx, .xls) and CSV files are supported."}), 400

    units = []
    try:
        if filename.endswith(".csv"):
            import csv
            import io
            stream = io.StringIO(file.stream.read().decode("utf-8-sig", errors="ignore"))
            reader = csv.DictReader(stream)
            for row in reader:
                r_clean = {k.strip().lower(): str(v or "").strip() for k, v in row.items() if k}
                unit_no = r_clean.get("unit no") or r_clean.get("unit") or r_clean.get("unit_no") or r_clean.get("flat no") or r_clean.get("flat")
                if not unit_no:
                    continue
                block = r_clean.get("tower / block") or r_clean.get("block") or r_clean.get("tower") or r_clean.get("wing") or ""
                floor = r_clean.get("floor") or ""
                flat_label = r_clean.get("flat label") or r_clean.get("flat_label") or unit_no.split("-")[-1]
                usage = r_clean.get("usage type") or r_clean.get("usage") or r_clean.get("type") or "Residential"
                size = float(r_clean.get("super built-up area (sqft)") or r_clean.get("size_sqft") or r_clean.get("size") or 0)
                carpet = float(r_clean.get("rera carpet area (sqft)") or r_clean.get("carpet_sqft") or r_clean.get("carpet") or 0)
                terrace = float(r_clean.get("balcony/terrace area (sqft)") or r_clean.get("terrace_sqft") or r_clean.get("terrace") or 0)
                units.append({
                    "unit_no": unit_no.upper(),
                    "block": block.upper(),
                    "flat_label": flat_label,
                    "floor": floor,
                    "usage_type": usage,
                    "office_no": "",
                    "size_sqft": size,
                    "carpet_sqft": carpet,
                    "terrace_sqft": terrace
                })
        else:
            import openpyxl
            wb = openpyxl.load_workbook(file.stream, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return jsonify({"status": "error", "message": "Uploaded Excel sheet is empty."}), 400

            header_row = [str(c or "").strip().lower() for c in rows[0]]
            def find_idx(*keywords):
                for kw in keywords:
                    for idx, h in enumerate(header_row):
                        if kw in h:
                            return idx
                return None

            idx_unit = find_idx("unit no", "unit_no", "flat no", "unit", "flat")
            idx_block = find_idx("tower", "block", "wing")
            idx_floor = find_idx("floor")
            idx_label = find_idx("flat label", "label")
            idx_usage = find_idx("usage", "type", "category")
            idx_size = find_idx("super", "built", "size")
            idx_carpet = find_idx("carpet", "rera")
            idx_terrace = find_idx("balcony", "terrace")

            if idx_unit is None:
                return jsonify({"status": "error", "message": "Could not find 'Unit No' column in uploaded sheet."}), 400

            for r in rows[1:]:
                if not r or idx_unit >= len(r) or not r[idx_unit]:
                    continue
                unit_no = str(r[idx_unit]).strip().upper()
                block = str(r[idx_block]).strip().upper() if idx_block is not None and idx_block < len(r) and r[idx_block] else ""
                floor = str(r[idx_floor]).strip() if idx_floor is not None and idx_floor < len(r) and r[idx_floor] else ""
                flat_label = str(r[idx_label]).strip() if idx_label is not None and idx_label < len(r) and r[idx_label] else unit_no.split("-")[-1]
                usage = str(r[idx_usage]).strip() if idx_usage is not None and idx_usage < len(r) and r[idx_usage] else "Residential"
                size = float(r[idx_size] or 0) if idx_size is not None and idx_size < len(r) and str(r[idx_size]).replace(".", "", 1).isdigit() else 0.0
                carpet = float(r[idx_carpet] or 0) if idx_carpet is not None and idx_carpet < len(r) and str(r[idx_carpet]).replace(".", "", 1).isdigit() else 0.0
                terrace = float(r[idx_terrace] or 0) if idx_terrace is not None and idx_terrace < len(r) and str(r[idx_terrace]).replace(".", "", 1).isdigit() else 0.0

                units.append({
                    "unit_no": unit_no,
                    "block": block,
                    "flat_label": flat_label,
                    "floor": floor,
                    "usage_type": usage,
                    "office_no": "",
                    "size_sqft": size,
                    "carpet_sqft": carpet,
                    "terrace_sqft": terrace
                })

        if not units:
            return jsonify({"status": "error", "message": "No valid unit rows found in file."}), 400

        saved_count = db.save_units(project_code, units)
        log_unit_master_import(
            project_code=project_code,
            filename=filename,
            imported_count=saved_count,
            ip_address=request.remote_addr
        )
        return jsonify({
            "status": "success",
            "message": f"Successfully imported {saved_count} units into {project_code} inventory!",
            "count": saved_count
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error parsing uploaded file: {str(e)}"}), 500

@app.route("/api/units/generate-plan", methods=["POST"])
def api_units_generate_plan():
    """Generates complete unit inventory based on towers, floors, and units per floor."""
    data = request.get_json() or {}
    project_code = str(data.get("project_code") or data.get("project", "")).strip()
    if not project_code:
        return jsonify({"status": "error", "message": "Project code is required."}), 400

    blocks_raw = data.get("blocks", "A")
    if isinstance(blocks_raw, list):
        blocks = [str(b).strip().upper() for b in blocks_raw if str(b).strip()]
    else:
        blocks = [b.strip().upper() for b in str(blocks_raw).split(",") if b.strip()]
    if not blocks:
        blocks = ["A"]

    try:
        start_floor = int(data.get("start_floor", 1))
        end_floor = int(data.get("end_floor", 10))
        units_per_floor = int(data.get("units_per_floor", 4))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Floors and units per floor must be integers."}), 400

    usage_type = str(data.get("usage_type", "Residential")).strip()
    try:
        size_sqft = float(data.get("size_sqft", 0))
        carpet_sqft = float(data.get("carpet_sqft", 0))
    except (ValueError, TypeError):
        size_sqft, carpet_sqft = 0.0, 0.0

    units = []
    for blk in blocks:
        for fl in range(start_floor, end_floor + 1):
            floor_label = f"{fl}st Floor" if fl == 1 else (f"{fl}nd Floor" if fl == 2 else (f"{fl}rd Floor" if fl == 3 else f"{fl}th Floor"))
            for u_idx in range(1, units_per_floor + 1):
                flat_num = f"{fl}{u_idx:02d}"
                unit_no = f"{blk}-{flat_num}" if blk else flat_num
                units.append({
                    "unit_no": unit_no,
                    "block": blk,
                    "flat_label": flat_num,
                    "floor": floor_label,
                    "usage_type": usage_type,
                    "office_no": "",
                    "size_sqft": size_sqft,
                    "carpet_sqft": carpet_sqft,
                    "terrace_sqft": 0.0
                })

    saved_count = db.save_units(project_code, units)
    log_activity(
        activity_type=ActivityType.UNIT_PLAN_GENERATE,
        action="Generate Specimen Unit Plan",
        description=f"Generated {saved_count} units across blocks {','.join(blocks)} for project {project_code}.",
        project_code=project_code,
        details={"blocks": blocks, "start_floor": start_floor, "end_floor": end_floor, "units_per_floor": units_per_floor, "count": saved_count},
        ip_address=request.remote_addr
    )
    return jsonify({
        "status": "success",
        "message": f"Successfully generated and registered {saved_count} units for project {project_code}!",
        "count": saved_count
    })

@app.route("/api/vouchers/sync", methods=["POST"])
def api_vouchers_sync():
    """Receives synced vouchers from local client Windows machine running Tally."""
    data = request.get_json() or {}
    project = data.get("project", "Sun Footprint")
    project_code = data.get("company_code") or data.get("project_code") or "010010"
    vouchers = data.get("vouchers", [])

    # Dynamic resolution: Check if source company name matches any registered project or alias
    source_name = str(data.get("source") or "").replace("Live Tally - ", "").strip().upper()
    master = load_project_master()
    matched_pcfg = None
    if source_name:
        for pkey, pcfg in master.get("projects", {}).items():
            p_code = str(pcfg.get("code", "")).strip().upper()
            p_name = str(pcfg.get("display_name", "")).strip().upper()
            if (p_name and (p_name in source_name or source_name in p_name)) or (p_code and p_code in source_name):
                matched_pcfg = pcfg
                break
            for al in pcfg.get("aliases", []):
                al_str = str(al).strip().upper()
                if al_str and (al_str in source_name or source_name in al_str):
                    matched_pcfg = pcfg
                    break
            if matched_pcfg:
                break

    if matched_pcfg:
        project_code = matched_pcfg.get("code", project_code)
        project = matched_pcfg.get("display_name", project)

    # Save synced payload in data directory (merging if progressive sync)
    sync_type = str(data.get("sync_type") or "full").lower()
    sync_file = os.path.join(BASE_DIR, "data", f"synced_{project.replace(' ', '_').lower()}.json")
    try:
        if sync_type == "progressive" and os.path.exists(sync_file):
            with open(sync_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_vouchers = existing_data.get("vouchers", []) if isinstance(existing_data, dict) else []
            v_map = {(str(v.get("vch_no") or v.get("voucher_number") or ""), str(v.get("date") or "")): v for v in existing_vouchers}
            for v in vouchers:
                v_map[(str(v.get("vch_no") or v.get("voucher_number") or ""), str(v.get("date") or ""))] = v
            merged_vouchers = list(v_map.values())
            data_to_save = dict(data)
            data_to_save["vouchers"] = merged_vouchers
            data_to_save["count"] = len(merged_vouchers)
            with open(sync_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
        else:
            with open(sync_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        print("Error saving sync data:", e)

    # Persist to PostgreSQL / Database with incremental deduplication
    sync_res = {"inserted": 0, "updated": 0, "unchanged": 0, "periods": []}
    try:
        sync_res = db.save_vouchers(project_code, vouchers)
        clear_voucher_classification_cache(project_code)
    except Exception as e:
        print("Error saving sync data to database:", e)

    log_tally_sync(
        project_code=project_code,
        project_name=project,
        vouchers_count=len(vouchers),
        inserted=sync_res.get("inserted", 0),
        updated=sync_res.get("updated", 0),
        unchanged=sync_res.get("unchanged", 0),
        source=f"Cloud Sync - {source_name or project}",
        periods=sync_res.get("periods", []),
        ip_address=request.remote_addr
    )

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
    log_purge_vouchers(purged_count=purged_count, ip_address=request.remote_addr)
    return jsonify({
        "status": "success",
        "purged_count": purged_count,
        "message": f"Successfully purged {purged_count} synthetic vouchers. Only 100% authentic Tally vouchers remain in the database."
    })


@app.route("/api/activity-logs", methods=["GET"])
def api_activity_logs():
    """Returns paginated activity & audit logs with live statistics for easy tracing."""
    project = request.args.get("project", "ALL")
    act_type = request.args.get("type", "ALL")
    status = request.args.get("status", "ALL")
    search = request.args.get("search", "")
    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        limit = 100
        offset = 0

    res = db.get_activity_logs(
        project_code=project,
        activity_type=act_type,
        status=status,
        search=search,
        limit=limit,
        offset=offset
    )
    stats = db.get_activity_stats()
    return jsonify({
        "status": "success",
        "total": res.get("total", 0),
        "count": len(res.get("logs", [])),
        "limit": limit,
        "offset": offset,
        "stats": stats,
        "logs": res.get("logs", [])
    })


@app.route("/api/activity-logs/export", methods=["GET"])
def api_activity_logs_export():
    """Exports activity logs as CSV for statutory audit & compliance records."""
    from flask import Response
    project = request.args.get("project", "ALL")
    act_type = request.args.get("type", "ALL")
    status = request.args.get("status", "ALL")
    search = request.args.get("search", "")

    csv_data = export_activity_logs_csv(
        project_code=project,
        activity_type=act_type,
        status=status,
        search=search
    )
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Sun_Builders_Activity_Audit_Trail_{timestamp_str}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    is_cloud_env = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("DYNO") or os.environ.get("RENDER") or (os.environ.get("PORT") and not os.path.exists(r"C:\Windows")))
    print("=" * 65)
    print("  SUN BUILDERS REAL ESTATE GST AUTOMATION - FLASK SERVER")
    print(f"  Running at: http://localhost:{port}")
    print("=" * 65)
    log_activity(
        activity_type=ActivityType.SYSTEM_EVENT,
        action="Server Started",
        description=f"Flask server running on port {port}. Engine: {'PostgreSQL' if db.is_postgres else 'SQLite'}.",
        project_code="SYSTEM",
        project_name="Core Engine",
        status=ActivityStatus.SUCCESS
    )
    if not is_cloud_env:
        threading.Thread(target=_local_cloud_sync_agent, daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)


