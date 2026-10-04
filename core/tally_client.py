import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import re
from datetime import datetime

def clean_tally_xml(xml_str: str) -> str:
    """Removes non-printable chars, fixes unescaped ampersands, and cleans control entities."""
    s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', xml_str)
    s = re.sub(r'&#(?:0?[0-8]|1[1-2]|1[4-9]|2[0-9]|3[0-1]);', '', s)
    s = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', s)
    return s

class TallyClient:
    """
    Communicates with Tally.ERP 9 / TallyPrime via local XML/HTTP API on port 9000.
    """
    def __init__(self, host="localhost", port=9000):
        if isinstance(host, str) and (host.startswith("http://") or host.startswith("https://")):
            self.url = host.rstrip('/')
        else:
            self.url = f"http://{host}:{port}"

    def is_connected(self) -> bool:
        """Checks if Tally is running and responding to XML requests."""
        try:
            req_xml = """<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>List of Companies</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>"""
            req = urllib.request.Request(self.url, data=req_xml.encode('utf-8'), headers={'Content-Type': 'text/xml'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    return False
                raw = resp.read().decode('utf-8', errors='ignore')
                ET.fromstring(clean_tally_xml(raw))
                return True
        except Exception:
            return False

    def get_loaded_companies(self) -> list:
        """Returns list of currently active / open companies in Tally."""
        for req_type in ["Collection", "Data"]:
            req_xml = f"""<ENVELOPE>
                <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>{req_type}</TYPE><ID>List of Companies</ID></HEADER>
                <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
            </ENVELOPE>"""
            try:
                req = urllib.request.Request(self.url, data=req_xml.encode('utf-8'), headers={'Content-Type': 'text/xml'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw_xml = clean_tally_xml(resp.read().decode('utf-8', errors='ignore'))
                    root = ET.fromstring(raw_xml)
                    companies = [elem.text for elem in root.findall(".//COMPANYNAME") if elem.text]
                    if not comps:
                        companies = [elem.text for elem in root.findall(".//NAME") if elem.text and not elem.text.startswith("$$")]
                    if companies:
                        return companies
            except Exception:
                pass
        return []

    def export_all_vouchers_xml(self, company_name: str) -> str:
        """
        Exports all vouchers for the specified company via robust TDL Collection.
        """
        vch_req = f"""<ENVELOPE>
            <HEADER>
                <VERSION>1</VERSION>
                <TALLYREQUEST>Export</TALLYREQUEST>
                <TYPE>Collection</TYPE>
                <ID>CustomAllVouchers</ID>
            </HEADER>
            <BODY>
                <DESC>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                    <TDL>
                        <TDLMESSAGE>
                            <COLLECTION NAME="CustomAllVouchers" ISINITIALIZE="Yes">
                                <TYPE>Voucher</TYPE>
                                <FETCH>DATE, VOUCHERTYPENAME, VOUCHERNUMBER, NARRATION, ALLLEDGERENTRIES.LIST</FETCH>
                            </COLLECTION>
                        </TDLMESSAGE>
                    </TDL>
                </DESC>
            </BODY>
        </ENVELOPE>"""

        req = urllib.request.Request(self.url, data=vch_req.encode('utf-8'), headers={'Content-Type': 'text/xml; charset=utf-8'})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return clean_tally_xml(resp.read().decode('utf-8', errors='ignore'))

    def parse_vouchers(self, raw_xml: str) -> list:
        """
        Parses raw Tally XML into structured voucher dictionaries.
        """
        vouchers = []
        try:
            root = ET.fromstring(raw_xml)
            for vch in root.findall(".//VOUCHER"):
                v_type = vch.findtext("VOUCHERTYPENAME", "")
                v_date_str = vch.findtext("DATE", "")
                v_num = vch.findtext("VOUCHERNUMBER", "")
                narration = vch.findtext("NARRATION", "")

                entries = []
                for ledger_entry in vch.findall(".//ALLLEDGERENTRIES.LIST"):
                    ledger_name = ledger_entry.findtext("LEDGERNAME", "")
                    amount_str = ledger_entry.findtext("AMOUNT", "0")
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        amount = 0.0
                    entries.append({
                        "ledger_name": ledger_name,
                        "amount": amount
                    })

                vouchers.append({
                    "voucher_type": v_type,
                    "date": v_date_str,
                    "voucher_number": v_num,
                    "narration": narration,
                    "entries": entries
                })
        except Exception as e:
            print(f"[TallyClient] XML Parsing error: {e}")
        return vouchers
