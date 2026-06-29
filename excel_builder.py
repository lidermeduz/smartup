"""
excel_builder.py — bitta deal'dan rasmingizdagi kabi "Спецификация"
Excel faylini yasaydi.

build_spec(deal, company) -> tayyor .xlsx fayl yo'lini qaytaradi.

MUHIM: deal lug'atidagi maydon nomlari ("deal_nomi", "items" va h.k.)
Smartup javobiga qarab farq qiladi. Pastdagi `_get` yordamida
maydonlarni o'z javobingizga moslang (TODO joylari).
"""

import os
import tempfile
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


def _g(d: dict, *keys, default=""):
    """Bir nechta mumkin bo'lgan kalitlardan birinchi topilganini oladi."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _date_only(value: str) -> str:
    """ '29.06.2026 14:30:00' -> '29.06.2026' (vaqtni kesib tashlaydi). """
    if not value:
        return ""
    return str(value).split(" ")[0]


def build_spec(deal: dict, company: dict) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Спецификация"

    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center")
    bold = Font(name="Arial", size=9, bold=True)
    reg = Font(name="Arial", size=9)
    small = Font(name="Arial", size=8)

    widths = [4, 26, 20, 8, 11, 14, 7, 12, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Sarlavha ── (haqiqiy maydonlar)
    spec_no = _g(deal, "delivery_number", "deal_id", default="—")
    spec_date = _date_only(_g(deal, "delivery_date", "deal_time", "booked_date"))
    dog_no = _g(deal, "contract_number", default="—")
    dog_date = ""  # javobda shartnoma sanasi yo'q; kerak bo'lsa qo'shing

    ws.merge_cells("C2:G2")
    ws["C2"] = f"Спецификация № {spec_no} от {spec_date}"
    ws["C2"].font = bold
    ws["C2"].alignment = center
    ws.merge_cells("C3:G3")
    ws["C3"] = f"Приложение к дог № {dog_no} от {dog_date}"
    ws["C3"].font = bold
    ws["C3"].alignment = center

    # ── Postavshik (tashkilotning o'zi — config'dan, doimiy) ──
    supplier_lines = [
        f'Поставщик: {company.get("supplier_name", company["name"])}',
        f'АДРЕС: {company.get("supplier_address", "")}',
        f'ТЕЛ: {company.get("supplier_phone", "")}',
        f'ИНН: {company.get("supplier_inn", "")}',
    ]
    # ── Pokupatel (deal'dan: mijoz) ──
    buyer_lines = [
        f'ПОКУПАТЕЛЬ: {_g(deal, "person_name")}',
        f'АДРЕС: {_g(deal, "delivery_address_full", "delivery_address_short")}',
        f'ТЕЛ: ',  # javobda mijoz telefoni yo'q
        f'ИНН: {_g(deal, "person_tin")}',
    ]
    for i, text in enumerate(supplier_lines):
        r = 5 + i
        ws.merge_cells(f"A{r}:E{r}")
        ws[f"A{r}"] = text
        ws[f"A{r}"].font = small
        ws[f"A{r}"].alignment = left
    for i, text in enumerate(buyer_lines):
        r = 5 + i
        ws.merge_cells(f"F{r}:I{r}")
        ws[f"F{r}"] = text
        ws[f"F{r}"].font = small
        ws[f"F{r}"].alignment = left

    # ── Jadval sarlavhasi (10-11 qatorlar) ──
    single = {
        "A": "№", "B": "НОМЕНКЛАТУРА", "C": "ИКПУ", "D": "кол-во",
        "E": "Цена", "F": "Стоимость поставки",
        "I": "Стоим. Поставки с учетом НДС",
    }
    for col, text in single.items():
        ws.merge_cells(f"{col}10:{col}11")
        ws[f"{col}10"] = text
        ws[f"{col}10"].font = bold
        ws[f"{col}10"].alignment = center
    ws.merge_cells("G10:H10")
    ws["G10"] = "НДС"
    ws["G10"].font = bold
    ws["G10"].alignment = center
    ws["G11"] = "ставка"
    ws["H11"] = "сумма"
    ws["G11"].font = bold
    ws["H11"].font = bold
    ws["G11"].alignment = center
    ws["H11"].alignment = center
    for col in "ABCDEFGHI":
        for row in (10, 11):
            ws[f"{col}{row}"].border = box

    # ── Tovarlar (order_products) ──
    items = _g(deal, "order_products", default=[])
    num_fmt = "#,##0.00"
    start = 12
    r = start
    for idx, it in enumerate(items, start=1):
        name = _g(it, "product_name")
        # ИКПУ (МХИК): javobda alohida maydon yo'q. Tizimingizda qaysi
        # maydonda kelishini tekshiring. Hozircha product_local_code -> product_code:
        ikpu = _g(it, "product_local_code", "product_code")
        qty = float(_g(it, "sold_quant", "order_quant", default=0) or 0)
        price = float(_g(it, "product_price", default=0) or 0)
        vat = float(_g(it, "vat_percent", default=12) or 12)

        ws[f"A{r}"] = idx
        ws[f"B{r}"] = name
        ws[f"C{r}"] = ikpu
        ws[f"D{r}"] = qty
        ws[f"E{r}"] = price
        ws[f"F{r}"] = f"=D{r}*E{r}"
        ws[f"G{r}"] = vat
        ws[f"H{r}"] = f"=F{r}*G{r}/100"
        ws[f"I{r}"] = f"=F{r}+H{r}"
        for col in "ABCDEFGHI":
            cell = ws[f"{col}{r}"]
            cell.border = box
            cell.font = reg
            if col in "DEFHI":
                cell.number_format = num_fmt
                cell.alignment = right
            elif col == "B":
                cell.alignment = left
            else:
                cell.alignment = center
        r += 1

    # ── Итого ──
    tr = r
    ws[f"B{tr}"] = "итого"
    ws[f"B{tr}"].font = bold
    ws[f"B{tr}"].alignment = center
    ws[f"D{tr}"] = f"=SUM(D{start}:D{r-1})"
    ws[f"F{tr}"] = f"=SUM(F{start}:F{r-1})"
    ws[f"H{tr}"] = f"=SUM(H{start}:H{r-1})"
    ws[f"I{tr}"] = f"=SUM(I{start}:I{r-1})"
    for col in "ABCDEFGHI":
        cell = ws[f"{col}{tr}"]
        cell.border = box
        if col in "DFHI":
            cell.number_format = num_fmt
            cell.alignment = right
            cell.font = bold

    # ── Pastki qism ──
    fr = tr + 2
    ws.merge_cells(f"A{fr}:F{fr}")
    ws[f"A{fr}"] = "Всего отпущено на сумму:"
    ws[f"A{fr}"].font = bold
    ws[f"G{fr}"] = "сум"
    ws[f"G{fr}"].font = bold

    sr = fr + 2
    ws[f"A{sr}"] = "ПОСТАВЩИК"
    ws[f"A{sr}"].font = bold
    ws[f"F{sr}"] = "ПОКУПАТЕЛЬ"
    ws[f"F{sr}"].font = bold
    dr = sr + 2
    ws[f"A{dr}"] = f'Директор: {company.get("supplier_director", "")} ______________'
    ws[f"A{dr}"].font = reg
    ws[f"F{dr}"] = "Директор: ______________"
    ws[f"F{dr}"].font = reg

    # ── Sariq eslatma ──
    nr = dr + 3
    ws.merge_cells(f"A{nr}:I{nr+1}")
    note = ws[f"A{nr}"]
    note.value = ("Эслатма: Ишончномани ва тулов топширикномасини биологик "
                  "фаол кушимчалар учун деб утказинг !!!")
    note.font = Font(name="Arial", size=10, bold=True, color="C00000")
    note.alignment = Alignment(horizontal="center", vertical="center",
                               wrap_text=True)
    yellow = PatternFill("solid", start_color="FFFF00")
    for col in "ABCDEFGHI":
        ws[f"{col}{nr}"].fill = yellow
        ws[f"{col}{nr+1}"].fill = yellow

    ws.page_setup.orientation = "landscape"
    ws.print_options.horizontalCentered = True

    # Faylni vaqtinchalik papkaga saqlaymiz
    deal_id = _g(deal, "deal_id", "id", default="deal")
    path = os.path.join(tempfile.gettempdir(),
                        f"Spetsifikatsiya_{company['name']}_{deal_id}.xlsx")
    wb.save(path)
    return path
