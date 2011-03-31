# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты 
# 3. Тип счетов
# 3. Остатки по счетам
##############################################################################
"Reports Balances Accounting"
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.tools import safe_eval
import time
from decimal import Decimal, ROUND_HALF_EVEN
import datetime
import logging

#
# Остатки по счетам за периоды
#
class PrintAccountInit(ModelView):
    'Print Account'
    _name = 'ekd.balances.print.init'
    _description = __doc__
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
                    required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period')
    end_period = fields.Many2One('account.period', 'End Period')
    start_date = fields.Date('Start Period')
    end_date = fields.Date('End Period')

    company = fields.Many2One('company.company', 'Company', required=True)
    empty_account = fields.Boolean('Empty Account',
                                        help='With account without move')

    def default_fiscalyear(self):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        context = Transaction().context
        fiscalyear_id = fiscalyear_obj.find(
            context.get('company', False), exception=False)
        if fiscalyear_id:
            return fiscalyear_id
        return False

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

    def default_empty_account(self):
        return False

    def on_change_fiscalyear(self,  vals):
        return {
                'start_period': False,
                'end_period': False,
                }

PrintAccountInit()

class PrintAccount(Wizard):
    'Print Account'
    _name = 'ekd.balances.print'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.balances.print.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-print', True),
                        ],
                        },
                },
        'print': {
            'result': {
                'type': 'print',
                    'report': 'ekd.balances.turnovers',
                    'state': 'end',
                    },
                },
            }
PrintAccount()

class BalanceAccountReport(Report):
    _name = "ekd.balances.account.balances"

    def parse(self, report, objects, datas, localcontext={}):
        res = super(BalanceAccountReport, self).parse(report, objects, datas, localcontext)
        return res

BalanceAccountReport()

class TurnoverAccountReport(Report):
    _name = "ekd.balances.account.turnovers"

    def execute(self,  ids, datas):
        res = super(TurnoverAccountReport, self).execute(ids, datas)
        return res

    def parse(self, report, objects, datas, localcontext={}):

        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['current_date'] = context.get('current_date', False)
        localcontext['total_balance_dt'] = sum((x['balance_dt'] for x in objects))
        localcontext['total_balance_ct'] = sum((x['balance_ct'] for x in objects))
        localcontext['total_debit'] = sum((x['debit'] for x in objects))
        localcontext['total_credit'] = sum((x['credit'] for x in objects))
        localcontext['total_balance_dt_end'] = sum((x['balance_dt_end'] for x in objects))
        localcontext['total_balance_ct_end'] = sum((x['balance_ct_end'] for x in objects))

        res = super(TurnoverAccountReport, self).parse(report, objects, datas,
                localcontext)

        return res

TurnoverAccountReport()

 #
# Остатки по счетам за периоды (Дебиторская и кредиторская задолжность)
#
class BalancePartner(Report):
    "Turnover and Balances parties"
    _name = "ekd.balances.party.balances"

BalancePartner()

class TurnoverPartner(Report):
    "Turnover parties"
    _name = "ekd.balances.party.turnovers"


    def parse(self,  report, objects, datas, localcontext={}):
        tmp_objects = []
        tmp_account = []

        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['current_date'] = context.get('current_date', False)
        localcontext['total_balance_dt'] = sum((x['balance_dt'] for x in objects))
        localcontext['total_balance_ct'] = sum((x['balance_ct'] for x in objects))
        localcontext['total_debit'] = sum((x['debit'] for x in objects))
        localcontext['total_credit'] = sum((x['credit'] for x in objects))
        localcontext['total_balance_dt_end'] = sum((x['balance_dt_end'] for x in objects))
        localcontext['total_balance_ct_end'] = sum((x['balance_ct_end'] for x in objects))
        for obj in objects:
            if obj['account'] not in tmp_account:
                tmp_account.append(obj['account'])

        if len(tmp_account) == 1:
            res = super(TurnoverPartner, self).parse(report, [{
                'total_dt': sum((x['balance_dt'] for x in objects)),
                'total_ct': sum((x['balance_ct'] for x in objects)),
                'total_debit': sum((x['debit'] for x in objects)),
                'total_credit': sum((x['credit'] for x in objects)),
                'total_dt_end': sum((x['balance_dt_end'] for x in objects)),
                'total_ct_end': sum((x['balance_ct_end'] for x in objects)),
                'acc_code': '10',
                'acc_name':'sdfsdfsdf',
                'lines':objects,
                },], datas, localcontext)
        else:
            res = super(TurnoverPartner, self).parse(report, [{
                'total_dt': sum((x['balance_dt'] for x in objects)),
                'total_ct': sum((x['balance_ct'] for x in objects)),
                'total_debit': sum((x['debit'] for x in objects)),
                'total_credit': sum((x['credit'] for x in objects)),
                'total_dt_end': sum((x['balance_dt_end'] for x in objects)),
                'total_ct_end': sum((x['balance_ct_end'] for x in objects)),
                'acc_code': '10',
                'acc_name':'sdfsdfsdf',
                'lines':objects,
                },], datas, localcontext)

        return res

