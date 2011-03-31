# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Company"
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval

class Company(ModelSQL, ModelView):
    _name = 'company.company'

    cal_accounting = fields.Many2One('calendar.calendar', 'Accounting Calendar')

Company()

class User(ModelSQL, ModelView):
    _name = 'res.user'

    current_period = fields.Property(fields.Many2One('ekd.period', 'Current Period',
            domain=[('company', '=', Eval('company'))]))
    fiscalyear = fields.Property(fields.Many2One('ekd.fiscalyear', 'Current Fiscal Year',
            domain=[('company', '=', Eval('company'))]))

    company = fields.Many2One('company.company', 'Current Company',
            domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
            depends=['main_company'], on_change=['company', 'fiscalyear', 'current_period'])

    def __init__(self):
        super(User, self).__init__()
        self._context_fields.insert(0, 'current_period')
        self._context_fields.insert(0, 'fiscalyear')

    def on_change_company(self, vals):
        if not vals.get('company'):
            return {}
        if not vals.get('fiscalyear'):
            return {}
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        period_obj = self.pool.get('ekd.period')
        fiscalyear_old = fiscalyear_obj.browse(vals.get('fiscalyear'))
        period_old = fiscalyear_obj.browse(vals.get('current_period'))
        return {
            'fiscalyear': None,
            'current_period':None,
            }

User()

