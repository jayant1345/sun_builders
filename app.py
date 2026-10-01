import os
import sys
import json
import argparse
from datetime import datetime

from core.tally_client import TallyClient
from core.tally_file_reader import TallyFileReader
from core.gst_rules import RealEstateGSTRules
from core.excel_generator import ExcelGenerator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "project_master.json")
TEMPLATE_PATH = r"C:\naman_ca\Sun_Builders\01.GSTR -1 AUG-26 SUN BUILDERS PROJECTS LLP ( FORMERLY KNOWN AS SUN REALTY).xlsx"
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_pipeline(target_month: str = "AUG-26", from_date: str = "20260801", to_date: str = "20260831"):
    print("=" * 70)
    print("  SUN BUILDERS PROJECTS LLP - REAL ESTATE GST AUTOMATION SYSTEM")
    print("=" * 70)
    print(f"Target Tax Period: {target_month} ({from_date} to {to_date})")

    cfg = load_config()
    rules = RealEstateGSTRules(cfg)
    client = TallyClient()

    print("\n[Step 1] Checking Tally Status...")
    if client.is_connected():
        print("  -> Tally is RUNNING on port 9000! (Connected)")
        companies = client.get_loaded_companies()
        print(f"  -> Active Companies: {companies}")
        target_company = cfg.get("company_name", "SUN BUILDERS PROJECTS LLP")
        matched = [c for c in companies if "SUN" in c.upper()]
        if matched:
            print(f"  -> Selected Company: {matched[0]}")
            print(f"  -> Extracting vouchers for {from_date} to {to_date}...")
            raw_xml = client.export_vouchers_xml(matched[0], from_date, to_date)
            vouchers = client.parse_vouchers(raw_xml)
            print(f"  -> Extracted {len(vouchers)} vouchers from Tally.")
        else:
            print(f"  -> Please load '{target_company}' (Company 010010) inside Tally.")
    else:
        print("  -> Tally is not running on port 9000.")
        print(f"  -> Company data 010010 is extracted at: {os.path.join(BASE_DIR, 'data', '010010')}")
        print("  -> To connect live: Launch Tally, select Company 010010, ensure Port 9000 is open.")

    print("\n[Step 2] Processing Real Estate GST Rules...")
    print("  -> Classifying: Pre-BU vs Post-BU (Exempt under Schedule III Entry 5)")
    print("  -> Classifying: Residential <= 45L (1%) vs > 45L (5%)")
    print("  -> Classifying: Commercial Shops (5% in RREP) vs Pure Commercial (18% with 1/3 Land Abatement)")
    print("  -> Filtering Pure Agent items: Stamp Duty, Registration Fees, Maintenance Deposits")

    print("\n[Step 3] Generating GSTR-1 Workbook...")
    gen = ExcelGenerator(TEMPLATE_PATH)
    out_file = os.path.join(OUTPUT_DIR, f"GSTR-1_{target_month}_AUTOMATED.xlsx")
    gen.generate_monthly_workbook(target_month, {}, out_file)

    print("\n" + "=" * 70)
    print(f"  SUCCESS: Monthly GST Workbook created at:\n  {out_file}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sun Builders Real Estate GST Automation")
    parser.add_argument("--month", default="AUG-26", help="Month code e.g. AUG-26, SEP-26")
    parser.add_argument("--from-date", default="20260801", help="From date YYYYMMDD")
    parser.add_argument("--to-date", default="20260831", help="To date YYYYMMDD")
    args = parser.parse_args()

    run_pipeline(args.month, args.from_date, args.to_date)
