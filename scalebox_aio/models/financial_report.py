# -*- coding: utf-8 -*-
# Part of Scalebox All-in-One ERP.
# Copyright (C) 2026 Scalebox For Digital Services. All Rights Reserved.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ScaleboxFinancialReport(models.TransientModel):
    """Main financial reports: Balance Sheet - Profit & Loss - Cash Flow.

    Computed directly from posted journal items (account.move.line) with no intermediate tables.
    """

    _name = 'scalebox.financial.report'
    _description = 'Scalebox - Financial Reports'
    _inherit = ['scalebox.xlsx.export.mixin']

    report_type = fields.Selection([
        ('pl', 'Profit and Loss'),
        ('bs', 'Balance Sheet'),
        ('cf', 'Cash Flow'),
        ('tb', 'Trial Balance'),
    ], string='Report', required=True, default='pl')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        related='company_id.currency_id', readonly=True)
    date_from = fields.Date(
        string='From Date',
        default=lambda self: fields.Date.context_today(self).replace(month=1, day=1))
    date_to = fields.Date(
        string='To Date', required=True,
        default=fields.Date.context_today)
    line_ids = fields.One2many(
        'scalebox.financial.report.line', 'wizard_id', string='Lines')

    # ------------------------------------------------------------------
    # Data helpers (account.move.line aggregations)
    # ------------------------------------------------------------------
    def _base_domain(self, with_date_from=False):
        self.ensure_one()
        domain = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('date', '<=', self.date_to),
        ]
        if with_date_from and self.date_from:
            domain.append(('date', '>=', self.date_from))
        return domain

    def _sum_balance(self, extra_domain, with_date_from=False):
        res = self.env['account.move.line'].read_group(
            self._base_domain(with_date_from) + extra_domain,
            ['balance:sum'], [])
        return (res[0]['balance'] or 0.0) if res else 0.0

    def _by_account(self, extra_domain, with_date_from=False, fields_sum=None):
        """Group by account. Returns a list of (account name, values dict)."""
        fields_sum = fields_sum or ['balance:sum']
        groups = self.env['account.move.line'].read_group(
            self._base_domain(with_date_from) + extra_domain,
            fields_sum, ['account_id'])
        result = []
        for g in groups:
            result.append((g['account_id'][1] if g['account_id'] else _('Undefined'), g))
        return result

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------
    def action_generate(self):
        self.ensure_one()
        if self.report_type in ('pl', 'cf') and not self.date_from:
            raise UserError(_('Set the start date for this report.'))
        self.line_ids.unlink()
        builder = getattr(self, '_build_%s' % self.report_type)
        lines = builder()
        seq = 0
        vals_list = []
        for line in lines:
            name, balance, style = line[0], line[1], line[2]
            debit = line[3] if len(line) > 3 else 0.0
            credit = line[4] if len(line) > 4 else 0.0
            seq += 10
            vals_list.append({
                'wizard_id': self.id,
                'sequence': seq,
                'name': name,
                'balance': balance,
                'style': style,
                'debit': debit,
                'credit': credit,
            })
        self.env['scalebox.financial.report.line'].create(vals_list)
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self._fields['report_type'].selection).get(self.report_type),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_generate()
        return self.env.ref(
            'scalebox_aio.action_report_financial').report_action(self)

    # --- Excel export ---
    def _xlsx_title(self):
        return dict(self._fields['report_type'].selection).get(self.report_type)

    def _xlsx_filename(self):
        return '%s_%s.xlsx' % (self.report_type, self.date_to)

    def _xlsx_sheet_name(self):
        return self._xlsx_title()

    def _xlsx_meta(self):
        meta = []
        if self.report_type != 'bs':
            meta.append((_('From'), str(self.date_from)))
        meta.append((_('To') if self.report_type != 'bs' else _('As of'),
                     str(self.date_to)))
        return meta

    def _xlsx_columns(self):
        cols = [(_('Item'), 'name', 'text')]
        if self.report_type == 'tb':
            cols += [(_('Debit'), 'debit', 'money'),
                     (_('Credit'), 'credit', 'money')]
        cols.append((_('Amount'), 'balance', 'money'))
        return cols

    def _xlsx_rows(self):
        rows = []
        for line in self.line_ids:
            rows.append({
                'name': line.name,
                'debit': line.debit if line.style != 'header' else None,
                'credit': line.credit if line.style != 'header' else None,
                'balance': line.balance if line.style != 'header' else None,
            })
        return rows

    def _build_pl(self):
        """Profit and loss for the selected period."""
        lines = [(_('Revenue'), 0.0, 'header')]
        revenue_total = 0.0
        for name, g in self._by_account(
                [('account_id.internal_group', '=', 'income')], True):
            amount = -(g['balance'] or 0.0)
            revenue_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Revenue'), revenue_total, 'total'))

        lines.append((_('Expenses and Cost of Sales'), 0.0, 'header'))
        expense_total = 0.0
        for name, g in self._by_account(
                [('account_id.internal_group', '=', 'expense')], True):
            amount = g['balance'] or 0.0
            expense_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Expenses'), expense_total, 'total'))

        lines.append((_('Net Profit / (Loss)'),
                      revenue_total - expense_total, 'total'))
        return lines

    def _build_bs(self):
        """Balance sheet as of the selected date."""
        lines = [(_('Assets'), 0.0, 'header')]
        assets_total = 0.0
        for name, g in self._by_account(
                [('account_id.internal_group', '=', 'asset')]):
            amount = g['balance'] or 0.0
            assets_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Assets'), assets_total, 'total'))

        lines.append((_('Liabilities'), 0.0, 'header'))
        liabilities_total = 0.0
        for name, g in self._by_account(
                [('account_id.internal_group', '=', 'liability')]):
            amount = -(g['balance'] or 0.0)
            liabilities_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Liabilities'), liabilities_total, 'total'))

        lines.append((_('Equity'), 0.0, 'header'))
        equity_total = 0.0
        for name, g in self._by_account(
                [('account_id.internal_group', '=', 'equity')]):
            amount = -(g['balance'] or 0.0)
            equity_total += amount
            lines.append((name, amount, 'line'))
        # Unallocated earnings = inverse of income & expense account balances up to the date
        earnings = -self._sum_balance(
            [('account_id.internal_group', 'in', ('income', 'expense'))])
        lines.append((_('Net Earnings (Current & Unallocated)'),
                      earnings, 'line'))
        equity_total += earnings
        lines.append((_('Total Equity'), equity_total, 'total'))

        lines.append((_('Total Liabilities and Equity'),
                      liabilities_total + equity_total, 'total'))
        return lines

    def _build_tb(self):
        """Trial balance: per-account debit/credit totals for the period."""
        lines = []
        total_debit = total_credit = 0.0
        for name, g in self._by_account(
                [], True, ['debit:sum', 'credit:sum', 'balance:sum']):
            debit = g['debit'] or 0.0
            credit = g['credit'] or 0.0
            if not debit and not credit:
                continue
            total_debit += debit
            total_credit += credit
            lines.append((name, (g['balance'] or 0.0), 'line', debit, credit))
        lines.append((_('Total'), total_debit - total_credit, 'total',
                      total_debit, total_credit))
        return lines

    def _build_cf(self):
        """Cash flow for the period (bank and cash accounts movement)."""
        cash_domain = [('account_id.account_type', '=', 'asset_cash')]
        # Opening balance: everything before the start date
        opening = 0.0
        if self.date_from:
            res = self.env['account.move.line'].read_group([
                ('parent_state', '=', 'posted'),
                ('company_id', '=', self.company_id.id),
                ('date', '<', self.date_from),
            ] + cash_domain, ['balance:sum'], [])
            opening = (res[0]['balance'] or 0.0) if res else 0.0

        lines = [(_('Opening Cash Balance'), opening, 'total'),
                 (_('Cash Receipts'), 0.0, 'header')]
        inflow_total = 0.0
        for name, g in self._by_account(
                cash_domain, True, ['debit:sum', 'credit:sum']):
            amount = g['debit'] or 0.0
            inflow_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Receipts'), inflow_total, 'total'))

        lines.append((_('Cash Payments'), 0.0, 'header'))
        outflow_total = 0.0
        for name, g in self._by_account(
                cash_domain, True, ['debit:sum', 'credit:sum']):
            amount = g['credit'] or 0.0
            outflow_total += amount
            lines.append((name, amount, 'line'))
        lines.append((_('Total Payments'), outflow_total, 'total'))

        lines.append((_('Net Cash Flow for the Period'),
                      inflow_total - outflow_total, 'total'))
        lines.append((_('Closing Cash Balance'),
                      opening + inflow_total - outflow_total, 'total'))
        return lines


class ScaleboxFinancialReportLine(models.TransientModel):
    _name = 'scalebox.financial.report.line'
    _description = 'Scalebox - Financial Report Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'scalebox.financial.report', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Item', readonly=True)
    balance = fields.Monetary(string='Amount', readonly=True)
    debit = fields.Monetary(string='Debit', readonly=True)
    credit = fields.Monetary(string='Credit', readonly=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    style = fields.Selection([
        ('header', 'Header'),
        ('line', 'Line'),
        ('total', 'Total'),
    ], default='line', readonly=True)
