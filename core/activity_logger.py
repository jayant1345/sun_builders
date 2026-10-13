import os
import sys
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import csv
import io

from core.db import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
LOG_FILE = os.path.join(DATA_DIR, "activity.log")

# Setup file logger for forensic / server-side activity tracing
file_logger = logging.getLogger("sun_builders_activity")
file_logger.setLevel(logging.INFO)

if not file_logger.handlers:
    # Rotating file handler (5 MB per file, max 5 backups)
    rfh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    rfh.setFormatter(formatter)
    file_logger.addHandler(rfh)
    
    # Safe console handler that handles Windows cp1252/terminal encoding
    class SafeStreamHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                msg = self.format(record)
                stream = self.stream
                try:
                    stream.write(msg + self.terminator)
                except UnicodeEncodeError:
                    safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
                    stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)

    ch = SafeStreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[ACTIVITY] %(asctime)s - %(message)s", datefmt="%H:%M:%S"))
    file_logger.addHandler(ch)


class ActivityType:
    TALLY_SYNC = "TALLY_SYNC"
    GSTR_GENERATE = "GSTR_GENERATE"
    BU_DATE_UPDATE = "BU_DATE_UPDATE"
    VOUCHER_OVERRIDE = "VOUCHER_OVERRIDE"
    UNIT_BU_OVERRIDE = "UNIT_BU_OVERRIDE"
    UNIT_MASTER_IMPORT = "UNIT_MASTER_IMPORT"
    UNIT_PLAN_GENERATE = "UNIT_PLAN_GENERATE"
    PURGE_VOUCHERS = "PURGE_VOUCHERS"
    REPORT_DOWNLOAD = "REPORT_DOWNLOAD"
    PROJECT_CONFIG = "PROJECT_CONFIG"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class ActivityStatus:
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    INFO = "INFO"


def log_activity(
    activity_type: str,
    action: str,
    description: str,
    project_code: str = None,
    project_name: str = None,
    details: dict = None,
    status: str = ActivityStatus.SUCCESS,
    ip_address: str = None,
    user_agent: str = None
):
    """
    Core function to record any business or system activity.
    Saves to:
    1. Persistent database table `activity_logs` (PostgreSQL / SQLite) for instant UI retrieval
    2. Persistent rotating log file `data/activity.log` for file-based tracing & compliance
    """
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_iso = now.isoformat()

    # Log to file
    details_str = json.dumps(details, default=str) if details else ""
    log_msg = f"[{activity_type}] [{action}] Project: {project_code or 'GLOBAL'} | Status: {status} | {description}"
    if details_str:
        log_msg += f" | Details: {details_str}"

    if status == ActivityStatus.ERROR:
        file_logger.error(log_msg)
    elif status == ActivityStatus.WARNING:
        file_logger.warning(log_msg)
    else:
        file_logger.info(log_msg)

    # Insert to database
    try:
        db.insert_activity_log(
            activity_type=activity_type,
            action=action,
            description=description,
            project_code=project_code,
            project_name=project_name,
            details=details,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=created_at,
            timestamp_iso=timestamp_iso
        )
    except Exception as e:
        file_logger.error(f"Failed to persist activity log to database: {e}")


def log_tally_sync(
    project_code: str,
    project_name: str,
    vouchers_count: int,
    inserted: int,
    updated: int,
    unchanged: int,
    source: str = "Live Tally Port 9000",
    status: str = ActivityStatus.SUCCESS,
    periods: list = None,
    ip_address: str = None,
    error_msg: str = None
):
    if error_msg:
        desc = f"Tally sync failed for {project_name} ({project_code}): {error_msg}"
        status = ActivityStatus.ERROR
    else:
        desc = f"Tally sync for {project_name} ({project_code}): +{inserted} new, {updated} updated, {unchanged} verified unchanged ({vouchers_count} total scanned)."
    
    details = {
        "source": source,
        "scanned_count": vouchers_count,
        "new_inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "periods": periods or [],
        "error": error_msg
    }
    log_activity(
        activity_type=ActivityType.TALLY_SYNC,
        action="Sync Tally Vouchers",
        description=desc,
        project_code=project_code,
        project_name=project_name,
        details=details,
        status=status,
        ip_address=ip_address
    )


def log_gstr_generation(
    month: str,
    filename: str,
    summary: dict,
    logs_count: int,
    ip_address: str = None
):
    gross = summary.get("gross_receipts", 0)
    units_cnt = summary.get("total_units", 0)
    desc = f"Generated GSTR-1 workbook for tax period {month}: {filename} ({units_cnt} units, Gross ₹{gross:,.2f})"
    details = {
        "month": month,
        "filename": filename,
        "total_units": units_cnt,
        "gross_receipts": gross,
        "taxable_receipts": summary.get("taxable_receipts", 0),
        "exempt_post_bu": summary.get("exempt_post_bu", 0),
        "tax_due": summary.get("tax_due", 0),
        "step_logs_count": logs_count
    }
    log_activity(
        activity_type=ActivityType.GSTR_GENERATE,
        action=f"Generate GSTR-1 ({month})",
        description=desc,
        project_code="ALL",
        project_name="Consolidated Entity",
        details=details,
        status=ActivityStatus.SUCCESS,
        ip_address=ip_address
    )


