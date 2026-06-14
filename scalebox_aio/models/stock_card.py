# -*- coding: utf-8 -*-
# Part of Scalebox All-in-One ERP.
# Copyright (C) 2026 Scalebox For Digital Services. All Rights Reserved.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ScaleboxStockCard(models.TransientModel):
    """Product stock card: in / out / running balance, with PDF printing."""

    _name = 'scalebox.stock.card'
    _description = 'Scalebox - Product Stock Card'
    _inherit = ['scalebox.xlsx.export.mixin']

    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain="[('type', '=', 'consu')]")
    warehouse_ids = fields.Many2many(
        'stock.warehouse', string='Warehouses', required=True,
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)]))
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    date_from = fields.Date(
        string='From Date', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='To Date', required=True,
        default=fields.Date.context_today)
    opening_qty = fields.Float(
        string='Opening Balance', readonly=True,
        digits='Product Unit of Measure')
    closing_qty = fields.Float(
        string='Closing Balance', readonly=True,
        digits='Product Unit of Measure')
    total_in = fields.Float(
        string='Total In', readonly=True,
        digits='Product Unit of Measure')
    total_out = fields.Float(
        string='Total Out', readonly=True,
        digits='Product Unit of Measure')
    line_ids = fields.One2many(
        'scalebox.stock.card.line', 'wizard_id', string='Moves')

    def _move_domain(self):
        self.ensure_one()
        return [
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('product_id', '=', self.product_id.id),
        ]

    def _move_direction(self, move):
        """+qty entering the selected warehouses, -qty leaving them,
        0 for transfers within the selected set."""
        wh_ids = set(self.warehouse_ids.ids)
        src_in = (move.location_id.usage == 'internal'
                  and move.location_id.warehouse_id.id in wh_ids)
        dest_in = (move.location_dest_id.usage == 'internal'
                   and move.location_dest_id.warehouse_id.id in wh_ids)
        if dest_in and not src_in:
            return move.quantity
        if src_in and not dest_in:
            return -move.quantity
        return 0.0

    def _get_document_ref(self, move):
        """Invoice / source document number instead of just the picking ref."""
        pick = move.picking_id
        if not pick:
            return move.reference or '/'
        so = getattr(pick, 'sale_id', False)
        if so:
            es = self.env['scalebox.easy.sale'].search(
                [('sale_order_id', '=', so.id)], limit=1)
            if es and es.invoice_id:
                return es.invoice_id.name
            return (so.invoice_ids[:1].name or so.name) if so.invoice_ids else so.name
        po = getattr(pick, 'purchase_id', False)
        if po:
            ep = self.env['scalebox.easy.purchase'].search(
                [('purchase_order_id', '=', po.id)], limit=1)
            if ep and ep.invoice_id:
                return ep.invoice_id.name
            return (po.invoice_ids[:1].name or po.name) if po.invoice_ids else po.name
        sr = self.env['scalebox.easy.sale.return'].search(
            [('picking_ids', 'in', pick.id)], limit=1)
        if sr and sr.refund_id:
            return sr.refund_id.name
        pr = self.env['scalebox.easy.purchase.return'].search(
            [('picking_ids', 'in', pick.id)], limit=1)
        if pr and pr.refund_id:
            return pr.refund_id.name
        return pick.origin or pick.name

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('Start date must be before end date.'))
        self.line_ids.unlink()
        Move = self.env['stock.move']

        # Opening balance: all moves before the start date
        opening = 0.0
        prior_moves = Move.search(
            self._move_domain() + [('date', '<', fields.Datetime.to_datetime(self.date_from))])
        for move in prior_moves:
            opening += self._move_direction(move)

        # Period moves in chronological order
        period_moves = Move.search(
            self._move_domain() + [
                ('date', '>=', fields.Datetime.to_datetime(self.date_from)),
                ('date', '<', fields.Datetime.add(
                    fields.Datetime.to_datetime(self.date_to), days=1)),
            ], order='date, id')

        balance = opening
        total_in = total_out = 0.0
        vals_list = []
        seq = 0
        for move in period_moves:
            qty = self._move_direction(move)
            if not qty:
                continue
            balance += qty
            if qty > 0:
                total_in += qty
            else:
                total_out += -qty
            seq += 10
            vals_list.append({
                'wizard_id': self.id,
                'sequence': seq,
                'date': move.date,
                'reference': move.reference or move.picking_id.name or '/',
                'document_ref': self._get_document_ref(move),
                'partner_id': move.picking_id.partner_id.id or move.partner_id.id,
                'qty_in': qty if qty > 0 else 0.0,
                'qty_out': -qty if qty < 0 else 0.0,
                'balance': balance,
            })
        self.env['scalebox.stock.card.line'].create(vals_list)
        self.opening_qty = opening
        self.closing_qty = balance
        self.total_in = total_in
        self.total_out = total_out
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product Stock Card'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print(self):
        self.ensure_one()
        if not self.line_ids and not self.opening_qty:
            self.action_generate()
        return self.env.ref(
            'scalebox_aio.action_report_stock_card').report_action(self)

    # --- Excel export ---
    def _xlsx_title(self):
        return _('Product Stock Card')

    def _xlsx_filename(self):
        return 'stock_card_%s.xlsx' % (self.product_id.default_code or self.product_id.id)

    def _xlsx_sheet_name(self):
        return _('Stock Card')

    def _xlsx_meta(self):
        return [
            (_('Product:'), self.product_id.display_name),
            (_('Period:'), '%s - %s' % (self.date_from, self.date_to)),
            (_('Warehouses:'), ', '.join(self.warehouse_ids.mapped('name'))),
            (_('Opening Balance'), self.opening_qty),
            (_('Closing Balance'), self.closing_qty),
        ]

    def _xlsx_columns(self):
        return [
            (_('Date'), 'date', 'text'),
            (_('Document No.'), 'document_ref', 'text'),
            (_('Reference'), 'reference', 'text'),
            (_('Customer / Vendor'), 'partner', 'text'),
            (_('In'), 'qty_in', 'number'),
            (_('Out'), 'qty_out', 'number'),
            (_('Balance'), 'balance', 'number'),
        ]

    def _xlsx_rows(self):
        rows = [{
            'date': '', 'document_ref': '', 'reference': '',
            'partner': _('Opening Balance'),
            'qty_in': None, 'qty_out': None, 'balance': self.opening_qty,
        }]
        for line in self.line_ids:
            rows.append({
                'date': str(line.date or ''),
                'document_ref': line.document_ref or '',
                'reference': line.reference or '',
                'partner': line.partner_id.name or '',
                'qty_in': line.qty_in or None,
                'qty_out': line.qty_out or None,
                'balance': line.balance,
            })
        return rows


class ScaleboxStockCardLine(models.TransientModel):
    _name = 'scalebox.stock.card.line'
    _description = 'Scalebox - Stock Card Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'scalebox.stock.card', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    date = fields.Datetime(string='Date', readonly=True)
    reference = fields.Char(string='Reference', readonly=True)
    document_ref = fields.Char(string='Document No.', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer / Vendor', readonly=True)
    qty_in = fields.Float(
        string='In', readonly=True, digits='Product Unit of Measure')
    qty_out = fields.Float(
        string='Out', readonly=True, digits='Product Unit of Measure')
    balance = fields.Float(
        string='Balance', readonly=True, digits='Product Unit of Measure')
