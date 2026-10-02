import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime

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
        """Checks if Tally is running by sending a real Tally XML request and
        verifying the response actually parses as Tally XML. A bare HTTP 200
        is not enough, since other local dev tools can also listen on 9000."""
        try:
            req_xml = """<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>List of Companies</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY></ENVELOPE>"""
            req = urllib.request.Request(self.url, data=req_xml.encode('utf-8'), headers={'Content-Type': 'text/xml'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    return False
                ET.fromstring(resp.read())
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
                    raw_xml = resp.read().decode('utf-8', errors='ignore')
                    root = ET.fromstring(raw_xml)
                    companies = [elem.text for elem in root.findall(".//COMPANYNAME") if elem.text]
                    if not companies:
                        companies = [elem.text for elem in root.findall(".//NAME") if elem.text and not elem.text.startswith("$$")]
                    if companies:
                        return companies
            except Exception as e:
                pass
        return []

    def export_vouchers_xml(self, company_name: str, from_date_yyyymmdd: str = "20000101", to_date_yyyymmdd: str = "20991231") -> str:
        """
        Exports all vouchers for the specified company and date range in native Tally XML format.
        """
        req_xml = f"""<ENVELOPE>
            <HEADER>
                <VERSION>1</VERSION>
                <TALLYREQUEST>Export</TALLYREQUEST>
                <TYPE>Data</TYPE>
                <ID>Voucher Register</ID>
            </HEADER>
            <BODY>
                <DESC>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                        <SVFROMDATE>{from_date_yyyymmdd}</SVFROMDATE>
                        <SVTODATE>{to_date_yyyymmdd}</SVTODATE>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                </DESC>
            </BODY>
        </ENVELOPE>"""
        req = urllib.request.Request(self.url, data=req_xml.encode('utf-8'), headers={'Content-Type': 'text/xml'})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.read().decode('utf-8', errors='ignore')

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
                        "amount": amount  # in Tally negative is Credit, positive is Debit
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
