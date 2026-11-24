"""Xuất báo cáo Thống kê khai thác dạng Excel, theo đúng bộ lọc trên giao diện."""
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


def make_analytics_workbook(title, headers, rows, filter_info=None):
    """Mỗi lần xuất chỉ tạo một bảng, đầy đủ các trang theo phạm vi quyền hiện tại."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Thống kê"
    n = len(headers)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
    heading = ws.cell(1, 1, title)
    heading.font = Font(name="Arial", size=15, bold=True, color="17365D")
    heading.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 31

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=n)
    date_text = datetime.now().strftime("%d/%m/%Y %H:%M")
    subtitle = f"Xuất lúc: {date_text} · Toàn bộ dữ liệu khớp bộ lọc (không giới hạn phân trang)"
    if filter_info:
        subtitle += " · " + filter_info[:500]
    ws.cell(2, 1, subtitle).font = Font(name="Arial", size=10, italic=True, color="607080")
    ws.row_dimensions[2].height = 25

    for idx, name in enumerate(headers, 1):
        cell = ws.cell(4, idx, name)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245A81")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[4].height = 32

    for i, values in enumerate(rows, 5):
        for j, value in enumerate(values, 1):
            cell = ws.cell(i, j, value if value is not None else "")
            cell.font = Font(name="Arial", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if i % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="EDF4F8")
            if isinstance(value, (int, float)):
                cell.number_format = "#,##0.##"
        ws.row_dimensions[i].height = 26
    for j, name in enumerate(headers, 1):
        width = 14 if name in ("STT", "Kết quả") else min(48, max(17, len(str(name)) + 7))
        if j == 2:
            width = max(width, 27)
        ws.column_dimensions[get_column_letter(j)].width = width
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(n)}{max(4, ws.max_row)}"
    ws.sheet_view.showGridLines = False
    ws.print_options.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
