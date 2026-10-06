"""
Sun Builders Projects LLP - Standalone Tally Cloud Bridge Agent
=================================================================
Runs on the CA office PC (wherever Tally is installed). Has no web server
and no local dashboard of its own - the CA office does all its work on
the Railway cloud dashboard in a browser, exactly as today.

This program's only job: watch the cloud dashboard for a "Sync Tally"
button click, and when one happens, read live vouchers from Tally on
this PC (http://localhost:9000) and send them to the cloud.

Supports MULTI-COMPANY: Automatically detects all loaded companies in Tally
and syncs each project, or targets the specific project selected on screen.
"""

import os
import sys
import json
import time
import ctypes
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)))
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.db import db
from core.tally_client import TallyClient
from tally_sync_agent import resolve_company_code, extract_from_live_tally

RAILWAY_CLOUD_URL = "https://sunbuilders-production.up.railway.app"
POLL_INTERVAL_SECONDS = 4
MUTEX_NAME = "Local\\SunBuildersTallyBridgeAgentMutex"


def ensure_single_instance():
    """Refuses to start a second copy; Windows releases the mutex automatically
    if a previous copy crashed, so this never gets stuck 'locked' forever."""
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        print("=" * 70)
        print("  Sun Builders Tally Bridge Agent is ALREADY RUNNING.")
        print("  Look for its window in your taskbar - no need to open a second one.")
        print("=" * 70)
        try:
            input("\nPress Enter to close this window...")
        except EOFError:
            pass
        sys.exit(0)


