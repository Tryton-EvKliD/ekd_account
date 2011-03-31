# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Address'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import If, Greater, Eval, Not, Bool, Eval

STATES = {
    'readonly': Not(Bool("active")),
}

class BankAccount(ModelSQL, ModelView):
    "Bank"
    _name = 'ekd.party.bank_account'
    _description = __doc__

   account_bank = fields.Property(fields.Many2One('ekd.account',
        'Account Bank', domain=[
            ('kind_analytic', '=', 'money_bank'),
            ('company', '=', Eval('company')),
        ],
        states={
            'required': Bool(Eval('company')),
            'invisible': Not(Bool(Eval('company'))),
        }))

BankAccount()
