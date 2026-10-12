import re
from datetime import datetime

CREDITOR_KEYWORDS = [
    r'\bcreditor\b', r'\bvendor\b', r'\bsupplier\b', r'\bcontractor\b', r'\bsubcontractor\b',
    r'\bpurchase\b', r'\bmaterial\b', r'\belectric\b', r'\belectricity\b', r'\bcable\b', r'\bnotary\b',
    r'\bstamp duty\b', r'\bregistration\b', r'\breg fee\b', r'\bsale deed\b', r'\bsales deed\b', r'\bats\b',
    r'\bmaintenance\b', r'\bmaintanance\b', r'\bauda\b', r'\baec\b', r'\btorrent\b',
    r'\bconsultant\b', r'\bprofessional fee\b', r'\blegal fee\b', r'\baudit fee\b', r'\bbank charges\b',
    r'\bcourier\b', r'\bprinting\b', r'\bstationery\b', r'\bfreight\b', r'\btransport\b', r'\broadlines\b', r'\blogistics\b',
    r'\blabour\b', r'\blabor\b', r'\bcement\b', r'\bsteel\b', r'\bsand supplier\b', r'\bbricks\b', r'\btiles\b', r'\bplumbing\b', r'\bsanitary\b',
    r'\bpaint\b', r'\bsecurity services\b', r'\bwater charges\b', r'\bdiesel\b', r'\bfuel\b', r'\brepair\b',
    r'\bcorporation\b', r'\benterprises\b', r'\btraders\b', r'\bbuildcon\b', r'\binfra\b', r'\bagency\b', r'\bagencies\b',
    r'\bgas\b', r'\bgujarat gas\b', r'\bhardware\b', r'\bplywood\b', r'\bglass\b', r'\baluminium\b', r'\baluminum\b', r'\biron\b',
    r'\br\.m\.c\b', r'\brmc\b', r'\breadymix\b', r'\bconcrete\b', r'\bearthmovers\b', r'\bexcavation\b', r'\bcrane\b', r'\bbank coll\b',
    r'\baxis bank\b', r'\bicici bank\b', r'\bhdfc bank\b', r'\bsbi\b'
]

def is_creditor_party(party_str: str, raw_name: str = "", narr: str = "") -> bool:
    """Returns True if party name or narration indicates a vendor/creditor/contractor."""
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}".lower()
    for kw in CREDITOR_KEYWORDS:
        if re.search(kw, combined):
            return True
    return False

def is_after_bu_member(party_str: str, raw_name: str = "", narr: str = "") -> bool:
    """
    Returns True if member ledger/narration contains 'After BU' or variations ('Af Bu', 'Afterbu'),
    indicating flat purchased after BU permission (Schedule III Entry 5 - 0% GST).
    """
    combined = f"{party_str or ''} {raw_name or ''} {narr or ''}".lower()
    return bool(re.search(r'(?:after|aft|af)\s*[\-_]?\s*bu\b', combined) or 'afterbu' in combined)

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
