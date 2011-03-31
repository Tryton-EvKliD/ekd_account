# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms
"Account"
#from __future__ import with_statement
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Equal, Eval, Or, In, Not, PYSONEncoder, Date

class Account(ModelSQL, ModelView):
    'Account'
    _name = 'ekd.account'

    root_analytic = fields.Many2One('ekd.account.analytic', 'account', 'Root Analytic',
                states={
                'invisible': Not(Equal(Eval('kind_analytic'), 'analytic')),
                },
                domain=[('type','in', ['root', 'view'])]
                )

Account()
