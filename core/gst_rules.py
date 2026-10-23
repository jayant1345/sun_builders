import re
from datetime import datetime

CREDITOR_KEYWORDS = [
    # True vendors/contractors/suppliers/banks - no connection to any member's unit, never
    # shown on a member's row in the output sheet. Deliberately does NOT include stamp
    # duty/registration fee/refundable deposit/electricity-exp keywords any more - those are
    # non-GST amounts a MEMBER paid through their own unit's ledger (see classify_pass_through_type
    # below), and belong in that member's row (in their own Receipt/Payment column), not dropped
    # entirely. Conflating the two was the bug CA flagged: "advance receipts have been recorded,
    # but the software is not fetching these receipts correctly" - stamp duty/reg fee vouchers
    # tied to a real unit were being silently excluded instead of routed to their own column.
    r'\bcreditor\b', r'\bvendor\b', r'\bsupplier\b', r'\bcontractor\b', r'\bsubcontractor\b',
    r'\bpurchase\b', r'\bmaterial\b', r'\bcable\b', r'\bnotary\b', r'\bsale deed\b', r'\bsales deed\b', r'\bats\b',
    r'\bconsultant\b', r'\bprofessional fee\b', r'\blegal fee\b', r'\baudit fee\b', r'\bbank charges\b',
    r'\bcourier\b', r'\bprinting\b', r'\bstationery\b', r'\bfreight\b', r'\btransport\b', r'\broadlines\b', r'\blogistics\b',
    r'\blabour\b', r'\blabor\b', r'\bcement\b', r'\bsteel\b', r'\bsand supplier\b', r'\bbricks\b', r'\btiles\b', r'\bplumbing\b', r'\bsanitary\b',
    r'\bpaint\b', r'\bsecurity services\b', r'\bwater charges\b', r'\bdiesel\b', r'\bfuel\b', r'\brepair\b',
    r'\bcorporation\b', r'\benterprises\b', r'\btraders\b', r'\bbuildcon\b', r'\binfra\b', r'\bagency\b', r'\bagencies\b',
    r'\bgas\b', r'\bgujarat gas\b', r'\bhardware\b', r'\bplywood\b', r'\bglass\b', r'\baluminium\b', r'\baluminum\b', r'\biron\b',
    r'\br\.m\.c\b', r'\brmc\b', r'\breadymix\b', r'\bconcrete\b', r'\bearthmovers\b', r'\bexcavation\b', r'\bcrane\b', r'\bbank coll\b',
    r'\baxis bank\b', r'\bicici bank\b', r'\bhdfc bank\b', r'\bsbi\b',
    # "M/s" (Messrs.) is a business-entity prefix - a flat/shop owner is never addressed this way,
    # only a registered firm. Backstops the creditor check for any vendor whose ledger name
    # happens to parse out a digit-containing fragment that looks like a flat code (e.g. a
    # supplier ledger swept into income because of a coincidental match in the unit-code regex).
    # NOTE: deliberately no bare '\bllp\b' keyword - the company's own name ("Sun Builders
    # Projects LLP") appears naturally in bank transfer narrations (e.g. NEFT/RTGS reference
    # text), which would wrongly flag genuine member payments as creditor entries. Confirmed
    # on real data: this exact pattern hit unit C-901's real payments.
    r'\bm/s\.?\b', r'\btimber\b', r'\bmart\b', r'\bstores?\b', r'\bsupply\b', r'\bindustries\b',
    r'\bworks contract\b', r'\bdepot\b', r'\bwholesale\b', r'\bdistributors?\b', r'\bimpex\b',
    r'\bpvt\.?\s*ltd\.?\b',
]