TurnoverPartner()

class CardPartner(Report):
    "Card parties"
    _name = "ekd.balances.party.card"

    def parse(self,  report, objects, datas, localcontext={}):
        tmp_objects = []
        tmp_account = []

        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['current_date'] = context.get('current_date', False)
        for obj in objects:
            if obj['account'] not in tmp_account:
                tmp_account.append(obj['account'])
        if len(tmp_account) == 1:
            res = super(CardPartner, self).parse(report, [{
                'account_code': '10',
                'account_name':'name account',
                'sub_account':'1',
                'lines':objects,
                },], datas, localcontext)
        else:
            res = super(CardPartner, self).parse(report, [{
                'account_code': '10',
                'account_name':'name account',
                'sub_account':'1',
                'lines':objects,
                },], datas, localcontext)

        return res

CardPartner()

#
# Остатки по счетам за периоды (Товарно-материальные ценности)
#
class BalanceProduct(Report):
    "Turnover and Balances product"
    _name = "ekd.balances.product.balances"

BalanceProduct()

class TurnoverProduct(Report):
    "Turnover product"
    _name = "ekd.balances.product.turnovers"

    def parse(self,  report, objects, datas, localcontext={}):
        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['acc_code'] = '10.1'
        localcontext['acc_name'] = u'Материалы'
        localcontext['current_date'] = context.get('current_date', False)
        localcontext['total_qbalance'] = sum((x['qbalance'] for x in objects))
        localcontext['total_balance'] = sum((x['balance'] for x in objects))
        localcontext['total_qdebit'] = sum((x['qdebit'] for x in objects))
        localcontext['total_debit'] = sum((x['debit'] for x in objects))
        localcontext['total_qcredit'] = sum((x['qcredit'] for x in objects))
        localcontext['total_credit'] = sum((x['credit'] for x in objects))
        localcontext['total_qbalance_end'] = sum((x['qbalance_end'] for x in objects))
        localcontext['total_balance_end'] = sum((x['balance_end'] for x in objects))
        
        res = super(TurnoverProduct, self).parse(report, objects, datas,
                localcontext)
        return res

TurnoverProduct()

#
# Остатки по счетам за периоды (Дополнительная аналитика)
#
class BalanceAnalytic(Report):
    "Balances analytic accounts"
    _name = "ekd.balances.analytic.balances"
    _description =__doc__

BalanceAnalytic()

class TurnoverAnalytic(Report):
    "Turnover analytic accounts"
    _name = "ekd.balances.analytic.turnovers"
    _description =__doc__

    def parse(self,  report, objects, datas, localcontext={}):

        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['current_date'] = context.get('current_date', False)
        localcontext['total_balance_dt'] = sum((x['balance_dt'] for x in objects))
        localcontext['total_balance_ct'] = sum((x['balance_ct'] for x in objects))
        localcontext['total_debit'] = sum((x['debit'] for x in objects))
        localcontext['total_credit'] = sum((x['credit'] for x in objects))
        localcontext['total_balance_dt_end'] = sum((x['balance_dt_end'] for x in objects))
        localcontext['total_balance_ct_end'] = sum((x['balance_ct_end'] for x in objects))
        
        res = super(TurnoverAnalytic, self).parse(report, objects, datas,
                localcontext)
        return res

TurnoverAnalytic()

#
# Ежедневные остатки по финансовым счетам
#
class BalanceFinance(Report):
    "Balances finance accounts"
    _name = "ekd.balances.finance.balances"
    _description =__doc__

BalanceFinance()

class TurnoverFinance(Report):
    "Turnover finance accounts"
    _name = "ekd.balances.finance.turnovers"
    _description =__doc__

TurnoverFinance()
