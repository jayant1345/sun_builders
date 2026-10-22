import os
import re
import json
import sqlite3
from datetime import datetime
from urllib.parse import urlparse


def _parse_unit_and_name(raw_text):
    """Splits a raw Tally ledger name into (flat/unit code, owner name(s)).
    Stops the flat-code capture right after the unit digits, so a ledger like
    'I-803-Neetaben Trivedi - After BU' (multiple owners glued with a hyphen,
    no comma) correctly yields unit='I-803' and name='Neetaben Trivedi - After BU'
    instead of swallowing the first owner's name into the flat code.
    """
    if not raw_text:
        return "", ""
    raw = str(raw_text).replace('_x000D_\n', ' ').replace('_x000D_', ' ').strip()

    m = re.match(r'^([A-Za-z]{1,4})\s*[\-_/,\s]\s*(\d{1,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m:
        unit = f"{m.group(1).upper()}-{m.group(2)}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name

    m2 = re.match(r'^([A-Za-z]{1,4})(\d{2,5}[A-Za-z]?)\s*[,;.:\-]*\s*(.*)$', raw)
    if m2:
        unit = f"{m2.group(1).upper()}-{m2.group(2)}"
        rest_name = re.sub(r'^[,;.:\-\s]+', '', m2.group(3).strip()).strip()
        rest_name = re.sub(r'\s+', ' ', rest_name)
        return unit, rest_name

    for sep in [',', ';', '-']:
        if sep in raw:
            p0, p1 = raw.split(sep, 1)
            p0, p1 = p0.strip(), p1.strip()
            if len(p0) <= 8 and any(ch.isdigit() for ch in p0):
                return p0, p1

    return "", raw

# Optional psycopg2 import
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class SyncResult(dict):
    """Result dictionary that also supports arithmetic addition and boolean checks."""
    def __int__(self):
        return self.get("inserted", 0) + self.get("updated", 0)

    def __add__(self, other):
        return int(self) + int(other)

    def __radd__(self, other):
        return int(other) + int(self)

    def __repr__(self):
        return f"<SyncResult new={self.get('inserted',0)}, updated={self.get('updated',0)}, unchanged={self.get('unchanged',0)}, total={self.get('total',0)}>"


class DatabaseManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
        
        # Railway / Heroku postgres URL compatibility (postgres:// -> postgresql://)
        if self.db_url and self.db_url.startswith("postgres://"):
            self.db_url = "postgresql://" + self.db_url[len("postgres://"):]
            
        self.is_postgres = bool(self.db_url and PSYCOPG2_AVAILABLE)
        self.sqlite_path = os.path.join(self.base_dir, "data", "sun_builders.db")
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)
        
        print(f"[DatabaseManager] Initialized. Engine: {'PostgreSQL' if self.is_postgres else 'SQLite'}")
        self.init_db()
        self.purge_fake_vouchers()

    def get_connection(self):
        if self.is_postgres:
            return psycopg2.connect(self.db_url)
        else:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            return conn

    def init_db(self):
        """Create projects and vouchers tables if they do not exist."""
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS projects (
                            code VARCHAR(20) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            project_type VARCHAR(100),
                            gst_rate VARCHAR(20) DEFAULT '1%',
                            bu_status VARCHAR(50) DEFAULT 'under_construction',
                            bu_date VARCHAR(20),
                            bu_ref VARCHAR(255),
                            bu_authority VARCHAR(255),
                            notes TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS vouchers (
                            id SERIAL PRIMARY KEY,
                            project_code VARCHAR(20) NOT NULL,
                            voucher_number VARCHAR(100) NOT NULL,
                            date VARCHAR(50),
                            party_name VARCHAR(255),
                            party_original VARCHAR(255),
                            block_no VARCHAR(50),
                            unit_no VARCHAR(50),
                            amount NUMERIC(15, 2) DEFAULT 0,
                            classification VARCHAR(100),
                            gst_rate VARCHAR(20),
                            narration TEXT,
                            is_exempt BOOLEAN DEFAULT FALSE,
                            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT unq_vch UNIQUE (project_code, voucher_number, date, amount)
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_vch_project ON vouchers(project_code);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS units (
                            id SERIAL PRIMARY KEY,
                            project_code VARCHAR(20) NOT NULL,
                            unit_no VARCHAR(50) NOT NULL,
                            block VARCHAR(20),
                            flat_label VARCHAR(50),
                            floor VARCHAR(20),
                            usage_type VARCHAR(50),
                            office_no VARCHAR(50),
                            size_sqft NUMERIC(12, 2) DEFAULT 0,
                            carpet_sqft NUMERIC(12, 2) DEFAULT 0,
                            terrace_sqft NUMERIC(12, 2) DEFAULT 0,
                            CONSTRAINT unq_unit UNIQUE (project_code, unit_no)
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_unit_project ON units(project_code);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS activity_logs (
                            id SERIAL PRIMARY KEY,
                            created_at VARCHAR(50) NOT NULL,
                            timestamp_iso VARCHAR(50),
                            activity_type VARCHAR(50) NOT NULL,
                            action VARCHAR(100) NOT NULL,
                            project_code VARCHAR(20),
                            project_name VARCHAR(255),
                            description TEXT NOT NULL,
                            details TEXT,
                            status VARCHAR(20) DEFAULT 'SUCCESS',
                            ip_address VARCHAR(50),
                            user_agent VARCHAR(255)
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_created ON activity_logs(created_at);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(100) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            role VARCHAR(50) DEFAULT 'admin',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP
                        );
                    """)
                else:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS projects (
                            code TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            project_type TEXT,
                            gst_rate TEXT DEFAULT '1%',
                            bu_status TEXT DEFAULT 'under_construction',
                            bu_date TEXT,
                            bu_ref TEXT,
                            bu_authority TEXT,
                            notes TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS vouchers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_code TEXT NOT NULL,
                            voucher_number TEXT NOT NULL,
                            date TEXT,
                            party_name TEXT,
                            party_original TEXT,
                            block_no TEXT,
                            unit_no TEXT,
                            amount REAL DEFAULT 0,
                            classification TEXT,
                            gst_rate TEXT,
                            narration TEXT,
                            is_exempt INTEGER DEFAULT 0,
                            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(project_code, voucher_number, date, amount)
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_vch_project ON vouchers(project_code);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS units (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_code TEXT NOT NULL,
                            unit_no TEXT NOT NULL,
                            block TEXT,
                            flat_label TEXT,
                            floor TEXT,
                            usage_type TEXT,
                            office_no TEXT,
                            size_sqft REAL DEFAULT 0,
                            carpet_sqft REAL DEFAULT 0,
                            terrace_sqft REAL DEFAULT 0,
                            UNIQUE(project_code, unit_no)
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_unit_project ON units(project_code);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS activity_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            created_at TEXT NOT NULL,
                            timestamp_iso TEXT,
                            activity_type TEXT NOT NULL,
                            action TEXT NOT NULL,
                            project_code TEXT,
                            project_name TEXT,
                            description TEXT NOT NULL,
                            details TEXT,
                            status TEXT DEFAULT 'SUCCESS',
                            ip_address TEXT,
                            user_agent TEXT
                        );
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_created ON activity_logs(created_at);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_type ON activity_logs(activity_type);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_project ON activity_logs(project_code);")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            role TEXT DEFAULT 'admin',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            last_login TEXT
                        );
                    """)
                conn.commit()
                print("[DatabaseManager] Schema verified successfully.")
                self.seed_admin_user()
        except Exception as e:
            print(f"[DatabaseManager] Schema init warning: {e}")

        self._migrate_voucher_override_columns()

    def _migrate_voucher_override_columns(self):
        """Adds the CA manual-override columns to an already-existing vouchers table
        (CREATE TABLE IF NOT EXISTS above only helps on a brand new DB). Lets the CA
        directly correct a voucher's BU status, income/exclusion, or GST rate from the
        dashboard, overriding the auto-classification in enrich_and_classify_vouchers."""
        columns = [
            ("override_bu_status", "VARCHAR(20)" if self.is_postgres else "TEXT"),
            ("override_is_income", "BOOLEAN" if self.is_postgres else "INTEGER"),
            ("override_rate", "NUMERIC(6,4)" if self.is_postgres else "REAL"),
            ("override_note", "VARCHAR(255)" if self.is_postgres else "TEXT"),
        ]
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    for col, col_type in columns:
                        cur.execute(f"ALTER TABLE vouchers ADD COLUMN IF NOT EXISTS {col} {col_type};")
                else:
                    cur.execute("PRAGMA table_info(vouchers);")
                    existing = {row[1] for row in cur.fetchall()}
                    for col, col_type in columns:
                        if col not in existing:
                            cur.execute(f"ALTER TABLE vouchers ADD COLUMN {col} {col_type};")
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Override column migration warning: {e}")

    def seed_projects_from_file(self, config_path):
        """Seed project master data into database if empty."""
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            raw_projects = data.get("projects") or data.get("real_estate_projects") or {}
            if isinstance(raw_projects, dict):
                for pkey, p in raw_projects.items():
                    code = p.get("code")
                    if not code:
                        continue
                    name = p.get("display_name", pkey)
                    p_type = p.get("type", "Residential")
                    rate_val = p.get("default_residential_rate", 0.05)
                    rate = "1%" if rate_val == 0.01 else "5%"
                    if p.get("type") == "Commercial" or p.get("commercial_rate") == 0.18:
                        rate = "18%"
                    bu_status = "obtained" if p.get("has_bu") else "under_construction"
                    bu_date = p.get("bu_permission_date")
                    bu_ref = p.get("bu_reference_no", "")
                    bu_auth = p.get("authority") or p.get("bu_authority", "")
                    notes = p.get("notes", "")

                    self.upsert_project(code, name, p_type, rate, bu_status, bu_date, bu_ref, bu_auth, notes)
            elif isinstance(raw_projects, list):
                for p in raw_projects:
                    code = p.get("code")
                    if not code:
                        continue
                    name = p.get("name") or p.get("display_name", code)
                    p_type = p.get("type", "Residential")
                    rate = p.get("gst_rate", "1%")
                    bu_status = p.get("bu_status", "under_construction")
                    bu_date = p.get("bu_permission_date") or p.get("bu_date")
                    bu_ref = p.get("bu_reference_no", "")
                    bu_auth = p.get("authority") or p.get("bu_authority", "")
                    notes = p.get("notes", "")

                    self.upsert_project(code, name, p_type, rate, bu_status, bu_date, bu_ref, bu_auth, notes)
        except Exception as e:
            print(f"[DatabaseManager] Seed projects warning: {e}")

    def upsert_project(self, code, name, project_type, gst_rate, bu_status, bu_date, bu_ref="", bu_authority="", notes=""):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("""
                        INSERT INTO projects (code, name, project_type, gst_rate, bu_status, bu_date, bu_ref, bu_authority, notes, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            project_type = EXCLUDED.project_type,
                            gst_rate = EXCLUDED.gst_rate,
                            bu_status = EXCLUDED.bu_status,
                            bu_date = EXCLUDED.bu_date,
                            bu_ref = EXCLUDED.bu_ref,
                            bu_authority = EXCLUDED.bu_authority,
                            notes = EXCLUDED.notes,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (code, name, project_type, gst_rate, bu_status, bu_date, bu_ref, bu_authority, notes))
                else:
                    cur.execute("""
                        INSERT INTO projects (code, name, project_type, gst_rate, bu_status, bu_date, bu_ref, bu_authority, notes, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT (code) DO UPDATE SET
                            name = excluded.name,
                            project_type = excluded.project_type,
                            gst_rate = excluded.gst_rate,
                            bu_status = excluded.bu_status,
                            bu_date = excluded.bu_date,
                            bu_ref = excluded.bu_ref,
                            bu_authority = excluded.bu_authority,
                            notes = excluded.notes,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (code, name, project_type, gst_rate, bu_status, bu_date, bu_ref, bu_authority, notes))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] Error upserting project {code}: {e}")
            return False

    def delete_project(self, code):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("DELETE FROM projects WHERE code = %s;", (code,))
                else:
                    cur.execute("DELETE FROM projects WHERE code = ?;", (code,))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] Error deleting project {code}: {e}")
            return False


    def save_units(self, project_code, units):
        """Upsert the unit/flat inventory master (block, size, usage - no owner/payment
        data) for a project. Sourced from the CA's unit-master Excel sheets, not Tally."""
        if not units:
            return 0
        saved = 0
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                for u in units:
                    unit_no = str(u.get("unit_no") or "").strip()
                    if not unit_no:
                        continue
                    args = (
                        project_code, unit_no, u.get("block", ""), u.get("flat_label", ""),
                        u.get("floor", ""), u.get("usage_type", ""), u.get("office_no", ""),
                        float(u.get("size_sqft") or 0), float(u.get("carpet_sqft") or 0),
                        float(u.get("terrace_sqft") or 0)
                    )
                    if self.is_postgres:
                        cur.execute("""
                            INSERT INTO units (project_code, unit_no, block, flat_label, floor, usage_type, office_no, size_sqft, carpet_sqft, terrace_sqft)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (project_code, unit_no) DO UPDATE SET
                                block = EXCLUDED.block, flat_label = EXCLUDED.flat_label, floor = EXCLUDED.floor,
                                usage_type = EXCLUDED.usage_type, office_no = EXCLUDED.office_no,
                                size_sqft = EXCLUDED.size_sqft, carpet_sqft = EXCLUDED.carpet_sqft, terrace_sqft = EXCLUDED.terrace_sqft;
                        """, args)
                    else:
                        cur.execute("""
                            INSERT INTO units (project_code, unit_no, block, flat_label, floor, usage_type, office_no, size_sqft, carpet_sqft, terrace_sqft)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (project_code, unit_no) DO UPDATE SET
                                block = excluded.block, flat_label = excluded.flat_label, floor = excluded.floor,
                                usage_type = excluded.usage_type, office_no = excluded.office_no,
                                size_sqft = excluded.size_sqft, carpet_sqft = excluded.carpet_sqft, terrace_sqft = excluded.terrace_sqft;
                        """, args)
                    saved += 1
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Error saving units for {project_code}: {e}")
        return saved

    def get_units(self, project_code):
        """Fetch the unit inventory master for a project."""
        units = []
        try:
            with self.get_connection() as conn:
                if self.is_postgres:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute("SELECT * FROM units WHERE project_code = %s ORDER BY block ASC, unit_no ASC", (project_code,))
                else:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM units WHERE project_code = ? ORDER BY block ASC, unit_no ASC", (project_code,))
                for r in cur.fetchall():
                    units.append(dict(r))
        except Exception as e:
            print(f"[DatabaseManager] Error fetching units for {project_code}: {e}")
        return units

    def get_projects(self):
        projects = []
        try:
            with self.get_connection() as conn:
                if self.is_postgres:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                else:
                    cur = conn.cursor()
                cur.execute("SELECT * FROM projects ORDER BY code ASC")
                rows = cur.fetchall()
                for r in rows:
                    if self.is_postgres:
                        projects.append(dict(r))
                    else:
                        projects.append(dict(r))
        except Exception as e:
            print(f"[DatabaseManager] Error fetching projects: {e}")
        return projects

    def get_project(self, code):
        try:
            with self.get_connection() as conn:
                if self.is_postgres:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute("SELECT * FROM projects WHERE code = %s", (code,))
                else:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM projects WHERE code = ?", (code,))
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"[DatabaseManager] Error fetching project {code}: {e}")
            return None

    def save_vouchers(self, project_code, vouchers):
        """
        Incremental upsert for project vouchers with 100% duplicate prevention.
        - Supports whole project dumps from inception to till date.
        - Only extracts/inserts new month records while preserving existing verified data.
        - Updates records if amounts or details changed in Tally.
        - Returns a SyncResult with detailed incremental counts.
        """
        if not vouchers:
            return SyncResult({"total": 0, "inserted": 0, "updated": 0, "unchanged": 0, "periods": []})

        inserted = 0
        updated = 0
        unchanged = 0
        periods_seen = set()
        to_update = []
        to_insert = []

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()

                # 1. Fetch existing voucher keys for this project to compare incrementally
                if self.is_postgres:
                    cur.execute("SELECT voucher_number, date, amount, party_name, classification FROM vouchers WHERE project_code = %s", (project_code,))
                else:
                    cur.execute("SELECT voucher_number, date, amount, party_name, classification FROM vouchers WHERE project_code = ?", (project_code,))

                existing_map = {}
                for r in cur.fetchall():
                    vn = str(r[0] or "").strip()
                    vd = str(r[1] or "").strip()
                    if vn:
                        existing_map[(vn, vd)] = {
                            "amount": float(r[2] or 0),
                            "party": str(r[3] or "").strip(),
                            "classification": str(r[4] or "").strip()
                        }

                # 2. Process incoming vouchers from dump
                for v in vouchers:
                    v_num = str(v.get("voucher_number") or v.get("vch_no") or v.get("voucher_no") or "").strip()
                    v_date = str(v.get("date") or v.get("iso_date") or "").strip()
                    party = str(v.get("party_name") or v.get("member_name") or v.get("name") or "").strip()
                    blk = str(v.get("block_no") or "").strip()
                    unit = str(v.get("unit_no") or v.get("flat_no") or v.get("unit") or "").strip()

                    # If unit is empty or a bank name, inspect bank_cash for real member unit
                    orig = str(v.get("party_original") or v.get("raw_name") or party).strip()
                    bc = str(v.get("bank_cash") or "").strip()
                    if (not unit or any(b in unit.upper() for b in ["HDFC", "AXIS", "ICICI", "BANK"])) and bc:
                        u_bc, name_bc = _parse_unit_and_name(bc)
                        if u_bc:
                            unit = u_bc
                            party = name_bc or party
                            orig = bc

                    amt_raw = v.get("amount") if v.get("amount") is not None else v.get("cr_amount", 0)
                    try:
                        amt = float(amt_raw or 0)
                    except (ValueError, TypeError):
                        amt = 0.0

                    if amt <= 0 and not v_num:
                        continue

                    cls = str(v.get("classification") or "").strip()
                    rate = str(v.get("gst_rate") or "").strip()
                    narr = str(v.get("narration") or "").strip()
                    exempt = bool(v.get("is_exempt") or v.get("badge_type") == "exempt" or "exempt" in cls.lower())

                    # If voucher_number is missing, synthesize a deterministic unique number
                    if not v_num:
                        v_num = f"VCH-{project_code}-{v_date.replace('-', '')}-{unit.replace('/', '-')}"

                    # Track period
                    if len(v_date) >= 7:
                        parts = v_date.split("-")
                        if len(parts) == 3:
                            periods_seen.add(f"{parts[1]}-{parts[2] if len(parts[2])==4 else parts[0]}")

                    key = (v_num, v_date)
                    if key in existing_map:
                        old_record = existing_map[key]
                        # Check if any financial or master value changed in Tally
                        if abs(old_record["amount"] - amt) > 0.01 or old_record["party"] != party or old_record["classification"] != cls:
                            if self.is_postgres:
                                to_update.append((party, orig, blk, unit, amt, cls, rate, narr, exempt, project_code, v_num, v_date))
                            else:
                                to_update.append((party, orig, blk, unit, amt, cls, rate, narr, 1 if exempt else 0, project_code, v_num, v_date))
                            updated += 1
                        else:
                            unchanged += 1
                    else:
                        # Brand new voucher for this period
                        if self.is_postgres:
                            to_insert.append((project_code, v_num, v_date, party, orig, blk, unit, amt, cls, rate, narr, exempt))
                        else:
                            to_insert.append((project_code, v_num, v_date, party, orig, blk, unit, amt, cls, rate, narr, 1 if exempt else 0))
                        inserted += 1
                        existing_map[key] = {"amount": amt, "party": party, "classification": cls}

                # 3. Batch execute all updates and inserts for maximum throughput
                if to_update:
                    if self.is_postgres and PSYCOPG2_AVAILABLE:
                        from psycopg2.extras import execute_batch
                        execute_batch(cur, """
                            UPDATE vouchers SET
                                party_name = %s, party_original = %s, block_no = %s, unit_no = %s,
                                amount = %s, classification = %s, gst_rate = %s, narration = %s,
                                is_exempt = %s, synced_at = CURRENT_TIMESTAMP
                            WHERE project_code = %s AND voucher_number = %s AND date = %s;
                        """, to_update, page_size=1000)
                    else:
                        cur.executemany("""
                            UPDATE vouchers SET
                                party_name = ?, party_original = ?, block_no = ?, unit_no = ?,
                                amount = ?, classification = ?, gst_rate = ?, narration = ?,
                                is_exempt = ?, synced_at = CURRENT_TIMESTAMP
                            WHERE project_code = ? AND voucher_number = ? AND date = ?;
                        """, to_update)

                if to_insert:
                    if self.is_postgres and PSYCOPG2_AVAILABLE:
                        from psycopg2.extras import execute_batch
                        execute_batch(cur, """
                            INSERT INTO vouchers (
                                project_code, voucher_number, date, party_name, party_original,
                                block_no, unit_no, amount, classification, gst_rate, narration, is_exempt
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (project_code, voucher_number, date, amount) DO UPDATE SET
                                party_name = EXCLUDED.party_name,
                                party_original = EXCLUDED.party_original,
                                block_no = EXCLUDED.block_no,
                                unit_no = EXCLUDED.unit_no,
                                classification = EXCLUDED.classification,
                                gst_rate = EXCLUDED.gst_rate,
                                narration = EXCLUDED.narration,
                                is_exempt = EXCLUDED.is_exempt;
                        """, to_insert, page_size=1000)
                    else:
                        cur.executemany("""
                            INSERT INTO vouchers (
                                project_code, voucher_number, date, party_name, party_original,
                                block_no, unit_no, amount, classification, gst_rate, narration, is_exempt
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (project_code, voucher_number, date, amount) DO UPDATE SET
                                party_name = excluded.party_name,
                                party_original = excluded.party_original,
                                block_no = excluded.block_no,
                                unit_no = excluded.unit_no,
                                classification = excluded.classification,
                                gst_rate = excluded.gst_rate,
                                narration = excluded.narration,
                                is_exempt = excluded.is_exempt;
                        """, to_insert)

                conn.commit()
                print(f"[DatabaseManager] Incremental Sync for {project_code}: +{inserted} new, {updated} updated, {unchanged} unchanged (0 duplicates).")
        except Exception as e:
            print(f"[DatabaseManager] Error during incremental save_vouchers: {e}")

        return SyncResult({
            "total": len(vouchers),
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "periods": sorted(list(periods_seen))
        })

    def get_vouchers(self, project_code):
        """Retrieve stored vouchers for a project."""
        vouchers = []
        try:
            with self.get_connection() as conn:
                if self.is_postgres:
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    cur.execute("SELECT * FROM vouchers WHERE project_code = %s ORDER BY date ASC, id ASC", (project_code,))
                else:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM vouchers WHERE project_code = ? ORDER BY date ASC, id ASC", (project_code,))
                rows = cur.fetchall()
                for r in rows:
                    item = dict(r)
                    if not self.is_postgres:
                        item["is_exempt"] = bool(item.get("is_exempt"))
                    vouchers.append(item)
        except Exception as e:
            print(f"[DatabaseManager] Error fetching vouchers for {project_code}: {e}")
        return vouchers

    def set_voucher_override(self, project_code, voucher_number, date, bu_status=None, is_income=None, rate=None, note=None):
        """
        CA manual correction for a single voucher, identified the same way save_vouchers
        upserts it (project_code, voucher_number, date). All fields are optional and
        independent: pass only the ones being changed. Passing the literal string "auto"
        for bu_status, or None for is_income/rate, clears that override back to
        auto-classification. Never deletes or touches amount/party/narration - this only
        steers enrich_and_classify_vouchers's decision for this one voucher.
        """
        if bu_status == "auto":
            bu_status = None
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                args = (bu_status, is_income, rate, note, project_code, voucher_number, date)
                if self.is_postgres:
                    cur.execute("""
                        UPDATE vouchers SET override_bu_status = %s, override_is_income = %s,
                            override_rate = %s, override_note = %s
                        WHERE project_code = %s AND voucher_number = %s AND date = %s;
                    """, args)
                else:
                    cur.execute("""
                        UPDATE vouchers SET override_bu_status = ?, override_is_income = ?,
                            override_rate = ?, override_note = ?
                        WHERE project_code = ? AND voucher_number = ? AND date = ?;
                    """, args)
                updated = cur.rowcount
                conn.commit()
                return updated > 0
        except Exception as e:
            print(f"[DatabaseManager] Error setting voucher override: {e}")
            return False

    def set_unit_bu_override(self, project_code, unit_no, bu_status=None, note=None):
        """
        Sets manual BU status override for all vouchers of an entire unit in one go.
        bu_status can be 'after_bu', 'before_bu', or 'auto' (clears override).
        """
        if bu_status == "auto":
            bu_status = None
        clean_u = unit_no.replace("-", "").replace(" ", "").upper()
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                args = (bu_status, note, project_code, unit_no, clean_u)
                if self.is_postgres:
                    cur.execute("""
                        UPDATE vouchers SET override_bu_status = %s, override_note = %s
                        WHERE project_code = %s AND (
                            UPPER(unit_no) = UPPER(%s) OR 
                            REPLACE(REPLACE(UPPER(unit_no), '-', ''), ' ', '') = %s
                        );
                    """, args)
                else:
                    cur.execute("""
                        UPDATE vouchers SET override_bu_status = ?, override_note = ?
                        WHERE project_code = ? AND (
                            UPPER(unit_no) = UPPER(?) OR 
                            REPLACE(REPLACE(UPPER(unit_no), '-', ''), ' ', '') = ?
                        );
                    """, args)
                updated = cur.rowcount
                conn.commit()
                return updated
        except Exception as e:
            print(f"[DatabaseManager] Error setting unit BU override: {e}")
            return 0

    def fix_flat_name_parsing(self):
        """
        One-time, idempotent correction: re-derives unit_no/block_no/party_name from
        the original unparsed ledger text (party_original) using the corrected
        flat-code parser. Fixes historical rows where a hyphen-glued owner name
        (e.g. 'I-803-Neetaben Trivedi') was mis-split, swallowing the first owner's
        name into the flat code instead of the account name. Never deletes rows;
        only corrects unit_no/block_no/party_name when the re-derived split differs.
        Safe to run on every startup - rows already correctly split are left as-is.
        """
        fixed = 0
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, party_original, unit_no, block_no, party_name FROM vouchers WHERE party_original IS NOT NULL AND party_original != ''")
                rows = cur.fetchall()

                for r in rows:
                    rid, orig, old_unit, old_block, old_party = r[0], r[1], r[2], r[3], r[4]
                    new_unit, new_name = _parse_unit_and_name(orig)
                    old_unit_s = (old_unit or "").strip()

                    if new_unit and new_name:
                        if new_unit == old_unit_s and new_name == (old_party or ""):
                            continue
                        final_unit, final_name = new_unit, new_name
                    elif not new_unit and old_unit_s and not any(ch.isdigit() for ch in old_unit_s):
                        # Old parser left a bogus non-digit fragment (e.g. 'AXIS', 'ICICI')
                        # as the flat code for a vendor/bank ledger that has no real unit.
                        # A real flat code always contains a digit, so this is unambiguous.
                        final_unit, final_name = "", str(orig).strip()
                    elif old_unit_s and any(b in str(orig).upper() for b in ["HDFC BANK", "AXIS BANK", "ICICI BANK", "BANK MASTER"]):
                        # party_original was mistakenly set to bank ledger name instead of member
                        if self.is_postgres:
                            cur.execute("UPDATE vouchers SET party_original = %s WHERE id = %s", (old_party, rid))
                        else:
                            cur.execute("UPDATE vouchers SET party_original = ? WHERE id = ?", (old_party, rid))
                        fixed += 1
                        continue
                    else:
                        continue

                    if self.is_postgres:
                        cur.execute(
                            "UPDATE vouchers SET unit_no = %s, party_name = %s WHERE id = %s",
                            (final_unit, final_name, rid)
                        )
                    else:
                        cur.execute(
                            "UPDATE vouchers SET unit_no = ?, party_name = ? WHERE id = ?",
                            (final_unit, final_name, rid)
                        )
                    fixed += 1

                conn.commit()
                if fixed:
                    print(f"[DatabaseManager] fix_flat_name_parsing: corrected {fixed} voucher flat/name split(s).")
        except Exception as e:
            print(f"[DatabaseManager] Error in fix_flat_name_parsing: {e}")
        return fixed

    def count_vouchers_per_project(self):
        counts = {}
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT project_code, COUNT(*) FROM vouchers GROUP BY project_code")
                for row in cur.fetchall():
                    counts[str(row[0])] = row[1]
        except Exception as e:
            print(f"[DatabaseManager] Error counting vouchers: {e}")
        return counts

    def dedupe_exact_vouchers(self, project_code):
        """
        One-time cleanup: removes rows that are exact full duplicates - same
        project_code, voucher_number, date, amount, party_name AND classification -
        keeping only the earliest (lowest id) row per group. Deliberately does NOT
        key on voucher_number/date/amount alone, since Tally numbers vouchers
        separately per voucher type, so two genuinely different vouchers can share
        a (voucher_number, date) pair; requiring every field to match avoids ever
        deleting a real, distinct voucher.
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                placeholder = "%s" if self.is_postgres else "?"
                before = None
                cur.execute(f"SELECT COUNT(*) FROM vouchers WHERE project_code = {placeholder}", (project_code,))
                before = cur.fetchone()[0]

                cur.execute(f"""
                    DELETE FROM vouchers
                    WHERE project_code = {placeholder}
                    AND id NOT IN (
                        SELECT MIN(id) FROM vouchers
                        WHERE project_code = {placeholder}
                        GROUP BY project_code, voucher_number, date, amount, party_name, classification
                    )
                """, (project_code, project_code))
                conn.commit()

                cur.execute(f"SELECT COUNT(*) FROM vouchers WHERE project_code = {placeholder}", (project_code,))
                after = cur.fetchone()[0]
                removed = before - after
                print(f"[DatabaseManager] Dedup for {project_code}: {before} -> {after} ({removed} exact duplicate rows removed).")
                return {"project_code": project_code, "before": before, "after": after, "removed": removed}
        except Exception as e:
            print(f"[DatabaseManager] Error during dedupe_exact_vouchers for {project_code}: {e}")
            return {"project_code": project_code, "error": str(e)}


    def purge_fake_vouchers(self):
        """Purges any synthetic / mock vouchers (e.g. FP-2608-*) from the database."""
        deleted_count = 0
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("DELETE FROM vouchers WHERE voucher_number LIKE 'FP-%' OR voucher_number LIKE 'FP-2608-%' OR voucher_number LIKE 'VCH-FP-%'")
                    deleted_count = cur.rowcount
                else:
                    cur.execute("DELETE FROM vouchers WHERE voucher_number LIKE 'FP-%' OR voucher_number LIKE 'FP-2608-%' OR voucher_number LIKE 'VCH-FP-%'")
                    deleted_count = cur.rowcount
                conn.commit()
                if deleted_count > 0:
                    print(f"[DatabaseManager] Purged {deleted_count} synthetic Excel vouchers.")
        except Exception as e:
            print(f"[DatabaseManager] Purge error: {e}")
        return deleted_count

    def insert_activity_log(self, activity_type, action, description, project_code=None, project_name=None, details=None, status="SUCCESS", ip_address=None, user_agent=None, created_at=None, timestamp_iso=None):
        now = datetime.now()
        if not created_at:
            created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        if not timestamp_iso:
            timestamp_iso = now.isoformat()
        
        details_str = json.dumps(details) if isinstance(details, (dict, list)) else (str(details) if details else None)
        placeholder = "%s" if self.is_postgres else "?"
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO activity_logs (created_at, timestamp_iso, activity_type, action, project_code, project_name, description, details, status, ip_address, user_agent)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (created_at, timestamp_iso, activity_type, action, project_code or "", project_name or "", description, details_str, status or "SUCCESS", ip_address or "", user_agent or ""))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] Activity log insert error: {e}")
            return False

    def get_activity_logs(self, project_code=None, activity_type=None, status=None, search=None, limit=100, offset=0):
        placeholder = "%s" if self.is_postgres else "?"
        clauses = []
        params = []
        if project_code and project_code != "ALL":
            clauses.append(f"project_code = {placeholder}")
            params.append(project_code)
        if activity_type and activity_type != "ALL":
            clauses.append(f"activity_type = {placeholder}")
            params.append(activity_type)
        if status and status != "ALL":
            clauses.append(f"status = {placeholder}")
            params.append(status)
        if search:
            search_pattern = f"%{search.strip()}%"
            clauses.append(f"(description LIKE {placeholder} OR action LIKE {placeholder} OR project_name LIKE {placeholder} OR details LIKE {placeholder})")
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        where_clause = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        count_sql = f"SELECT COUNT(*) FROM activity_logs {where_clause}"
        data_sql = f"SELECT id, created_at, timestamp_iso, activity_type, action, project_code, project_name, description, details, status, ip_address, user_agent FROM activity_logs {where_clause} ORDER BY id DESC LIMIT {int(limit)} OFFSET {int(offset)}"

        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(count_sql, tuple(params))
                total = cur.fetchone()[0]

                cur.execute(data_sql, tuple(params))
                rows = cur.fetchall()
                logs = []
                for r in rows:
                    if self.is_postgres:
                        row_dict = {
                            "id": r[0], "created_at": r[1], "timestamp_iso": r[2], "activity_type": r[3],
                            "action": r[4], "project_code": r[5], "project_name": r[6], "description": r[7],
                            "details": r[8], "status": r[9], "ip_address": r[10], "user_agent": r[11]
                        }
                    else:
                        row_dict = dict(r)
                    det = row_dict.get("details")
                    if det:
                        try:
                            row_dict["details_parsed"] = json.loads(det)
                        except Exception:
                            row_dict["details_parsed"] = None
                    logs.append(row_dict)
                return {"total": total, "logs": logs}
        except Exception as e:
            print(f"[DatabaseManager] Activity log query error: {e}")
            return {"total": 0, "logs": []}

    def get_activity_stats(self):
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM activity_logs")
                total = cur.fetchone()[0]

                cur.execute("SELECT activity_type, COUNT(*) FROM activity_logs GROUP BY activity_type")
                by_type = {r[0]: r[1] for r in cur.fetchall()}

                cur.execute("SELECT status, COUNT(*) FROM activity_logs GROUP BY status")
                by_status = {r[0]: r[1] for r in cur.fetchall()}

                cur.execute("SELECT created_at FROM activity_logs ORDER BY id DESC LIMIT 1")
                last_row = cur.fetchone()
                last_active = last_row[0] if last_row else None

                return {
                    "total": total,
                    "by_type": by_type,
                    "by_status": by_status,
                    "last_active": last_active
                }
        except Exception as e:
            print(f"[DatabaseManager] Activity stats error: {e}")
            return {"total": 0, "by_type": {}, "by_status": {}, "last_active": None}

    def seed_admin_user(self):
        """Ensure default admin user exists with password 'admin'."""
        try:
            from werkzeug.security import generate_password_hash
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("SELECT id FROM users WHERE username = %s;", ('admin',))
                    if not cur.fetchone():
                        p_hash = generate_password_hash("admin")
                        cur.execute(
                            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s);",
                            ('admin', p_hash, 'admin')
                        )
                        conn.commit()
                        print("[DatabaseManager] Default admin user initialized (username: admin, password: admin).")
                else:
                    cur.execute("SELECT id FROM users WHERE username = ?;", ('admin',))
                    if not cur.fetchone():
                        p_hash = generate_password_hash("admin")
                        cur.execute(
                            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
                            ('admin', p_hash, 'admin')
                        )
                        conn.commit()
                        print("[DatabaseManager] Default admin user initialized (username: admin, password: admin).")
        except Exception as e:
            print(f"[DatabaseManager] Seed admin user warning: {e}")

    def get_user(self, username):
        """Retrieve user record by username."""
        if not username:
            return None
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("SELECT id, username, password_hash, role, created_at, last_login FROM users WHERE username = %s;", (username.strip(),))
                    row = cur.fetchone()
                    if row:
                        if hasattr(cur, 'description') and cur.description:
                            cols = [d[0] for d in cur.description]
                            return dict(zip(cols, row))
                        return dict(row)
                else:
                    cur.execute("SELECT id, username, password_hash, role, created_at, last_login FROM users WHERE username = ?;", (username.strip(),))
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            print(f"[DatabaseManager] get_user error: {e}")
        return None

    def verify_user(self, username, password):
        """Verify username and password against database."""
        from werkzeug.security import check_password_hash
        user = self.get_user(username)
        if not user:
            return None
        if check_password_hash(user["password_hash"], str(password or "")):
            self.update_last_login(username)
            return {
                "id": user["id"],
                "username": user["username"],
                "role": user.get("role", "admin")
            }
        return None

    def update_last_login(self, username):
        """Update last login timestamp for user."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s;", (username,))
                else:
                    cur.execute("UPDATE users SET last_login = ? WHERE username = ?;", (now_str, username))
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] update_last_login error: {e}")

    def update_password(self, username, new_password):
        """Update user password with salted hash."""
        from werkzeug.security import generate_password_hash
        p_hash = generate_password_hash(new_password)
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.is_postgres:
                    cur.execute("UPDATE users SET password_hash = %s WHERE username = %s;", (p_hash, username))
                else:
                    cur.execute("UPDATE users SET password_hash = ? WHERE username = ?;", (p_hash, username))
                conn.commit()
                return True
        except Exception as e:
            print(f"[DatabaseManager] update_password error: {e}")
            return False


# Singleton instance
db = DatabaseManager()


