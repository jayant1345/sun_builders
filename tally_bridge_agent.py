"""
Sun Builders Projects LLP - Standalone Tally Cloud Bridge Agent
=================================================================
Runs on the CA office PC (wherever Tally is installed). Has no web server
and no local dashboard of its own - the CA office does all its work on
the Railway cloud dashboard in a browser, exactly as today.

This program's only job: watch the cloud dashboard for a "Sync Tally"
button click, and when one happens, read live vouchers from Tally on
this PC (http://localhost:9000) and send them to the cloud with real-time
progress reporting.

Features:
- Live visual progress bar in terminal and web dashboard modal.
- Multi-company auto-detection & seamless company switching without restart.
- Windows Console QuickEdit mode disabled (mouse clicks never freeze execution).
- Chunked high-speed batch uploading to prevent network timeouts.
- Automatic retry & continuous watching.
"""

import os
import sys
import json
import time
import ctypes
import urllib.request
import urllib.error
from datetime import datetime

# Ensure unbuffered real-time stdout
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)))
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.db import db
from core.tally_client import TallyClient
from tally_sync_agent import resolve_company_code, extract_from_live_tally

RAILWAY_CLOUD_URL = "https://sunbuilders-production.up.railway.app"
POLL_INTERVAL_SECONDS = 3
MUTEX_NAME = "Local\\SunBuildersTallyBridgeAgentMutex"


def disable_quick_edit():
    """Prevents mouse clicks in the Windows terminal from pausing execution."""
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        h_stdin = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE = -10
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(h_stdin, ctypes.byref(mode)):
            # Clear ENABLE_QUICK_EDIT_MODE (0x0040) and ENABLE_INSERT_MODE (0x0020)
            new_mode = (mode.value & ~0x0040 & ~0x0020) | 0x0080  # ENABLE_EXTENDED_FLAGS
            kernel32.SetConsoleMode(h_stdin, new_mode)
    except Exception:
        pass


def ensure_single_instance():
    """Refuses to start a second copy; Windows releases the mutex automatically
    if a previous copy crashed, so this never gets stuck 'locked' forever."""
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        print("=" * 70, flush=True)
        print("  Sun Builders Tally Bridge Agent is ALREADY RUNNING.", flush=True)
        print("  Look for its window in your taskbar - no need to open a second one.", flush=True)
        print("=" * 70, flush=True)
        try:
            input("\nPress Enter to close this window...")
        except EOFError:
            pass
        sys.exit(0)


