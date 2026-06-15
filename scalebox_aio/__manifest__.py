# -*- coding: utf-8 -*-
# Part of Scalebox All-in-One ERP.
# Copyright (C) 2026 Scalebox For Digital Services. All Rights Reserved.
{
    'name': 'Scalebox All-in-One ERP',
    'version': '19.0.7.0.4',
    'price': 99.00,
    'currency': 'USD',
    'category': 'Accounting/Accounting',
    'summary': 'Simple all-in-one ERP: sales, purchases, inventory, accounting, POS and reports in one app',
    'description': """
Scalebox All-in-One ERP
=======================

A simplified layer on top of Odoo 19 Community for small businesses (up to 10 users).

- Easy Sale screen: sale order + stock delivery + invoice + payment in one step.
- Easy Purchase screen: purchase order + stock receipt + vendor bill + payment in one step.
- Sales and purchase returns with automatic credit/debit notes and stock returns.
- Expenses with configurable types, automatic journal entries and printable vouchers.
- Embedded official Point of Sale, loyalty programs and landed costs.
- Live KPI dashboard, financial reports (BS / P&L / Cash Flow) and printable reports.
- Two-level access rights (User / Manager) and negative-stock selling control.
- Fully bilingual (English / Arabic).

Built entirely on standard Odoo tables (res.partner / product.product / res.users /
sale.order / purchase.order / stock.picking / account.move) with no data duplication,
keeping all accounting and inventory postings valid and compatible with standard reports.
""",
    'author': 'Scalebox For Digital Services',
    'maintainer': 'Scalebox For Digital Services',
    'website': 'https://scalebox.scbox.pro',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
