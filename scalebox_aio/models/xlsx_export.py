# -*- coding: utf-8 -*-
# Part of Scalebox All-in-One ERP.
# Copyright (C) 2026 Scalebox For Digital Services. All Rights Reserved.

import io
import base64

from odoo import models, fields, _

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class ScaleboxXlsxExportMixin(models.AbstractModel):
    """Reusable Excel export. A report model lists its columns and rows,
    and this mixin produces a downloadable .xlsx via a standard attachment.

    Implementers provide:
        _xlsx_filename(self) -> str
        _xlsx_sheet_name(self) -> str
        _xlsx_title(self) -> str
        _xlsx_columns(self) -> list[(header, key, kind)]   kind in text/number/money
        _xlsx_rows(self) -> list[dict]                      keyed by column key
        optional _xlsx_meta(self) -> list[(label, value)]  header info block
    """

    _name = 'scalebox.xlsx.export.mixin'
    _description = 'Scalebox - Excel Export Mixin'

    def _xlsx_filename(self):
        return 'report.xlsx'

    def _xlsx_sheet_name(self):
        return 'Report'

    def _xlsx_title(self):
        return 'Report'

    def _xlsx_meta(self):
        return []

    def _xlsx_columns(self):
        return []

    def _xlsx_rows(self):
        return []

    def action_export_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            from odoo.exceptions import UserError
            raise UserError(_('The xlsxwriter library is not installed on the server.'))
        # ensure data is generated
        if hasattr(self, 'action_generate') and not self._xlsx_rows():
            self.action_generate()

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet(self._xlsx_sheet_name()[:31])
        ws.right_to_left()

        f_title = wb.add_format({'bold': True, 'font_size': 15, 'align': 'center'})
        f_meta = wb.add_format({'bold': True, 'font_size': 10})
        f_head = wb.add_format({
            'bold': True, 'bg_color': '#1a1a2e', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter'})
        f_text = wb.add_format({'border': 1})
        f_num = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        f_money = wb.add_format({'border': 1, 'num_format': '#,##0.00'})

        columns = self._xlsx_columns()
        ncols = max(len(columns), 1)
        ws.merge_range(0, 0, 0, ncols - 1, self._xlsx_title(), f_title)

        row = 2
        for label, value in self._xlsx_meta():
            ws.write(row, 0, label, f_meta)
            ws.write(row, 1, value)
            row += 1
        if self._xlsx_meta():
            row += 1

        for col, (header, key, kind) in enumerate(columns):
            ws.write(row, col, header, f_head)
            ws.set_column(col, col, 18)
        row += 1

        for rec in self._xlsx_rows():
            for col, (header, key, kind) in enumerate(columns):
                val = rec.get(key, '')
                if kind in ('number', 'money'):
                    ws.write_number(row, col, float(val or 0.0),
                                    f_money if kind == 'money' else f_num)
                else:
                    ws.write(row, col, '' if val is None else str(val), f_text)
            row += 1

        wb.close()
        output.seek(0)
        data = base64.b64encode(output.read())

        attachment = self.env['ir.attachment'].create({
            'name': self._xlsx_filename(),
            'type': 'binary',
            'datas': data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