# Non-GST amounts collected THROUGH a member's own unit ledger (the CA's 5-category exclusion
# list) - these stay tied to that member's row in the output sheet (their own Receipt/Payment
# column) rather than being dropped, but are excluded from the taxable base. Order matters:
# checked top-to-bottom, first match wins, since e.g. a stamp-duty narration might also contain
# "registration" in the same line.
PASS_THROUGH_KEYWORDS = [
    ("stamp_duty", [
        r'\bstamp duty\b', r'\bstamp\b', r'\bstampduty\b', r'\bfrank(?:ing)?\b'
    ]),
    ("reg_fee", [
        r'\bregistration\b', r'\breg(?:n|istration)?\.?\s*fee\b', r'\breg\b'
    ]),
    ("refundable_deposit", [
        r'\brefund', r'\bsecurity deposit\b', r'\bmember deposit\b', r'\bcaution deposit\b'
    ]),
    ("electricity_exp", [
        r'\belectric\b', r'\belectricity\b', r'\blight bill\b', r'\bauda\b', r'\baec\b', r'\btorrent\b',
        r'\bpgvcl\b', r'\bgeb\b', r'\bugvcl\b', r'\bdgvcl\b', r'\bmgvcl\b', r'\bpower deposit\b',
        r'\belectric deposit\b', r'\bmeter deposit\b', r'\btransformer\b'
    ]),
    ("maintenance_deposit", [
        r'\bmaintenance\b', r'\bmaintanance\b', r'\bsociety\b', r'\bsociety deposit\b',
        r'\bsociety maintenance\b', r'\bsociety maintanance\b', r'\bsociety fund\b',
        r'\bsinking fund\b', r'\badhoc\b'
    ]),
]

def is_valid_unit_code(unit_str: str) -> bool:
    """Returns True ONLY if unit_str is an authentic real estate block/unit/flat code.
    Rejects person names (Sonal, Hemil, Subhash), banks, deposits, expenses, and words without digits."""
    if not unit_str:
        return False
    u = str(unit_str).strip().upper()
    if u in ("", "—", "-", "N/A", "UNIT N/A", "UNDEFINED", "NONE", "NULL"):
        return False
    # A real flat/unit code in Sun Builders portfolio ALWAYS contains digits
    if not re.search(r'\d', u):
        return False
    # Disallow common words that accidentally got attached
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

# Pre-compiled high-performance classification regexes
CREDITOR_RE = re.compile(r'|'.join(f'(?:{k})' for k in CREDITOR_KEYWORDS), re.IGNORECASE)
PASS_THROUGH_COMPILED = [
    (category, re.compile(r'|'.join(f'(?:{p})' for p in patterns), re.IGNORECASE))
    for category, patterns in PASS_THROUGH_KEYWORDS
]

def classify_pass_through_type(party_str: str, raw_name: str = "", narr: str = ""):
    """Returns the non-GST pass-through category ('stamp_duty', 'reg_fee',
    'refundable_deposit', 'electricity_exp', 'maintenance_deposit') this voucher matches, or
    None. Pre-compiled for high performance across tens of thousands of vouchers."""
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}"
    for category, pattern_re in PASS_THROUGH_COMPILED:
        if pattern_re.search(combined):
            return category
    return None

def is_creditor_party(party_str: str, raw_name: str = "", narr: str = "") -> bool:
    """Returns True if party name or narration indicates a true vendor/creditor/contractor.
    Utilizes single pre-compiled combined regex for near-instant execution."""
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}"
    return bool(CREDITOR_RE.search(combined))

AFTER_BU_RE = re.compile(r'(?:after|aftr|aft|af)\s*[\-_]?\s*bu\b', re.IGNORECASE)

def is_after_bu_member(party_str: str, raw_name: str = "", narr: str = "") -> bool:
    """
    Returns True if member ledger/narration contains 'After BU' or variations ('Af Bu', 'Aft Bu',
    'Aftr Bu', 'Afterbu'), indicating flat purchased after BU permission (Schedule III Entry 5 - 0% GST).
    """
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}"
    return bool(AFTER_BU_RE.search(combined) or 'afterbu' in combined.lower())

def is_cancelled_booking(party_str: str, raw_name: str = "", narr: str = "") -> bool:
    """Returns True if the party name or narration indicates a booking that was cancelled/voided
    and refunded - e.g. a party name suffixed '-CANCELLED', or a refund voucher's narration
    mentioning 'cancellation'/'cancelleation' (a common misspelling seen in this data) even when
    the party name itself carries no CANCELLED tag. A fallen-through booking was never genuine
    sale consideration and must not be taxed as income."""
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}".lower()
    return 'cancel' in combined