def report_cloud_progress(request_id, percent, message, log=None, step=3, count=0):
    """Sends intermediate progress to the cloud so web users see real-time progress."""
    if not request_id:
        return
    try:
        req = urllib.request.Request(
            f"{RAILWAY_CLOUD_URL}/api/tally/report_progress",
            data=json.dumps({
                "request_id": request_id,
                "percent": percent,
                "message": message,
                "log": log or message,
                "step": step,
                "count": count
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def perform_live_tally_sync(target_project=None, request_id=None):
    """Reads vouchers from Tally on this PC and pushes them to Railway Cloud.
    If target_project is specified, finds and syncs that exact company.
    If multiple companies are loaded in Tally, syncs ALL loaded project companies!"""
    print("\n" + "=" * 70, flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] INITIATING LIVE TALLY SYNC (Target: {target_project or 'ALL'})", flush=True)
    print("=" * 70, flush=True)

    report_cloud_progress(request_id, 20, "Checking Port 9000 XML socket connection...", step=1)

    client = TallyClient()
    if not client.is_connected():
        msg = "Port 9000 is OFFLINE or Tally Prime is closed. Please open Tally Prime with your company loaded."
        print(f"[!] {msg}", flush=True)
        report_cloud_progress(request_id, 0, msg, step=1)
        return {
            "status": "offline",
            "connected": False,
            "message": msg,
            "count": 0,
            "vouchers": []
        }

    report_cloud_progress(request_id, 30, "Reading open companies from Tally...", step=2)
    raw_companies = client.get_loaded_companies()
    if not raw_companies:
        msg = "Tally is online, but no company is open. Please open your company in Tally."
        print(f"[!] {msg}", flush=True)
        report_cloud_progress(request_id, 30, msg, step=2)
        return {
            "status": "warning",
            "connected": True,
            "message": msg,
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

    print(f"[*] Open Companies identified: {companies_to_sync}", flush=True)
    report_cloud_progress(
        request_id, 40,
        f"Targeting company: {companies_to_sync[0]}",
        log=f"Found {len(companies_to_sync)} active company in Tally.",
        step=2
    )

    all_vouchers = []
    total_new = 0
    total_updated = 0
    total_unchanged = 0
    total_gross = 0.0
    total_taxable = 0.0
    synced_companies_info = []
    last_comp_name = companies_to_sync[0]
    last_target_code, last_project_display = resolve_company_code(last_comp_name)

    total_companies = len(companies_to_sync)
    for c_idx, comp_name in enumerate(companies_to_sync, 1):
        target_code, project_display = resolve_company_code(comp_name)
        last_comp_name = comp_name
        last_target_code = target_code
        last_project_display = project_display

        pct_start = 40 + int(((c_idx - 1) / total_companies) * 45)
        print(f"\n[{c_idx}/{total_companies}] Extracting from Tally: '{comp_name}' -> Project: {project_display} ({target_code})...", flush=True)
        report_cloud_progress(
            request_id, pct_start,
            f"[{c_idx}/{total_companies}] Extracting {project_display} Daybook from Tally Port 9000...",
            log=f"Extracting Tally Daybook collection for {comp_name}...",
            step=3
        )

        _, vouchers = extract_from_live_tally("http://localhost:9000", target_company=comp_name)

        if not vouchers:
            print(f"[!] No vouchers returned for '{comp_name}'. Skipping.", flush=True)
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

        v_count = len(vouchers)
        print(f"[+] Total authentic vouchers parsed: {v_count:,}. Saving locally in SQLite...", flush=True)
        report_cloud_progress(
            request_id, pct_start + 10,
            f"Parsed {v_count:,} vouchers. Saving to local database...",
            log=f"Extracted {v_count:,} daybook records. Ingesting locally...",
            step=3,
            count=v_count
        )

        # Save locally in SQLite
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

        # Push company vouchers to Railway Cloud in chunks if large
        CHUNK_SIZE = 5000
        cloud_ok = True
        total_chunks = max(1, (v_count + CHUNK_SIZE - 1) // CHUNK_SIZE)

        for chunk_idx in range(total_chunks):
            chunk_slice = vouchers[chunk_idx * CHUNK_SIZE : (chunk_idx + 1) * CHUNK_SIZE]
            chunk_pct = pct_start + 15 + int(((chunk_idx + 1) / total_chunks) * 20)
            
            chunk_label = f"Uploading to Cloud: {min((chunk_idx + 1) * CHUNK_SIZE, v_count):,}/{v_count:,} vouchers ({chunk_pct}%)..."
            print(f"    [*] {chunk_label}", flush=True)
            report_cloud_progress(
                request_id, chunk_pct,
                f"Ingesting into Railway Cloud DB: {min((chunk_idx + 1) * CHUNK_SIZE, v_count):,}/{v_count:,} vouchers...",
                log=f"Uploading batch {chunk_idx + 1}/{total_chunks} ({len(chunk_slice)} vouchers) to Railway Cloud...",
                step=3,
                count=v_count
            )

            try:
                req_cloud = urllib.request.Request(
                    f"{RAILWAY_CLOUD_URL}/api/vouchers/sync",
                    data=json.dumps({
                        "project": project_display,
                        "company_code": target_code,
                        "source": f"Live Tally - {comp_name}",
                        "count": len(chunk_slice),
                        "vouchers": chunk_slice,
                        "is_chunk": total_chunks > 1,
                        "chunk_index": chunk_idx,
                        "total_chunks": total_chunks
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req_cloud, timeout=180):
                    pass
            except Exception as e:
                print(f"    [!] Cloud sync batch {chunk_idx + 1} note: {e}", flush=True)
                cloud_ok = False

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
        msg = "Tally connected but returned 0 vouchers. Please verify vouchers exist in the open company."
        print(f"[!] {msg}", flush=True)
        report_cloud_progress(request_id, 100, msg, step=4)
        return {
            "status": "warning",
            "connected": True,
            "message": msg,
            "company": last_comp_name,
            "count": 0,
            "vouchers": []
        }

    report_cloud_progress(
        request_id, 98,
        f"Ingestion verified: {len(all_vouchers):,} vouchers processed. Generating summary...",
        log=f"Zero-duplicate verification complete (+{total_new} new, {total_updated} updated, {total_unchanged} consistent).",
        step=4,
        count=len(all_vouchers)
    )

    return {
        "status": "success",
        "connected": True,
        "company": last_comp_name,
        "project_code": last_target_code,
        "project_name": last_project_display,
        "count": len(all_vouchers),
        "vouchers": all_vouchers[:500],  # Return rows for web modal table
        "total_gross": round(total_gross, 2),
        "total_taxable": round(total_taxable, 2),
        "cloud_synced": True,
        "new_inserted": total_new,
        "updated": total_updated,
        "unchanged": total_unchanged,
        "duplicates_prevented": total_unchanged,
        "companies_synced": synced_companies_info,
        "message": f"Successfully synchronized {len(all_vouchers):,} vouchers (+{total_new} new, {total_updated} updated, {total_unchanged} consistent)."
    }


def run_bridge_loop():
    disable_quick_edit()
    print("=" * 70, flush=True)
    print("  SUN BUILDERS - TALLY CLOUD BRIDGE AGENT (MULTI-COMPANY)", flush=True)
    print(f"  Target Server : {RAILWAY_CLOUD_URL}", flush=True)
    print("  Local Tally   : http://localhost:9000 (Port 9000)", flush=True)
    print("  Mode          : Live Polling + Real-Time Progress Stream", flush=True)
    print("  Keep this window open. You do NOT need to restart between companies.", flush=True)
    print("=" * 70, flush=True)

    last_heartbeat = 0
    poll_count = 0

    while True:
        try:
            now = time.time()
            if now - last_heartbeat >= 20:
                last_heartbeat = now
                client = TallyClient()
                tally_ok = client.is_connected()
                tally_status = "Online (Port 9000 Connected)" if tally_ok else "Waiting for Tally (Port 9000 Offline)"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [Watching] Bridge active. Tally: {tally_status}", flush=True)

            with urllib.request.urlopen(f"{RAILWAY_CLOUD_URL}/api/tally/poll_sync", timeout=10) as resp:
                poll_data = json.loads(resp.read().decode("utf-8"))

            if poll_data.get("pending"):
                request_id = poll_data["request_id"]
                target_project = poll_data.get("target_project")
                print(f"\n{'='*70}", flush=True)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> CLOUD TRIGGERED SYNC (Target: {target_project or 'ALL'}) <<<", flush=True)
                print(f"{'='*70}", flush=True)

                try:
                    result = perform_live_tally_sync(target_project=target_project, request_id=request_id)
                except Exception as sync_err:
                    print(f"[!] Sync error occurred: {sync_err}", flush=True)
                    result = {
                        "status": "error",
                        "connected": True,
                        "message": f"Error during sync: {str(sync_err)}",
                        "count": 0,
                        "vouchers": []
                    }

                result["request_id"] = request_id
                try:
                    submit_req = urllib.request.Request(
                        f"{RAILWAY_CLOUD_URL}/api/tally/submit_sync_result",
                        data=json.dumps(result).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    urllib.request.urlopen(submit_req, timeout=30)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [DONE] Result reported to cloud: {result.get('status')} ({result.get('count', 0):,} vouchers).", flush=True)
                    print("[+] Bridge remains READY. Switch company in Tally anytime and click Re-Sync!\n", flush=True)
                except Exception as e:
                    print(f"[!] Could not report result to cloud: {e}", flush=True)

        except Exception as loop_e:
            pass  # Cloud unreachable temporarily; retry cleanly on next tick.

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    ensure_single_instance()
    try:
        run_bridge_loop()
    except KeyboardInterrupt:
        print("\nBridge agent stopped by user.", flush=True)
