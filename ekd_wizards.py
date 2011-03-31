# -*- coding: utf-8 -*-

"Document Cash"
from trytond.model import ModelView, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from decimal import Decimal, ROUND_HALF_EVEN
import datetime
import logging
import gettext
_ = gettext.gettext

class DocumentCashWizardInit(ModelView):
    'Document Cash Init'
    _name = 'ekd.document.cash.wizard.init'
    _description = __doc__

DocumentCashWizardInit()

class DocumentCashWizard(Wizard):
    'Configure companies'
    _name = 'ekd.document.cash.wizard'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.document.cash.wizard.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('document', 'Ok', 'tryton-ok', True),
                        ],
                    },
                },
        'document': {
            'result': {
                'type': 'form',
                'object': 'ekd.document.head.cash',
                'state': [
                        ('end', 'Cancel', 'tryton-cancel'),
                        ('add', 'Add New', 'tryton-ok', True),
                        ('print', 'Print', 'tryton-print', True),
                        ],
                },
                    },
        'add': {
            'result': {
                'type': 'action',
                'action': '_add',
                'state': 'document'
                        },
                },
        'print': {
            'actions': ['check',],
                'result': {
                    'type': 'print',
                    'report': 'account.account.aged_balance',
                    'state': 'document',
                        },
                },
            }

    def _add(self, data):
        document_obj = self.pool.get('ekd.document.head.cash')
#        document_obj.search([
#                        ('template_cash','=', data['form'][]
#                        ('date_account','=', data['form'][]
#                        ])
        if not  data['form']['state'] == 'posted':
            document_id = document_obj.create(data['form'])
        return {}

DocumentCashWizard()

class DocumentCashWizardPrint(Wizard):
    'Document Cash Wizarid'
    _name = 'ekd.document.cash.wizard.print'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_choice',
            },
        },
        'print_income': {
            'result': {
                'type': 'print',
                'report': 'ekd.document.cash.print.income',
                'state': 'end',
            },
        },
        'print_expense': {
            'result': {
                'type': 'print',
                'report': 'ekd.document.cash.print.expense',
                'state': 'end',
            },
        },

    }

    def _choice(self, data):
        document_obj = self.pool.get('ekd.document.head.cash')
        cash_income = []
        cash_expense = []
        for document in document_obj.browse(data.get('ids')):
            if document.template.code_call == "income":
                cash_income.append(document.id)
            else:
                cash_expense.append(document.id)
        data['cash_income'] = cash_income
        data['cash_expense'] = cash_expense
        if len(cash_income) > 0 and len(cash_expense) > 0:
            raise Exception('Only one type documents')
        elif len(cash_income) > 0:
                return 'print_income'
        else:
                return 'print_expense'

DocumentCashWizardPrint()