def is_plausible_receipt_amount(amount: float, min_amount: float = 100.0, max_amount: float = 10000000.0) -> bool:
    """Sanity-checks a single voucher amount as a genuine flat/shop owner installment or full
    payment. Real per-voucher owner receipts in this data range from a few hundred rupees up to
    roughly the price of one unit; amounts below min_amount are data-entry artifacts (e.g. Rs.1,
    Rs.4 placeholder rows) and amounts above max_amount (default Rs.1 Crore - well above this
    project's own 'Affordable Residential <= Rs.45L' threshold, with headroom for a full-cash
    higher-value unit) are not a plausible single owner payment and are far more likely to be a
    non-receipt entry (e.g. a sale-deed/agreement value booked as a journal entry) swept in because
    Tally's VOUCHERTYPENAME isn't filtered. Such amounts are excluded from taxable income and
    flagged for manual CA review rather than being silently taxed or silently dropped."""
    return min_amount <= amount <= max_amount

def parse_voucher_date(date_str):
    """Parses a voucher date stored as 'DD-MM-YYYY' (this app's live-sync format)."""
    try:
        return datetime.strptime(str(date_str or "").strip(), "%d-%m-%Y")
    except Exception:
        return None

def is_voucher_after_bu_date(voucher_date_str: str, has_bu: bool, bu_permission_date_str: str) -> bool:
    """Tests whether a given voucher date falls after the project's BU permission date.
    bu_permission_date_str is expected as 'YYYY-MM-DD' (as stored in project config);
    voucher_date_str is 'DD-MM-YYYY'. Returns False if the project has no BU yet, or either
    date fails to parse (never silently exempts on bad data). Callers should generally pass
    a UNIT's earliest payment date here (see compute_unit_bu_status in server.py), not an
    individual installment's own date - Schedule III Entry 5 exemption depends on whether
    the unit's sale agreement predates BU, not on when each later installment happens to
    be paid."""
    if not has_bu or not bu_permission_date_str:
        return False
    v_dt = parse_voucher_date(voucher_date_str)
    if not v_dt:
        return False
    try:
        bu_dt = datetime.strptime(str(bu_permission_date_str).strip(), "%Y-%m-%d")
    except Exception:
        return False
    return v_dt > bu_dt

def calculate_inclusive_tax(amount: float, rate: float = 0.01) -> dict:
    """
    Calculates tax assuming advance receipt amount is INCLUSIVE of GST.
    For 1% rate:
        Taxable Base = Round(Amount / 1.01, 2)
        CGST (0.5%)  = Round((Amount * 0.5) / 101, 2)
        SGST (0.5%)  = Round((Amount * 0.5) / 101, 2)
    For 5% rate:
        Taxable Base = Round(Amount / 1.05, 2)
        CGST (2.5%)  = Round((Amount * 2.5) / 105, 2)
        SGST (2.5%)  = Round((Amount * 2.5) / 105, 2)
    """
    if rate <= 0 or amount <= 0:
        return {"taxable_base": 0.0, "cgst": 0.0, "sgst": 0.0, "total_gst": 0.0, "rate": rate}
    
    half_rate_pct = (rate * 100.0) / 2.0
    denom = 100.0 + (rate * 100.0)
    cgst = round((amount * half_rate_pct) / denom, 2)
    sgst = round((amount * half_rate_pct) / denom, 2)
    taxable_base = round(amount / (1.0 + rate), 2)
    return {
        "taxable_base": taxable_base,
        "cgst": cgst,
        "sgst": sgst,
        "total_gst": cgst + sgst,
        "rate": rate
    }