def log_bu_update(
    project_code: str,
    project_name: str,
    old_date: str,
    new_date: str,
    old_status: str,
    new_status: str,
    reference_no: str = "",
    authority: str = "",
    ip_address: str = None
):
    desc = f"Updated BU Permission settings for {project_name} ({project_code}): Date changed from '{old_date or 'None'}' to '{new_date or 'None'}' ({new_status})."
    details = {
        "old_bu_date": old_date,
        "new_bu_date": new_date,
        "old_status": old_status,
        "new_status": new_status,
        "reference_no": reference_no,
        "authority": authority
    }
    log_activity(
        activity_type=ActivityType.BU_DATE_UPDATE,
        action="Update BU Permission Date",
        description=desc,
        project_code=project_code,
        project_name=project_name,
        details=details,
        status=ActivityStatus.SUCCESS,
        ip_address=ip_address
    )


def log_voucher_override(
    project_code: str,
    vch_no: str,
    date: str,
    override_fields: dict,
    note: str = "",
    ip_address: str = None
):
    desc = f"CA manual override applied on voucher #{vch_no} dated {date} for project {project_code}: {', '.join(f'{k}={v}' for k, v in override_fields.items() if v is not None)}"
    if note:
        desc += f" (Note: {note})"
    details = {
        "vch_no": vch_no,
        "date": date,
        "overrides": override_fields,
        "note": note
    }
    log_activity(
        activity_type=ActivityType.VOUCHER_OVERRIDE,
        action="Voucher Override",
        description=desc,
        project_code=project_code,
        project_name="",
        details=details,
        status=ActivityStatus.SUCCESS,
        ip_address=ip_address
    )


def log_unit_bu_override(
    project_code: str,
    unit_no: str,
    bu_status: str,
    affected_count: int,
    note: str = "",
    ip_address: str = None
):
    desc = f"CA unit BU status override applied on Unit {unit_no} ({project_code}): set to '{bu_status}' across {affected_count} historical/future vouchers."
    if note:
        desc += f" (Note: {note})"
    details = {
        "unit_no": unit_no,
        "bu_status": bu_status,
        "vouchers_updated": affected_count,
        "note": note
    }
    log_activity(
        activity_type=ActivityType.UNIT_BU_OVERRIDE,
        action="Unit BU Override",
        description=desc,
        project_code=project_code,
        project_name="",
        details=details,
        status=ActivityStatus.SUCCESS,
        ip_address=ip_address
    )


def log_unit_master_import(
    project_code: str,
    filename: str,
    imported_count: int,
    ip_address: str = None
):
    desc = f"Imported unit inventory layout from file '{filename}': {imported_count} units registered into project {project_code}."
    details = {
        "filename": filename,
        "imported_units": imported_count
    }
    log_activity(
        activity_type=ActivityType.UNIT_MASTER_IMPORT,
        action="Import Unit Master Excel",
        description=desc,
        project_code=project_code,
        project_name="",
        details=details,
        status=ActivityStatus.SUCCESS,
        ip_address=ip_address
    )


def log_report_download(
    filename: str,
    ip_address: str = None
):
    desc = f"Downloaded GST Workbook report: {filename}"
    details = {"filename": filename}
    log_activity(
        activity_type=ActivityType.REPORT_DOWNLOAD,
        action="Download Report",
        description=desc,
        project_code="ALL",
        project_name="GST Workbook",
        details=details,
        status=ActivityStatus.INFO,
        ip_address=ip_address
    )


def log_purge_vouchers(
    purged_count: int,
    ip_address: str = None
):
    desc = f"Purged {purged_count} synthetic Excel-extracted vouchers from database."
    details = {"purged_count": purged_count}
    log_activity(
        activity_type=ActivityType.PURGE_VOUCHERS,
        action="Purge Synthetic Vouchers",
        description=desc,
        project_code="GLOBAL",
        project_name="Database",
        details=details,
        status=ActivityStatus.SUCCESS if purged_count > 0 else ActivityStatus.INFO,
        ip_address=ip_address
    )


def export_activity_logs_csv(project_code=None, activity_type=None, status=None, search=None):
    """
    Exports activity logs to CSV format for CA compliance and audit records.
    """
    res = db.get_activity_logs(
        project_code=project_code,
        activity_type=activity_type,
        status=status,
        search=search,
        limit=5000,
        offset=0
    )
    logs = res.get("logs", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Log ID", "Date & Time", "Activity Category", "Action",
        "Project Code", "Project Name", "Status", "Activity Summary", "Detailed Parameters", "IP Address"
    ])

    for row in logs:
        writer.writerow([
            row.get("id", ""),
            row.get("created_at", ""),
            row.get("activity_type", ""),
            row.get("action", ""),
            row.get("project_code", ""),
            row.get("project_name", ""),
            row.get("status", ""),
            row.get("description", ""),
            row.get("details", ""),
            row.get("ip_address", "")
        ])

    output.seek(0)
    return output.getvalue()
