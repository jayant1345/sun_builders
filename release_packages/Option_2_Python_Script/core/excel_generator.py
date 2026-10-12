import os
import re
import shutil
import calendar
from datetime import datetime
import openpyxl

class ExcelGenerator:
    """
    Generates CA-standard multi-sheet GSTR-1 Excel files with live formulas.
    """
    def __init__(self, template_path: str):
        self.template_path = template_path

    @staticmethod
    def parse_month_year(target_month_str: str):
        """
        Parses a month string like 'SEP-26', 'SEP 2026', 'SEPTEMBER-2026'
        into (month_abbr, month_full, short_year, full_year, month_num, last_day).
        """
        months_map = {
            "JAN": (1, "JANUARY"), "FEB": (2, "FEBRUARY"), "MAR": (3, "MARCH"),
            "APR": (4, "APRIL"), "MAY": (5, "MAY"), "JUN": (6, "JUNE"),
            "JUL": (7, "JULY"), "AUG": (8, "AUGUST"), "SEP": (9, "SEPTEMBER"),
            "OCT": (10, "OCTOBER"), "NOV": (11, "NOVEMBER"), "DEC": (12, "DECEMBER")
        }
        s = (target_month_str or "SEP-26").strip().upper()
        
        # Find month
        m_num = 9
        m_abbr = "SEP"
        m_full = "SEPTEMBER"
        for k, (num, full) in months_map.items():
            if k in s or full in s:
                m_num = num
                m_abbr = k
                m_full = full
                break

        # Find year
        y_match = re.search(r'20(\d{2})', s)
        if y_match:
            short_y = y_match.group(1)
            full_y = "20" + short_y
        else:
            y2 = re.search(r'[\'\-_/\s](\d{2})\b', s)
            if y2:
                short_y = y2.group(1)
                full_y = "20" + short_y
            else:
                short_y = "26"
                full_y = "2026"

        last_day = calendar.monthrange(int(full_y), m_num)[1]
        return m_abbr, m_full, short_y, full_y, m_num, last_day

    def generate_monthly_workbook(self, target_month_str: str, project_data: dict, output_path: str) -> str:
        """
        Creates a new workbook from template, updates month headers, injects unit-wise
        collections for the target tax period, pre-evaluates and caches formula values
        for seamless display in Protected View, and saves with intact live formulas.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Copy template directly to preserve exact styles, merged cells, fonts, and formulas
        shutil.copy2(self.template_path, output_path)

        wb = openpyxl.load_workbook(output_path)
        wb.calculation.fullCalcOnLoad = True

        m_abbr, m_full, short_y, full_y, m_num, last_day = self.parse_month_year(target_month_str)
        target_display = f"{m_abbr}-{short_y}"
        target_display_tick = f"{m_abbr}'{short_y}"
        last_date_obj = datetime(int(full_y), m_num, last_day)

        # Dictionary to store pre-evaluated numeric values: (sheet_name, cell_coord) -> number
        self.computed_values = {}

        # 1. Update Month headers, labels & dates across all sheets
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows():
                for cell in row:
                    val = cell.value
                    if isinstance(val, datetime):
                        # Update month-end date for JV entries
                        if val.year == 2026 or val.year == int(full_y):
                            cell.value = last_date_obj
                    elif isinstance(val, str) and val.strip():
                        # Replace August 2026 patterns with target month
                        new_val = val
                        new_val = re.sub(r"AUG\s*'\s*26\b", target_display_tick, new_val, flags=re.IGNORECASE)
                        new_val = re.sub(r'AUG[\s\-_]+26\b', target_display, new_val, flags=re.IGNORECASE)
                        new_val = re.sub(r'AUG26\b', target_display, new_val, flags=re.IGNORECASE)
                        new_val = re.sub(r'AUGUST[\s\-_]+2026\b', f"{m_full} {full_y}", new_val, flags=re.IGNORECASE)
                        new_val = re.sub(r'AUGUST[\s\-_]+26\b', f"{m_full}-{short_y}", new_val, flags=re.IGNORECASE)
                        if new_val != val:
                            cell.value = new_val

        # 2. Populate Member Collection Sheets
        self._populate_footprint_sheet(wb, project_data.get("010010") or project_data.get("FOOTPRINT") or [])
        self._populate_parkwest_sheet(wb, project_data.get("010011") or project_data.get("PARK WEST") or [])

        # Set active sheet to member collection matching CA presentation
        if "SUN PARK WEST- MEMBER COLL." in wb.sheetnames:
            wb.active = wb["SUN PARK WEST- MEMBER COLL."]

        wb.save(output_path)

        # 3. Inject pre-computed cached values into XML so Excel Protected View displays numbers immediately
        self._inject_cached_xml_values(output_path)

        print(f"[ExcelGenerator] Generated finalized GST workbook: {output_path}")
        return output_path

    def _populate_footprint_sheet(self, wb, vouchers):
        """
        Populates SUN REALTY FOOTPRINT- MEMBERS with actual target month vouchers.
        Follows CA directives:
        1. Creditors/vendors/non-GST pass-throughs/cancelled bookings/implausible amounts excluded.
        2. Flats purchased after BU permission are 0% GST (Completely Exempt).
        3. Tax on Before-BU advances calculated considering the receipt as inclusive of tax base.
        4. Injects pre-evaluated cached values for all populated and empty template rows.
        """
        sheet_name = "SUN REALTY FOOTPRINT- MEMBERS"
        if sheet_name not in wb.sheetnames:
            return
        ws = wb[sheet_name]

        # 1. Clear residential rows (9 to 217) and reset default formulas
        for r in range(9, 218):
            ws.cell(r, 1).value = None
            ws.cell(r, 2).value = None
            ws.cell(r, 3).value = None
            ws.cell(r, 4).value = None
            ws.cell(r, 5).value = f'=+D{r}'
            ws.cell(r, 6).value = None
            ws.cell(r, 7).value = f'=+F{r}'
            ws.cell(r, 8).value = None
            ws.cell(r, 9).value = None
            ws.cell(r, 10).value = None
            ws.cell(r, 11).value = None
            ws.cell(r, 12).value = None
            ws.cell(r, 13).value = f'=C{r}-D{r}-F{r}-H{r}'
            ws.cell(r, 14).value = f'=ROUND(M{r}*0.5/101, 2)'
            self.computed_values[(sheet_name, f'E{r}')] = 0
            self.computed_values[(sheet_name, f'G{r}')] = 0
            self.computed_values[(sheet_name, f'M{r}')] = 0
            self.computed_values[(sheet_name, f'N{r}')] = 0

        # 2. Clear shop rows (223 to 229) and reset default formulas
        for r in range(223, 230):
            ws.cell(r, 1).value = None
            ws.cell(r, 2).value = None
            ws.cell(r, 3).value = None
            ws.cell(r, 4).value = None
            ws.cell(r, 5).value = f'=+D{r}'
            ws.cell(r, 6).value = None
            ws.cell(r, 7).value = f'=+F{r}'
            ws.cell(r, 8).value = None
            ws.cell(r, 9).value = None
            ws.cell(r, 10).value = None
            ws.cell(r, 11).value = None
            ws.cell(r, 12).value = None
            ws.cell(r, 13).value = f'=C{r}-D{r}-F{r}'
            ws.cell(r, 14).value = f'=ROUND(M{r}*2.5/105, 2)'
            self.computed_values[(sheet_name, f'E{r}')] = 0
            self.computed_values[(sheet_name, f'G{r}')] = 0
            self.computed_values[(sheet_name, f'M{r}')] = 0
            self.computed_values[(sheet_name, f'N{r}')] = 0

        if not vouchers:
            return

        # 3. Group vouchers by unit
        res_units = {}
        shop_units = {}
        total_after_bu_exempt = 0.0
        tot_res_net = 0.0
        tot_res_cgst = 0.0

        for v in vouchers:
            party = str(v.get("party_name") or v.get("name") or v.get("member_name") or "").strip()
            pass_through_type = v.get("_pass_through_type")
            is_income_v = bool(v.get("_is_income", v.get("is_income", True)))
            if not is_income_v and pass_through_type not in ("reg_fee", "stamp_duty"):
                continue

            unit = str(v.get("unit_no") or v.get("unit") or v.get("flat_no") or "").strip()
            amt = float(v.get("cr_amount") or v.get("amount") or 0)
            reg_fee = amt if pass_through_type == "reg_fee" else 0.0
            stamp_duty = amt if pass_through_type == "stamp_duty" else 0.0
            unit_rate = float(v.get("_tax_rate") or 0.01)

            unit_is_after_bu = bool(v.get("_is_after_bu"))
            if unit_is_after_bu:
                total_after_bu_exempt += max(0.0, amt - reg_fee - stamp_duty)

            if re.match(r'^[A-Za-z]\s*[\-_/]', unit):
                if unit not in res_units:
                    res_units[unit] = {"unit": unit, "party": party, "amount": 0.0, "reg_fee": 0.0, "stamp_duty": 0.0, "is_after_bu": unit_is_after_bu, "rate": unit_rate}
                res_units[unit]["amount"] += amt
                res_units[unit]["reg_fee"] += reg_fee
                res_units[unit]["stamp_duty"] += stamp_duty
                if party and not res_units[unit]["party"]:
                    res_units[unit]["party"] = party
                if unit_is_after_bu:
                    res_units[unit]["is_after_bu"] = True
            else:
                if not unit and not any(k in party.lower() for k in ["shop", "sh-", "sh "]):
                    continue
                u_key = unit or f"Shop-{party[:15]}"
                if u_key not in shop_units:
                    shop_units[u_key] = {"unit": unit or "", "party": party, "amount": 0.0, "reg_fee": 0.0, "stamp_duty": 0.0, "is_after_bu": unit_is_after_bu, "rate": unit_rate}
                shop_units[u_key]["amount"] += amt
                shop_units[u_key]["reg_fee"] += reg_fee
                shop_units[u_key]["stamp_duty"] += stamp_duty
                if party and not shop_units[u_key]["party"]:
                    shop_units[u_key]["party"] = party
                if unit_is_after_bu:
                    shop_units[u_key]["is_after_bu"] = True

        # 4. Populate residential units into rows 9..217
        r_idx = 9
        for u, data in sorted(res_units.items()):
            if r_idx >= 218:
                break
            ws.cell(r_idx, 1).value = data["unit"]
            ws.cell(r_idx, 2).value = data["party"]
            ws.cell(r_idx, 3).value = data["amount"]
            if data["reg_fee"] > 0:
                ws.cell(r_idx, 4).value = data["reg_fee"]
                self.computed_values[(sheet_name, f'E{r_idx}')] = round(data["reg_fee"], 2)
            if data["stamp_duty"] > 0:
                ws.cell(r_idx, 6).value = data["stamp_duty"]
                self.computed_values[(sheet_name, f'G{r_idx}')] = round(data["stamp_duty"], 2)

            # Tax Calculation:
            if data.get("is_after_bu"):
                # Flats purchased after BU permission are 0% GST (Completely Exempt)
                ws.cell(r_idx, 13).value = 0
                ws.cell(r_idx, 14).value = 0
                self.computed_values[(sheet_name, f'M{r_idx}')] = 0
                self.computed_values[(sheet_name, f'N{r_idx}')] = 0
            else:
                rate = data.get("rate", 0.01)
                half_pct, denom = rate * 50, 100 + rate * 100
                ws.cell(r_idx, 13).value = f'=C{r_idx}-D{r_idx}-F{r_idx}-H{r_idx}'
                ws.cell(r_idx, 14).value = f'=ROUND(M{r_idx}*{half_pct:g}/{denom:g}, 2)'

                net_val = max(0.0, data["amount"] - data["reg_fee"] - data["stamp_duty"])
                cgst_val = round(net_val * half_pct / denom, 2)
                self.computed_values[(sheet_name, f'M{r_idx}')] = round(net_val, 2)
                self.computed_values[(sheet_name, f'N{r_idx}')] = cgst_val
                tot_res_net += net_val
                tot_res_cgst += cgst_val

            r_idx += 1

        # 5. Populate shop units into rows 223..229
        s_idx = 223
        for u, data in sorted(shop_units.items()):
            if s_idx >= 230:
                break
            ws.cell(s_idx, 1).value = data["unit"]
            ws.cell(s_idx, 2).value = data["party"]
            ws.cell(s_idx, 3).value = data["amount"]
            if data["reg_fee"] > 0:
                ws.cell(s_idx, 4).value = data["reg_fee"]
                self.computed_values[(sheet_name, f'E{s_idx}')] = round(data["reg_fee"], 2)
            if data["stamp_duty"] > 0:
                ws.cell(s_idx, 6).value = data["stamp_duty"]
                self.computed_values[(sheet_name, f'G{s_idx}')] = round(data["stamp_duty"], 2)

            if data.get("is_after_bu"):
                ws.cell(s_idx, 13).value = 0
                ws.cell(s_idx, 14).value = 0
                self.computed_values[(sheet_name, f'M{s_idx}')] = 0
                self.computed_values[(sheet_name, f'N{s_idx}')] = 0
            else:
                rate = data.get("rate", 0.05)
                half_pct, denom = rate * 50, 100 + rate * 100
                ws.cell(s_idx, 13).value = f'=C{s_idx}-D{s_idx}-F{s_idx}'
                ws.cell(s_idx, 14).value = f'=ROUND(M{s_idx}*{half_pct:g}/{denom:g}, 2)'
                net_val = max(0.0, data["amount"] - data["reg_fee"] - data["stamp_duty"])
                cgst_val = round(net_val * half_pct / denom, 2)
                self.computed_values[(sheet_name, f'M{s_idx}')] = round(net_val, 2)
                self.computed_values[(sheet_name, f'N{s_idx}')] = cgst_val
            s_idx += 1

        # Track Footprint grand totals for XML cache
        self.computed_values[(sheet_name, 'M230')] = round(tot_res_net, 2)
        self.computed_values[(sheet_name, 'N230')] = round(tot_res_cgst, 2)

        # 6. Update After-BU Exempt Sale in FOOTPRINT- CALCULATION Row 17
        if "FOOTPRINT- CALCULATION" in wb.sheetnames:
            ws_calc = wb["FOOTPRINT- CALCULATION"]
            if total_after_bu_exempt > 0:
                ws_calc.cell(17, 2).value = round(total_after_bu_exempt, 2)
                self.computed_values[("FOOTPRINT- CALCULATION", "B17")] = round(total_after_bu_exempt, 2)
            ws_calc.cell(6, 4).value = "=ROUND(B6*0.5/101, 2)"
            ws_calc.cell(6, 5).value = "=+D6"
            self.computed_values[("FOOTPRINT- CALCULATION", "B11")] = round(tot_res_net, 2)
            self.computed_values[("FOOTPRINT- CALCULATION", "D11")] = round(tot_res_cgst, 2)
            self.computed_values[("FOOTPRINT- CALCULATION", "E11")] = round(tot_res_cgst, 2)
            self.computed_values[("FOOTPRINT- CALCULATION", "F11")] = round(tot_res_cgst * 2, 2)

    def _populate_parkwest_sheet(self, wb, vouchers):
        """
        Populates SUN PARK WEST- MEMBER COLL. with target month vouchers.
        Follows CA presentation standards (Screenshot 1):
        1. Col K (NET RECEIPT) = C - D - F.
        2. Col L (GST) = +K*1%/2.
        3. Empty rows maintain default formulas evaluating to 0 ('-' in Excel currency format).
        4. Injects pre-evaluated cached values for all cells.
        """
        sheet_name = "SUN PARK WEST- MEMBER COLL."
        if sheet_name not in wb.sheetnames:
            return
        ws = wb[sheet_name]

        # Clear residential rows 9..73 and reset default formulas
        for r in range(9, 74):
            ws.cell(r, 1).value = None
            ws.cell(r, 2).value = None
            ws.cell(r, 3).value = None
            ws.cell(r, 4).value = None
            ws.cell(r, 5).value = f'=+D{r}'
            ws.cell(r, 6).value = None
            ws.cell(r, 7).value = f'=+F{r}'
            ws.cell(r, 8).value = None
            ws.cell(r, 9).value = None
            ws.cell(r, 11).value = f'=C{r}-D{r}-F{r}'
            ws.cell(r, 12).value = f'=+K{r}*1%/2'
            self.computed_values[(sheet_name, f'E{r}')] = 0
            self.computed_values[(sheet_name, f'G{r}')] = 0
            self.computed_values[(sheet_name, f'K{r}')] = 0
            self.computed_values[(sheet_name, f'L{r}')] = 0

        if not vouchers:
            return

        units_map = {}
        for v in vouchers:
            party = str(v.get("party_name") or v.get("name") or v.get("member_name") or "").strip()
            pass_through_type = v.get("_pass_through_type")
            is_income_v = bool(v.get("_is_income", v.get("is_income", True)))
            if not is_income_v and pass_through_type not in ("reg_fee", "stamp_duty"):
                continue

            unit = str(v.get("unit_no") or v.get("unit") or v.get("flat_no") or "").strip()
            amt = float(v.get("cr_amount") or v.get("amount") or 0)
            reg_fee = amt if pass_through_type == "reg_fee" else 0.0
            stamp_duty = amt if pass_through_type == "stamp_duty" else 0.0
            unit_rate = float(v.get("_tax_rate") or 0.01)
            unit_is_after_bu = bool(v.get("_is_after_bu"))

            if unit not in units_map:
                units_map[unit] = {"unit": unit, "party": party, "amount": 0.0, "reg_fee": 0.0, "stamp_duty": 0.0, "is_after_bu": unit_is_after_bu, "rate": unit_rate}
            units_map[unit]["amount"] += amt
            units_map[unit]["reg_fee"] += reg_fee
            units_map[unit]["stamp_duty"] += stamp_duty
            if party and not units_map[unit]["party"]:
                units_map[unit]["party"] = party
            if unit_is_after_bu:
                units_map[unit]["is_after_bu"] = True

        r_idx = 9
        tot_pw_net = 0.0
        tot_pw_gst = 0.0

        for u, data in sorted(units_map.items()):
            if r_idx >= 74:
                break
            ws.cell(r_idx, 1).value = data["unit"]
            ws.cell(r_idx, 2).value = data["party"]
            ws.cell(r_idx, 3).value = data["amount"]
            if data["reg_fee"] > 0:
                ws.cell(r_idx, 4).value = data["reg_fee"]
                self.computed_values[(sheet_name, f'E{r_idx}')] = round(data["reg_fee"], 2)
            if data["stamp_duty"] > 0:
                ws.cell(r_idx, 6).value = data["stamp_duty"]
                self.computed_values[(sheet_name, f'G{r_idx}')] = round(data["stamp_duty"], 2)

            if data.get("is_after_bu"):
                ws.cell(r_idx, 11).value = 0
                ws.cell(r_idx, 12).value = 0
                self.computed_values[(sheet_name, f'K{r_idx}')] = 0
                self.computed_values[(sheet_name, f'L{r_idx}')] = 0
            else:
                ws.cell(r_idx, 11).value = f'=C{r_idx}-D{r_idx}-F{r_idx}'
                ws.cell(r_idx, 12).value = f'=+K{r_idx}*1%/2'
                net_val = max(0.0, data["amount"] - data["reg_fee"] - data["stamp_duty"])
                gst_val = round(net_val * 0.01 / 2.0, 2)
                self.computed_values[(sheet_name, f'K{r_idx}')] = round(net_val, 2)
                self.computed_values[(sheet_name, f'L{r_idx}')] = gst_val
                tot_pw_net += net_val
                tot_pw_gst += gst_val
            r_idx += 1

        self.computed_values[(sheet_name, 'K74')] = round(tot_pw_net, 2)
        self.computed_values[(sheet_name, 'L74')] = round(tot_pw_gst, 2)

        if "SUN PARK WEST" in wb.sheetnames:
            self.computed_values[("SUN PARK WEST", "B10")] = round(tot_pw_net, 2)
            self.computed_values[("SUN PARK WEST", "D10")] = round(tot_pw_gst, 2)
            self.computed_values[("SUN PARK WEST", "E10")] = round(tot_pw_gst, 2)
            self.computed_values[("SUN PARK WEST", "F10")] = round(tot_pw_gst * 2, 2)

    def _inject_cached_xml_values(self, file_path: str):
        """
        Injects computed numerical values into the <v> tag of formula cells (<c><f>...</f></c>)
        inside xl/worksheets/sheet*.xml.
        When an Excel file is downloaded from the web, Microsoft Excel opens it in PROTECTED VIEW.
        In Protected View, Excel disables formula evaluation and ONLY displays cached <v> values.
        Without <v>, formula cells render as completely blank/empty white cells.
        This post-processor guarantees that all calculated NET RECEIPT, GST, deductions, and sums
        are immediately visible even in Protected View, while keeping the live Excel formulas intact.
        """
        import zipfile
        import xml.etree.ElementTree as ET

        if not os.path.exists(file_path):
            return

        temp_out = file_path + ".tmp.xlsx"
        try:
            with zipfile.ZipFile(file_path, "r") as zin:
                wb_tree = ET.fromstring(zin.read("xl/workbook.xml"))
                rels_tree = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
                rel_map = {rel.get("Id"): rel.get("Target") for rel in rels_tree}

                sheet_to_file = {}
                for sheet in wb_tree.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
                    s_name = sheet.get("name")
                    r_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                    target = rel_map.get(r_id, "")
                    if not target.startswith("worksheets/"):
                        target = "worksheets/" + target.split("/")[-1]
                    sheet_to_file[s_name] = "xl/" + target

            file_to_sheet = {v: k for k, v in sheet_to_file.items()}
            ET.register_namespace("", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

            with zipfile.ZipFile(file_path, "r") as zin, zipfile.ZipFile(temp_out, "w") as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename in file_to_sheet:
                        s_name = file_to_sheet[item.filename]
                        tree = ET.fromstring(data)
                        modified = False
                        for c in tree.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                            coord = c.get("r")
                            key = (s_name, coord)
                            has_f = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f") is not None
                            if key in self.computed_values:
                                val = self.computed_values[key]
                                v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                if v is None:
                                    v = ET.SubElement(c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                if isinstance(val, (int, float)):
                                    if val == int(val):
                                        v.text = str(int(val))
                                    else:
                                        v.text = f"{val:.2f}".rstrip("0").rstrip(".")
                                else:
                                    v.text = str(val)
                                modified = True
                            elif has_f:
                                v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                if v is None:
                                    v = ET.SubElement(c, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                if not v.text:
                                    v.text = "0"
                                modified = True
                        if modified:
                            data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
                    zout.writestr(item, data)

            shutil.move(temp_out, file_path)
        except Exception as e:
            print(f"[ExcelGenerator] Warning during _inject_cached_xml_values: {e}")
            if os.path.exists(temp_out):
                try:
                    os.remove(temp_out)
                except Exception:
                    pass