class RealEstateGSTRules:
    """
    Implements Indian GST Real Estate Rules under Notification 11/2017-CT(R),
    Notification 03/2019-CT(R), and Schedule III of CGST Act.
    
    Updated with CA Office specific directives:
    1. GST NOT to be calculated on:
       - Refundable Deposit
       - Stamp Duty
       - Registration
       - Maintanance Deposit
       - Electricity Exp (AEC, AUDA, Torrent Power, etc.)
    2. Before BU vs After BU Rule:
       - Sun Footprint BU permission received as on 18/03/2025.
       - Advances received AFTER 18/03/2025 -> After BU -> EXEMPT FROM GST.
       - Advances received BEFORE 18/03/2025 -> Before BU -> TAXABLE.
    """
    def __init__(self, config: dict):
        self.config = config
        self.threshold_affordable = config.get("threshold_affordable_inr", 4500000)
        self.projects = config.get("projects", {})
        self.exclusions = config.get("non_gst_exclusions", {})

    def is_post_bu(self, project_name: str, transaction_date: datetime) -> bool:
        """
        Returns True if transaction occurred AFTER BU Permission date.
        e.g., Sun Footprint: BU date 18/03/2025.
        Receipts strictly after 18/03/2025 are EXEMPT from GST.
        """
        proj_cfg = self.projects.get(project_name, {})
        bu_date_str = proj_cfg.get("bu_permission_date")
        if not bu_date_str or not proj_cfg.get("has_bu", False):
            return False

        try:
            # Handles YYYY-MM-DD
            bu_dt = datetime.strptime(bu_date_str, "%Y-%m-%d")
            return transaction_date > bu_dt
        except Exception:
            return False

    def check_non_gst_category(self, item_name: str) -> str:
        """
        Identifies if an entry belongs to any of the 5 Non-GST exclusion categories:
        1. Refundable Deposit
        2. Stamp Duty
        3. Registration
        4. Maintanance Deposit
        5. Electricity Exp
        Returns category string or None.
        """
        text = item_name.lower().strip()
        for cat, keywords in self.exclusions.items():
            if any(kw in text for kw in keywords):
                return cat
        return None

    def classify_unit_tax_rate(self, project_name: str, agreement_value: float, is_commercial: bool = False, is_post_bu: bool = False) -> dict:
        """
        Determines applicable GST rate based on:
        - Post BU: 0% EXEMPT (Schedule III Entry 5)
        - Residential <= 45L: 1% (CGST 0.5%, SGST 0.5%)
        - Residential > 45L: 5% (CGST 2.5%, SGST 2.5%)
        - Commercial in RREP: 5%
        - Commercial Pure (Gravitas): 18% with 1/3rd Land Abatement (Effective 12%)
        """
        if is_post_bu:
            return {
                "rate": 0.0,
                "cgst_rate": 0.0,
                "sgst_rate": 0.0,
                "is_exempt": True,
                "category": "EXEMPT_POST_BU"
            }

        proj_cfg = self.projects.get(project_name, {})
        proj_type = proj_cfg.get("type", "Residential")

        if proj_type == "Commercial":
            return {
                "rate": 0.18,
                "cgst_rate": 0.09,
                "sgst_rate": 0.09,
                "is_exempt": False,
                "has_land_abatement": True,
                "land_fraction": 1.0 / 3.0,
                "category": "COMMERCIAL_CONSTRUCTION_18_WITH_ABATEMENT"
            }

        if is_commercial:
            rate = proj_cfg.get("commercial_rate", 0.05)
            return {
                "rate": rate,
                "cgst_rate": rate / 2.0,
                "sgst_rate": rate / 2.0,
                "is_exempt": False,
                "has_land_abatement": False,
                "category": "COMMERCIAL_RREP_5"
            }

        # Residential calculation
        if agreement_value > 0 and agreement_value <= self.threshold_affordable:
            rate = proj_cfg.get("default_residential_rate", 0.01)
            return {
                "rate": rate,
                "cgst_rate": rate / 2.0,
                "sgst_rate": rate / 2.0,
                "is_exempt": False,
                "has_land_abatement": False,
                "category": "RESIDENTIAL_AFFORDABLE_1"
            }
        else:
            rate = proj_cfg.get("higher_residential_rate", 0.05)
            return {
                "rate": rate,
                "cgst_rate": rate / 2.0,
                "sgst_rate": rate / 2.0,
                "is_exempt": False,
                "has_land_abatement": False,
                "category": "RESIDENTIAL_NON_AFFORDABLE_5"
            }

    def compute_net_taxable_receipt(self, gross_cr: float, deductions: dict) -> float:
        """
        Deducts all 5 non-GST categories:
        Net = Gross - Stamp Duty - Registration - Refundable Deposit - Maintenance Deposit - Electricity Exp - Cheques Bounced
        """
        total_deduction = sum(deductions.values())
        net = gross_cr - total_deduction
        return max(0.0, net)

    def extract_flat_no(self, ledger_name: str) -> str:
        """
        Extracts flat or shop code from ledger string:
        e.g., 'A-104,Gautam Prakash Narayan' -> 'A/0104'
        """
        match = re.match(r"^([A-Z0-9]+[/-][0-9]+)", ledger_name.strip())
        if match:
            return match.group(1).replace("-", "/")
        return ""
