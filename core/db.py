import os
import json
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

# Optional psycopg2 import
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


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
                conn.commit()
                print("[DatabaseManager] Schema verified successfully.")
        except Exception as e:
            print(f"[DatabaseManager] Schema init warning: {e}")

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
        """Bulk upsert vouchers for a project."""
        if not vouchers:
            return 0
        inserted = 0
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                for v in vouchers:
                    v_num = str(v.get("voucher_number") or "")
                    v_date = str(v.get("date") or "")
                    party = str(v.get("party_name") or "")
                    orig = str(v.get("party_original") or party)
                    blk = str(v.get("block_no") or "")
                    unit = str(v.get("unit_no") or "")
                    amt = float(v.get("amount") or 0)
                    cls = str(v.get("classification") or "")
                    rate = str(v.get("gst_rate") or "")
                    narr = str(v.get("narration") or "")
                    exempt = bool(v.get("is_exempt", False))

                    if self.is_postgres:
                        cur.execute("""
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
                        """, (project_code, v_num, v_date, party, orig, blk, unit, amt, cls, rate, narr, exempt))
                    else:
                        cur.execute("""
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
                        """, (project_code, v_num, v_date, party, orig, blk, unit, amt, cls, rate, narr, 1 if exempt else 0))
                    inserted += 1
                conn.commit()
        except Exception as e:
            print(f"[DatabaseManager] Error saving vouchers: {e}")
        return inserted

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


# Singleton instance
db = DatabaseManager()