def perform_live_tally_sync(target_project=None):
    """Reads vouchers from Tally on this PC and pushes them to Railway Cloud.
    If target_project is specified, finds and syncs that exact company.
    If multiple companies are loaded in Tally, syncs ALL loaded project companies!"""
    client = TallyClient()
    if not client.is_connected():
        return {
            "status": "offline",
            "connected": False,
            "message": "Port 9000 is OFFLINE or Tally is closed. Please open Tally with your company loaded.",
            "count": 0,
            "vouchers": []
        }

    raw_companies = client.get_loaded_companies()
    if not raw_companies:
        return {
            "status": "warning",
            "connected": True,
            "message": "Tally is online, but no company is open. Please open your company in Tally.",
            "count": 0,
            "vouchers": []
        }

    # Deduplicate company names while preserving order
    unique_companies = []
    seen = set()
    for c in raw_companies:
        c_clean = (c or "").strip()
        if c_clean and c_clean not in seen:
            seen.add(c_clean)
            unique_companies.append(c_clean)

    # Determine which companies to sync
    companies_to_sync = []
    if target_project and target_project != "ALL":
        for comp in unique_companies:
            code, _ = resolve_company_code(comp)
            if code == target_project:
                companies_to_sync.append(comp)

    # If no target specified or targeted project isn't among loaded, sync all loaded
    if not companies_to_sync:
        companies_to_sync = unique_companies

    print(f"[*] Companies identified for sync: {companies_to_sync}")

    all_vouchers = []
    total_new = 0
    total_updated = 0
    total_unchanged = 0
    total_gross = 0.0
    total_taxable = 0.0
    synced_companies_info = []
    last_comp_name = companies_to_sync[0]
    last_target_code, last_project_display = resolve_company_code(last_comp_name)

    for comp_name in companies_to_sync:
        target_code, project_display = resolve_company_code(comp_name)
        last_comp_name = comp_name
        last_target_code = target_code
        last_project_display = project_display

        print(f"[*] Extracting: '{comp_name}' -> Project: {project_display} ({target_code})...")
        _, vouchers = extract_from_live_tally("http://localhost:9000", target_company=comp_name)

        if not vouchers:
            print(f"[!] No vouchers returned for '{comp_name}'. Skipping.")
            continue

        # In-memory deduplication for this company
        unique_vchs = []
        seen_keys = set()
        for v in vouchers:
            v_key = (
                str(v.get("vch_no", "")).strip().lower(),
                str(v.get("date", "")).strip(),
                round(float(v.get("cr_amount", 0) or 0), 2),
                str(v.get("member_name", "")).strip().lower(),
            )
            if v_key in seen_keys:
                continue
            seen_keys.add(v_key)
            unique_vchs.append(v)
        vouchers = unique_vchs

        # Save locally in SQLite & JSON cache
        sync_res = db.save_vouchers(target_code, vouchers)
        total_new += sync_res.get("inserted", 0)
        total_updated += sync_res.get("updated", 0)
        total_unchanged += sync_res.get("unchanged", len(vouchers))

        sync_file = os.path.join(BASE_DIR, "data", f"synced_{project_display.replace(' ', '_').lower()}.json")
        try:
            os.makedirs(os.path.dirname(sync_file), exist_ok=True)
            with open(sync_file, "w", encoding="utf-8") as f:
                json.dump({
                    "project": project_display,
                    "company_code": target_code,
                    "company_name": comp_name,
                    "synced_at": datetime.now().isoformat(),
                    "vouchers": vouchers,
                }, f, indent=2)
        except Exception:
            pass

        # Push company vouchers to Railway Cloud
        cloud_ok = False
        try:
            req_cloud = urllib.request.Request(
                f"{RAILWAY_CLOUD_URL}/api/vouchers/sync",
                data=json.dumps({
                    "project": project_display,
                    "company_code": target_code,
                    "source": f"Live Tally - {comp_name}",
                    "count": len(vouchers),
                    "vouchers": vouchers,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req_cloud, timeout=40):
                cloud_ok = True
        except Exception as e:
            print(f"[Cloud Sync Note for {comp_name}]: {e}")

        for v in vouchers:
            total_gross += float(v.get("cr_amount", 0) or 0)
            total_taxable += float(v.get("taxable_amount", 0) or v.get("cr_amount", 0) or 0)

        synced_companies_info.append({
            "company": comp_name,
            "project_name": project_display,
            "project_code": target_code,
            "count": len(vouchers),
            "cloud_synced": cloud_ok
        })
        all_vouchers.extend(vouchers)

    if not all_vouchers:
        return {
            "status": "warning",
            "connected": True,
            "message": "Tally connected but returned no vouchers. Please verify vouchers exist in the open company.",
            "company": last_comp_name,
            "count": 0,
            "vouchers": []
        }

    return {
        "status": "success",
        "connected": True,
        "company": last_comp_name,
        "project_code": last_target_code,
        "project_name": last_project_display,
        "count": len(all_vouchers),
        "vouchers": all_vouchers[:500],  # Return rows so web modal displays table
        "total_gross": round(total_gross, 2),
        "total_taxable": round(total_taxable, 2),
        "cloud_synced": True,
        "new_inserted": total_new,
        "updated": total_updated,
        "unchanged": total_unchanged,
        "companies_synced": synced_companies_info
    }


def run_bridge_loop():
    print("=" * 70)
    print("  SUN BUILDERS - TALLY CLOUD BRIDGE AGENT (MULTI-COMPANY)")
    print(f"  Watching: {RAILWAY_CLOUD_URL}")
    print("  Keep this window open. Minimize it if you like - do not close it.")
    print("  Use the cloud dashboard in your browser for everything else.")
    print("=" * 70)

    while True:
        try:
            with urllib.request.urlopen(f"{RAILWAY_CLOUD_URL}/api/tally/poll_sync", timeout=10) as resp:
                poll_data = json.loads(resp.read().decode("utf-8"))

            if poll_data.get("pending"):
                request_id = poll_data["request_id"]
                target_project = poll_data.get("target_project")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Cloud requested sync (target={target_project or 'ALL'}). Reading Tally...")
                result = perform_live_tally_sync(target_project=target_project)
                result["request_id"] = request_id
                try:
                    submit_req = urllib.request.Request(
                        f"{RAILWAY_CLOUD_URL}/api/tally/submit_sync_result",
                        data=json.dumps(result).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    urllib.request.urlopen(submit_req, timeout=20)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done: {result.get('status')}, {result.get('count', 0)} vouchers synced to cloud.")
                except Exception as e:
                    print(f"[!] Could not report result to cloud: {e}")
        except Exception:
            pass  # Cloud unreachable right now; just retry on the next tick.
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    ensure_single_instance()
    try:
        run_bridge_loop()
    except KeyboardInterrupt:
        print("\nStopped.")
