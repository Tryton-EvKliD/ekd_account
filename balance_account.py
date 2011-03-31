# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты для сохранения данных
# 1. Учетные счета с периодами
# 1. Учетные счета с месячными периодами - 1 строка на 1 финансовый год
# 1. Учетные счета без периодов
##############################################################################
"Balances Accounting"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.tools import safe_eval
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import Equal, Eval, Not, In, PYSONEncoder
from trytond.backend import TableHandler
import time
import datetime
import logging
from account import _PARTY, _PRODUCT, _MONEY

_BALANCE_STATES = {
        'readonly': In(Eval('state'), ['draft', 'done']),
                }
_BALANCE_DEPENDS = ['state']

_ID_TABLES_BALANCES={
    'ekd_balances_party':1,
    'ekd_balances_analytic':2,
    'ekd_balances_assets':3,
    'ekd_balances_intangible_assets':4,
    'ekd_balances_material':5,
    'ekd_balances_goods':6,
    'ekd_balances_product':7,
    'ekd_balances_finance':8,
    '':9,
    }

_ID_TABLES_BALANCES_PERIOD={
    'ekd_balances_party_period':1,
    'ekd_balances_party_year':1,
    'ekd_balances_analytic_period':2,
    'ekd_balances_analytic_year':2,
    'ekd_balances_assets_period':3,
    'ekd_balances_material_balance':5,
    'ekd_balances_goods_balance':6,
    }

#
# Остатки по счетам за периоды
#
class BalanceAccountPeriod(ModelSQL, ModelView):
    "Turnover and Balances Account"
    _name = "ekd.balances.account"
    _description =__doc__

    def get_balance_end(self, ids, names):
        if not ids: 
            return {}
        res={}
        context = Transaction().context
        month = self.pool.get('ekd.period').browse(context.get('current_period')).start_date.strftime('%m')
        if 'balance_dt_end' in names or 'balance_ct_end' in names:
            party_obj = self.pool.get('ekd.balances.party')
            analytic_obj = self.pool.get('ekd.balances.analytic')
            party_ids=[]
            analytic_ids=[]
            for balance in self.browse(ids):
                if balance.account_kind == 'party' :
                    party_ids.append(balance.id)
                elif balance.account_kind == 'analytic' :
                    analytic_ids.append(balance.id)
        field_debit = "debit_%s"%(month or 
                                      datetime.datetime.now().strftime('%m'))
        field_credit = "credit_%s"%(month or 
                                       datetime.datetime.now().strftime('%m'))
        '''
        SELECT id, balance_dt+'+'.join(field_debits), 
                balance_ct+'+'.join(field_credits),
                field_debit, field_credit
        FROM ekd_balances_account
        WHERE fiscalyear=%s
        '''

        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if name == 'balance_end':
                    if balance.type_balance == 'active' or balance.type_balance == 'both' :
                        res[name][balance.id] = balance.balance_dt-balance.balance_ct+balance.debit-balance.credit
                    elif balance.type_balance == 'passive':
                        res[name][balance.id] = balance.balance_ct-balance.balance_dt-balance.debit+balance.credit
                elif name == 'balance':
                    if balance.type_balance == 'active' or balance.type_balance == 'both' :
                        res[name][balance.id] = abs(balance.balance_dt-balance.balance_ct)
                    elif balance.type_balance == 'passive':
                        res[name][balance.id] = -abs(balance.balance_dt+balance.balance_ct)
                elif name == 'debit':
                    res[name][balance.id] = balance[field_debit]
                elif name == 'credit':
                    res[name][balance.id] = balance[field_credit]

                elif name == 'balance_dt_end':
                    if balance.type_balance == 'passive':
                        continue
                    elif balance.account_kind in _PARTY :
                        party_ids = party_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for party_id in party_obj.browse(party_ids):
                            amount_balance += party_id.balance_dt_end
                        res[name][balance.id] = amount_balance
                    elif balance.account_kind == 'analytic' :
                        analytic_ids = analytic_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for analytic_id in analytic_obj.browse(analytic_ids):
                            if analytic_id.balance_end > 0:
                                amount_balance += analytic_id.balance_end
                        res[name][balance.id] = amount_balance

                    elif balance.type_balance == 'active':
                        res[name][balance.id] = balance.balance_dt+balance.debit-balance.credit

                    elif balance.type_balance == 'both':
                        if balance.balance_dt-balance.balance_ct+balance.debit-balance.credit > 0:
                            res[name][balance.id] = balance.balance_dt-balance.balance_ct+balance.debit-balance.credit
                    else:
                        raise Exception('Error Type unknown', balance.account.code, balance.type_balance)

                elif name == 'balance_ct_end':
                    if balance.type_balance == 'active':
                        continue
                    elif balance.account_kind in _PARTY :
                        party_ids = party_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for party_id in party_obj.browse(party_ids):
                            amount_balance += party_id.balance_ct_end
                        res[name][balance.id] = amount_balance
                    elif balance.account_kind == 'analytic' :
                        analytic_ids = analytic_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for analytic_id in analytic_obj.browse(analytic_ids):
                            if analytic_id.balance_end < 0:
                                amount_balance += abs(analytic_id.balance_end)
                        res[name][balance.id] = amount_balance

                    elif balance.type_balance == 'passive' :
                        res[name][balance.id] = balance.balance_ct-balance.debit+balance.credit

                    elif balance.type_balance == 'both':
                        if balance.balance_ct-balance.balance_dt-balance.debit+balance.credit > 0:
                            res[name][balance.id] = balance.balance_ct-balance.balance_dt-balance.debit+balance.credit
                    else:
                        raise Exception('Error Type unknown', balance.account.code, balance.type_balance)

        return res

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    account = fields.Many2One('ekd.account', 'Account', required=True,  select=2,
                        order_field="account.code", 
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    account_type = fields.Function(fields.Char('Type Account'), 'get_account_type')
    account_kind = fields.Function(fields.Char('Kind Account'), 'get_account_type')
    type_balance = fields.Function(fields.Char('Type Balance'), 'get_account_type')
    period = fields.Many2One('ekd.period', 'Period', required=True,
                        select=2, order_field="period, account.code",
                        domain=[
                            ('company','=',Eval('company'))
                        ])
    period_start = fields.Function(fields.Date('Start Period'), 'get_start_date')
    balance_dt = fields.Numeric('Debit Start', digits=(16, Eval('currency_digits', 2)),)
    balance_ct = fields.Numeric('Credit Start', digits=(16, Eval('currency_digits', 2)),)
    debit = fields.Numeric('Debit Turnover', digits=(16, Eval('currency_digits', 2)),)
    credit = fields.Numeric('Credit Turnover', digits=(16, Eval('currency_digits', 2)),)
    balance_end_dt = fields.Numeric('Debit End', digits=(16, Eval('currency_digits', 2)),)
    balance_end_ct = fields.Numeric('Credit End', digits=(16, Eval('currency_digits', 2)),)
    balance = fields.Function(fields.Numeric('Start Balance', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('End Balance', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_dt_end = fields.Function(fields.Numeric('Debit End', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_ct_end = fields.Function(fields.Numeric('Credit End', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                None, 'Ref entry debit lines'), 'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                None, 'Ref entry credit lines'), 'get_entries_field')
    parent = fields.Many2One('ekd.balances.account','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.account','ID Transfer balance')
    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAccountPeriod, self).__init__()
        self._order.insert(0, ('period', 'ASC'))
        self._order.insert(1, ('account', 'ASC'))

        #self._sql_constraints += [
        #        ('balance_account_uniq', 'UNIQUE(company,period,account)',\
        #         'company, period, account - must be unique per balance!'),
        #         ]

#        self._constraints += [
#        ('balance_account_uniq', 'unique (company,account,period)',\
#              ' company, account, period, currency must be unique per company!')]

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_active(self):
        return True

    def default_company(self):
        return Transaction().context.get('company') or False

    def get_start_date(self, ids, name):
        res = {}
        for line in self.browse(ids):
           res[line.id] = line.period.start_date
        return res

    def get_company(self, ids, name):
        res = {}
        for line in self.browse(ids):
           if line.account:
                res = {}.fromkeys(ids, line.account.comany.id)
        return res

    def get_account_type(self, ids, name):
        if name not in ('account_type', 'account_kind', 'type_balance'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(ids):
           if line.account:
            if name == 'account_type':
                res[line.id] = line.account.type.name
            elif name == 'account_kind':
                res[line.id] = line.account.kind
            else:
                res[line.id] = line.account.type_balance
        return res

    def get_currency_digits(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    res[name][line.id] = line.account.currency_digits
                elif name == 'second_currency_digits':
                    if line.account.second_currency:
                        res[name][line.id] = line.account.second_currency.digits
        return res

    def get_entries_field(self, ids, name):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        move_line = self.pool.get('ekd.account.move.line')
        res = {}
        for balance in self.browse(ids):
            if name == 'dt_line':
                res[balance.id] = move_line.search([('dt_balance','=', balance.id)])
            elif name == 'ct_line':
                res[balance.id] = move_line.search([('ct_balance','=', balance.id)])
            elif name == 'lines':
                res[balance.id] = move_line.search(
                        ['OR',
                            ('dt_balance','=', balance.id), 
                            ('ct_balance','=', balance.id)
                        ])
        return res

    def button_done(self, ids):
        return self.close(ids)

    def button_draft(self, ids):
        return self.cancel(ids)

    def button_restore(self, ids):
        return self.restore(ids)

    def close(self, ids):
        return self.write(ids, {'state': 'done', })

    def draft(self, ids):
        return self.write(ids, {'state': 'draft', })

    def restore(self, ids):
        return self.write(ids, {'state': 'draft', })

    def test_balance(self, values=None):
        '''
        Проверка баланса счетов 
        values = {'company': ID учетной организации,
                  'period': ID периода,
        '''
        cr = Transaction().cursor
        cr.execute('SELECT a.company, a.period,'\
                    'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc,'\
                    'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'\
                    'FROM ekd_balances_account a'\
                    'LEFT JOIN ekd_account e ON a.account=e.id'\
                    'WHERE a.company=%s AND a.period in %s in '\
                    'GROUP BY a.company, a.period'%(values.get('company'), values.get('period')))
        self.raise_user_warning(
                '%s@account_ru_move_line' % line.id,
                'delete_posted_line')
 
    def test_balance_analytic(self, values=None):
        '''
        Проверка соответствия аналитических остатков
        values = {'company': ID учетной организации,
                  'period': ID периода,
                  'account': [] список ID счетов,
        '''
        cr = Transaction().cursor
        if values.get('account',False):
            cr.execute('SELECT a.company, a.period, a.account, e.code, e.kind, COUNT(a.account) as count_line,'+\
                        'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc,'+\
                        'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'+\
                        'SUM(b.balance) as bal_anl, SUM(b.debit) as debit_anl, SUM(b.credit) as credit_anl,'+\
                        'SUM(c.balance_dt) as bal_dt_party, SUM(c.balance_ct) as bal_ct_party,'+\
                        'SUM(c.debit) as debit_party, SUM(c.credit) as credit_party,'+\
                        'SUM(d.balance) as bal_product, SUM(d.debit) as debit_product,'+\
                        'SUM(d.credit) as credit_product'+\
                    'FROM ekd_balances_account a'+\
                    'LEFT JOIN ekd_balances_analytic b ON a.company=b.company and a.period=b.period and a.account=b.account'+\
                    'LEFT JOIN ekd_balances_party c ON a.company=c.company and a.period=c.period and a.account=c.account'+\
                    'LEFT JOIN ekd_balances_product d ON a.company=d.company and a.period=d.period and a.account=d.account'+\
                    'LEFT JOIN ekd_account e ON a.account=e.id'+\
                    'WHERE a.company=%s AND a.period in %s AND a.account in ('+ ''.join() + ') '+\
                    'GROUP BY a.company, a.period, a.account, e.code ORDER BY e.code'%(values.get('company'), values.get('period')))
        else:
            cr.execute('SELECT a.company, a.period, a.account, e.code, e.kind, COUNT(a.account) as count_line,'+\
                        'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc, '+\
                        'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'+\
                        'SUM(b.balance) as bal_anl, SUM(b.debit) as debit_anl, SUM(b.credit) as credit_anl,'+\
                        'SUM(c.balance_dt) as bal_dt_party, SUM(c.balance_ct) as bal_ct_party,'+\
                        'SUM(c.debit) as debit_party, SUM(c.credit) as credit_party,'+\
                        'SUM(d.balance) as bal_product, SUM(d.debit) as debit_product,'+\
                        'SUM(d.credit) as credit_product'+\
                    'FROM ekd_balances_account a'+\
                    'LEFT JOIN ekd_balances_analytic b ON a.company=b.company and a.period=b.period and a.account=b.account'+\
                    'LEFT JOIN ekd_balances_party c ON a.company=c.company and a.period=c.period and a.account=c.account'+\
                    'LEFT JOIN ekd_balances_product d ON a.company=d.company and a.period=d.period and a.account=d.account'+\
                    'LEFT JOIN ekd_account e ON a.account=e.id'+\
                    'WHERE a.company=%s AND a.period in %s'+\
                    'GROUP BY a.company, a.period, a.account, e.code ORDER BY e.code'%(values.get('company'), values.get('period')))

        for line_id in cr.fetchall():
            if line_id['kind'] == 'analytic':
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_anl']:
                        pass
                    if line_id['debit'] != line_id['debit_anl']:
                        pass
                    if line_id['credit'] != line_id['credit_anl']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_anl']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_anl']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_anl']:
                        pass
            elif line_id['kind'] in _PARTY:
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_dt_party']:
                        pass
                    if line_id['balance_ct'] != line_id['bal_ct_party']:
                        pass
                    if line_id['debit'] != line_id['debit_anl']:
                        pass
                    if line_id['credit'] != line_id['credit_anl']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_dt_party']:
                        pass
                    if line_id['balance_ct']/line_id['count_line'] != line_id['bal_ct_party']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_anl']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_anl']:
                        pass
            elif line_id['kind'] in _PRODUCT:
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_product']:
                        pass
                    if line_id['debit'] != line_id['debit_product']:
                        pass
                    if line_id['credit'] != line_id['credit_product']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_product']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_product']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_product']:
                        pass
            elif line_id['kind'] == 'money':
                pass
    # Процедура переноса остатков (если есть более поздние)
    def transfer_balance(self, transfer_id, vals):
        balance = self.browse(transfer_id)
        self.write(transfer_id, {
                        'balance_dt': vals.get('balance_dt'),
                        'balance_ct': vals.get('balance_ct'),
                        })
        if balance.transfer and vals.get('transfer', True):
            self.transfer_balance(balance.transfer.id, {
                        'balance_dt':balance.balance_dt_end,
                        'balance_ct':balance.balance_ct_end,
                        'transfer': vals.get('transfer', True),
                        })

    def transfer_balances(self, vals=None):
        '''
            Transfer Balances of account - Перенос остатков.
            period     - словарь идентификаторов периодов (периоды уже отсортированны!!!)
            context    - словарь контекст
        '''
        if vals is None and not vals.get('company'):
            return False
        if vals.get('transfer_analytic',True):
            bal_analytic_obj = self.pool.get('ekd.balances.analytic')
            bal_party_obj = self.pool.get('ekd.balances.party')
            bal_product_obj = self.pool.get('ekd.balances.product')

        balance_ids= {}
        for period in vals.get('periods'):
            if not balance_ids:
                balance_ids = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period)
                            ])
                continue

            for balance_id in balance_ids:
                balance_line = self.browse(balance_id)
                if balance_line.balance_dt_end or balance_line.balance_ct_end:
                    # Перенос остатков по аналитическим счетам
                    if vals.get('transfer_analytic', True):
                        if balance_line.account.kind_analytic == 'analytic':
                            bal_analytic_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })
                        elif balance_line.account.kind_analytic in _PARTY:
                            bal_party_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })
                        elif balance_line.account.kind_analytic in _PRODUCT:
                            bal_product_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })

                    if balance_line.transfer:
                        self.transfer_balance(balance_line.transfer.id, {
                                    'balance_dt': balance_line.balance_dt_end,
                                    'balance_ct': balance_line.balance_ct_end,
                                    })
                    else:
                        balance_new_id = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period),
                            ('account','=',balance_line.account.id),
                            ])
                        if balance_new_id:
                            if isinstance(balance_new_id,list):
                                    balance_new_id = balance_new_id[0]
                            self.write(balance_line.id, {
                                    'transfer': balance_new_id,
                                    })
                            self.write(balance_new_id, {
                                    'balance_dt': balance_line.balance_dt_end,
                                    'balance_ct': balance_line.balance_ct_end,
                                    })

                        else:
                            self.write(balance_line.id, {
                                    'transfer': self.create({
                                            'company': vals.get('company'),
                                            'period': period,
                                            'account':  balance_line.account.id ,
                                            'currency': balance_line.currency.id,
                                            'balance_dt': balance_line.balance_dt_end,
                                            'balance_ct': balance_line.balance_ct_end,
                                            })
                                    })

            balance_ids = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period)
                            ])

        return True

BalanceAccountPeriod()

class BalanceAccountSingle(ModelSQL, ModelView):
    "Turnover and Balances Single Accounnt"
    _name = "ekd.balances.account.single"
    _description =__doc__

    account = fields.Many2One('ekd.account', 'Account', required=True,  select=2,
                        order_field="account.code", 
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    account_type = fields.Function(fields.Char('Type Account'), 'get_account_type')
    account_kind = fields.Function(fields.Char('Kind Account'), 'get_account_type')
    balance = fields.Function(fields.Numeric('End Balance', digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    credit = fields.Numeric('Credit Turnover', digits=(16, Eval('currency_digits', 2)),)
    debit = fields.Numeric('Debit Turnover', digits=(16, Eval('currency_digits', 2)),)
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'), 'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAccountSingle, self).__init__()
        self._order.insert(0, ('account', 'ASC'))

        #self._sql_constraints += [
        #        ('balance_account_uniq', 'UNIQUE(company,period,account)',\
        #         'company, period, account - must be unique per balance!'),
        #         ]

#        self._constraints += [
#        ('balance_account_uniq', 'unique (company,account,period)',\
#              ' company, account, period, currency must be unique per company!')]

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_active(self):
        return True

    def get_account_type(self, ids, name):
        if name not in ('account_type', 'account_kind', 'type_balance'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(ids):
           if line.account:
            if name == 'account_type':
                res[line.id] = line.account.type.name
            elif name == 'account_kind':
                res[line.id] = line.account.kind
            else:
                res[line.id] = line.account.type_balance
        return res

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[name][line.id] = line.account.currency_digits
        return res

    def get_entries_field(self, ids, name):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        move_line = self.pool.get('ekd.account.move.line')
        res = {}
        for balance in self.browse(ids):
                if name == 'dt_line':
                    res[balance.id] = move_line.search([('dt_balance','=', balance.id)])
                elif name == 'ct_line':
                    res[balance.id] = move_line.search([('ct_balance','=', balance.id)])
                elif name == 'lines':
                    res[balance.id] = move_line.search(['OR',('dt_balance','=', balance.id), ('ct_balance','=', balance.id)])
        return res

    def button_done(self, ids):
        return self.close(ids)

    def button_draft(self, ids):
        return self.cancel(ids)

    def button_restore(self, ids):
        return self.restore(ids)

    def close(self, ids):
        return self.write(ids, {'state': 'done', })

    def draft(self, ids):
        return self.write(ids, {'state': 'draft', })

    def restore(self, ids):
        return self.write(ids, {'state': 'draft', })

BalanceAccountSingle()

class BalanceAccountYear(ModelSQL, ModelView):
    "Turnover and Balances"
    _name = "ekd.balances.account.year"
    _description =__doc__

    def get_balance_end(self, ids, names):
        if not ids: 
            return {}
        res={}
        context = Transaction().context
        month = self.pool.get('ekd.period').browse(context.get('current_period')).start_date.strftime('%m')
        if 'balance_dt_end' in names or 'balance_ct_end' in names:
            party_obj = self.pool.get('ekd.balances.party')
            analytic_obj = self.pool.get('ekd.balances.analytic')
            party_ids=[]
            analytic_ids=[]
            for balance in self.browse(ids):
                if balance.account_kind == 'party' :
                    party_ids.append(balance.id)
                elif balance.account_kind == 'analytic' :
                    analytic_ids.append(balance.id)
        field_debit = "debit_%s"%(month or 
                                      datetime.datetime.now().strftime('%m'))
        field_credit = "credit_%s"%(month or 
                                       datetime.datetime.now().strftime('%m'))
        '''
        SELECT id, balance_dt+'+'.join(field_debits), 
                balance_ct+'+'.join(field_credits),
                field_debit, field_credit
        FROM ekd_balances_account
        WHERE fiscalyear=%s
        '''

        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if name == 'balance_end':
                    if balance.type_balance == 'active' or balance.type_balance == 'both' :
                        res[name][balance.id] = balance.balance_dt-balance.balance_ct+balance.debit-balance.credit
                    elif balance.type_balance == 'passive':
                        res[name][balance.id] = balance.balance_ct-balance.balance_dt-balance.debit+balance.credit
                elif name == 'balance':
                    if balance.type_balance == 'active' or balance.type_balance == 'both' :
                        res[name][balance.id] = abs(balance.balance_dt-balance.balance_ct)
                    elif balance.type_balance == 'passive':
                        res[name][balance.id] = -abs(balance.balance_dt+balance.balance_ct)
                elif name == 'debit':
                    res[name][balance.id] = balance[field_debit]
                elif name == 'credit':
                    res[name][balance.id] = balance[field_credit]

                elif name == 'balance_dt_end':
                    if balance.type_balance == 'passive':
                        continue
                    elif balance.account_kind in _PARTY :
                        party_ids = party_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for party_id in party_obj.browse(party_ids):
                            amount_balance += party_id.balance_dt_end
                        res[name][balance.id] = amount_balance
                    elif balance.account_kind == 'analytic' :
                        analytic_ids = analytic_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for analytic_id in analytic_obj.browse(analytic_ids):
                            if analytic_id.balance_end > 0:
                                amount_balance += analytic_id.balance_end
                        res[name][balance.id] = amount_balance

                    elif balance.type_balance == 'active':
                        res[name][balance.id] = balance.balance_dt+balance.debit-balance.credit

                    elif balance.type_balance == 'both':
                        if balance.balance_dt-balance.balance_ct+balance.debit-balance.credit > 0:
                            res[name][balance.id] = balance.balance_dt-balance.balance_ct+balance.debit-balance.credit
                    else:
                        raise Exception('Error Type unknown', balance.account.code, balance.type_balance)

                elif name == 'balance_ct_end':
                    if balance.type_balance == 'active':
                        continue
                    elif balance.account_kind in _PARTY :
                        party_ids = party_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for party_id in party_obj.browse(party_ids):
                            amount_balance += party_id.balance_ct_end
                        res[name][balance.id] = amount_balance
                    elif balance.account_kind == 'analytic' :
                        analytic_ids = analytic_obj.search([
                                            ('period','=',balance.period.id),
                                            ('account','=',balance.account.id)])
                        for analytic_id in analytic_obj.browse(analytic_ids):
                            if analytic_id.balance_end < 0:
                                amount_balance += abs(analytic_id.balance_end)
                        res[name][balance.id] = amount_balance

                    elif balance.type_balance == 'passive' :
                        res[name][balance.id] = balance.balance_ct-balance.debit+balance.credit

                    elif balance.type_balance == 'both':
                        if balance.balance_ct-balance.balance_dt-balance.debit+balance.credit > 0:
                            res[name][balance.id] = balance.balance_ct-balance.balance_dt-balance.debit+balance.credit
                    else:
                        raise Exception('Error Type unknown', balance.account.code, balance.type_balance)

        return res

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    account = fields.Many2One('ekd.account', 'Account', required=True,  select=2,
                        order_field="account.code", 
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    fiscalyear = fields.Many2One('ekd.fiscalyear', 'Fiscal Year',
                        domain=[
                            ('company','=',Eval('company'))
                        ])
    period_start = fields.Function(fields.Date('Start Period'), 'get_start_date')
    balance_dt = fields.Numeric('Debit Start', digits=(16, Eval('currency_digits', 2)),)
    balance_ct = fields.Numeric('Credit Start', digits=(16, Eval('currency_digits', 2)),)
    debit_01 = fields.Numeric('Debit Turnover 01', digits=(16, Eval('currency_digits', 2)),)
    credit_01 = fields.Numeric('Credit Turnover 01', digits=(16, Eval('currency_digits', 2)),)
    debit_02 = fields.Numeric('Debit Turnover 02', digits=(16, Eval('currency_digits', 2)),)
    credit_02 = fields.Numeric('Credit Turnover 02', digits=(16, Eval('currency_digits', 2)),)
    debit_03 = fields.Numeric('Debit Turnover 03', digits=(16, Eval('currency_digits', 2)),)
    credit_03 = fields.Numeric('Credit Turnover 03', digits=(16, Eval('currency_digits', 2)),)
    debit_04 = fields.Numeric('Debit Turnover 04', digits=(16, Eval('currency_digits', 2)),)
    credit_04 = fields.Numeric('Credit Turnover 04', digits=(16, Eval('currency_digits', 2)),)
    debit_05 = fields.Numeric('Debit Turnover 05', digits=(16, Eval('currency_digits', 2)),)
    credit_05 = fields.Numeric('Credit Turnover 05', digits=(16, Eval('currency_digits', 2)),)
    debit_06 = fields.Numeric('Debit Turnover 06', digits=(16, Eval('currency_digits', 2)),)
    credit_06 = fields.Numeric('Credit Turnover 06', digits=(16, Eval('currency_digits', 2)),)
    debit_07 = fields.Numeric('Debit Turnover 07', digits=(16, Eval('currency_digits', 2)),)
    credit_07 = fields.Numeric('Credit Turnover 07', digits=(16, Eval('currency_digits', 2)),)
    debit_08 = fields.Numeric('Debit Turnover 08', digits=(16, Eval('currency_digits', 2)),)
    credit_08 = fields.Numeric('Credit Turnover 08', digits=(16, Eval('currency_digits', 2)),)
    debit_09 = fields.Numeric('Debit Turnover 09', digits=(16, Eval('currency_digits', 2)),)
    credit_09 = fields.Numeric('Credit Turnover 09', digits=(16, Eval('currency_digits', 2)),)
    debit_10 = fields.Numeric('Debit Turnover 10', digits=(16, Eval('currency_digits', 2)),)
    credit_10 = fields.Numeric('Credit Turnover 10', digits=(16, Eval('currency_digits', 2)),)
    debit_11 = fields.Numeric('Debit Turnover 11', digits=(16, Eval('currency_digits', 2)),)
    credit_11 = fields.Numeric('Credit Turnover 11', digits=(16, Eval('currency_digits', 2)),)
    debit_12 = fields.Numeric('Debit Turnover 12', digits=(16, Eval('currency_digits', 2)),)
    credit_12 = fields.Numeric('Credit Turnover 12', digits=(16, Eval('currency_digits', 2)),)
    account_type = fields.Function(fields.Char('Type Account'), 'get_account_type')
    account_kind = fields.Function(fields.Char('Kind Account'), 'get_account_type')
    type_balance = fields.Function(fields.Char('Type Balance'), 'get_account_type')
    balance = fields.Function(fields.Numeric('Start Balance', digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    debit = fields.Function(fields.Numeric('Debit Turnover', digits=(16, Eval('currency_digits', 2)),), 'get_balance_end')
    credit = fields.Function(fields.Numeric('Credit Turnover', digits=(16, Eval('currency_digits', 2)),), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('End Balance', digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_dt_end = fields.Function(fields.Numeric('Debit End', digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_ct_end = fields.Function(fields.Numeric('Credit End', digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'), 'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    parent = fields.Many2One('ekd.balances.account.year','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.account.year','ID Transfer balance')

    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAccountYear, self).__init__()
        self._order.insert(0, ('fiscalyear', 'ASC'))
        self._order.insert(1, ('account', 'ASC'))

        #self._sql_constraints += [
        #        ('balance_account_uniq', 'UNIQUE(company,period,account)',\
        #         'company, period, account - must be unique per balance!'),
        #         ]

#        self._constraints += [
#        ('balance_account_uniq', 'unique (company,account,period)',\
#              ' company, account, period, currency must be unique per company!')]

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_active(self):
        return True

    def get_start_date(self, ids, name):
        res = {}
        for line in self.browse(ids):
           res[line.id] = line.period.start_date
        return res

    def get_account_type(self, ids, name):
        if name not in ('account_type', 'account_kind', 'type_balance'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(ids):
           if line.account:
            if name == 'account_type':
                res[line.id] = line.account.type.name
            elif name == 'account_kind':
                res[line.id] = line.account.kind
            else:
                res[line.id] = line.account.type_balance
        return res

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.account.currency_digits
        return res

    def get_entries_field(self, ids, name):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        move_line = self.pool.get('ekd.account.move.line')
        res = {}
        for balance in self.browse(ids):
                if name == 'dt_line':
                    res[balance.id] = move_line.search([('dt_balance','=', balance.id)])
                elif name == 'ct_line':
                    res[balance.id] = move_line.search([('ct_balance','=', balance.id)])
        return res

    def set_entries_field(self, id, name, value):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        return

    def button_done(self, ids):
        return self.close(ids)

    def button_draft(self, ids):
        return self.cancel(ids)

    def button_restore(self, ids):
        return self.restore(ids)

    def close(self, ids):
        return self.write(ids, {'state': 'done', })

    def draft(self, ids):
        return self.write(ids, {'state': 'draft', })

    def restore(self, ids):
        return self.write(ids, {'state': 'draft', })

    def test_balance(self, values=None):
        '''
        Проверка баланса счетов 
        values = {'company': ID учетной организации,
                  'period': ID периода,
        '''
        cr = Transaction().cursor
        cr.execute('SELECT a.company, a.period,'\
                    'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc,'\
                    'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'\
                    'FROM ekd_balances_account a'\
                    'LEFT JOIN ekd_account e ON a.account=e.id'\
                    'WHERE a.company=%s AND a.period in %s in '\
                    'GROUP BY a.company, a.period'%(values.get('company'), values.get('period')))
        self.raise_user_warning(
                '%s@account_ru_move_line' % line.id,
                'delete_posted_line')
 
    def test_balance_analytic(self, values=None):
        '''
        Проверка соответствия аналитических остатков
        values = {'company': ID учетной организации,
                  'period': ID периода,
                  'account': [] список ID счетов,
        '''
        cr = Transaction().cursor
        if values.get('account',False):
            cr.execute('SELECT a.company, a.period, a.account, e.code, e.kind, COUNT(a.account) as count_line,'+\
                        'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc,'+\
                        'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'+\
                        'SUM(b.balance) as bal_anl, SUM(b.debit) as debit_anl, SUM(b.credit) as credit_anl,'+\
                        'SUM(c.balance_dt) as bal_dt_party, SUM(c.balance_ct) as bal_ct_party,'+\
                        'SUM(c.debit) as debit_party, SUM(c.credit) as credit_party,'+\
                        'SUM(d.balance) as bal_product, SUM(d.debit) as debit_product,'+\
                        'SUM(d.credit) as credit_product'+\
                    'FROM ekd_balances_account a'+\
                    'LEFT JOIN ekd_balances_analytic b ON a.company=b.company and a.period=b.period and a.account=b.account'+\
                    'LEFT JOIN ekd_balances_party c ON a.company=c.company and a.period=c.period and a.account=c.account'+\
                    'LEFT JOIN ekd_balances_product d ON a.company=d.company and a.period=d.period and a.account=d.account'+\
                    'LEFT JOIN ekd_account e ON a.account=e.id'+\
                    'WHERE a.company=%s AND a.period in %s AND a.account in ('+ ''.join() + ') '+\
                    'GROUP BY a.company, a.period, a.account, e.code ORDER BY e.code'%(values.get('company'), values.get('period')))
        else:
            cr.execute('SELECT a.company, a.period, a.account, e.code, e.kind, COUNT(a.account) as count_line,'+\
                        'SUM(a.balance_dt) as bal_dt_acc, SUM(a.balance_ct) as bal_ct_acc, '+\
                        'SUM(a.debit) as debit_acc, SUM(a.credit) as credit_acc,'+\
                        'SUM(b.balance) as bal_anl, SUM(b.debit) as debit_anl, SUM(b.credit) as credit_anl,'+\
                        'SUM(c.balance_dt) as bal_dt_party, SUM(c.balance_ct) as bal_ct_party,'+\
                        'SUM(c.debit) as debit_party, SUM(c.credit) as credit_party,'+\
                        'SUM(d.balance) as bal_product, SUM(d.debit) as debit_product,'+\
                        'SUM(d.credit) as credit_product'+\
                    'FROM ekd_balances_account a'+\
                    'LEFT JOIN ekd_balances_analytic b ON a.company=b.company and a.period=b.period and a.account=b.account'+\
                    'LEFT JOIN ekd_balances_party c ON a.company=c.company and a.period=c.period and a.account=c.account'+\
                    'LEFT JOIN ekd_balances_product d ON a.company=d.company and a.period=d.period and a.account=d.account'+\
                    'LEFT JOIN ekd_account e ON a.account=e.id'+\
                    'WHERE a.company=%s AND a.period in %s'+\
                    'GROUP BY a.company, a.period, a.account, e.code ORDER BY e.code'%(values.get('company'), values.get('period')))

        for line_id in cr.fetchall():
            if line_id['kind'] == 'analytic':
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_anl']:
                        pass
                    if line_id['debit'] != line_id['debit_anl']:
                        pass
                    if line_id['credit'] != line_id['credit_anl']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_anl']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_anl']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_anl']:
                        pass
            elif line_id['kind'] in _PARTY:
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_dt_party']:
                        pass
                    if line_id['balance_ct'] != line_id['bal_ct_party']:
                        pass
                    if line_id['debit'] != line_id['debit_anl']:
                        pass
                    if line_id['credit'] != line_id['credit_anl']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_dt_party']:
                        pass
                    if line_id['balance_ct']/line_id['count_line'] != line_id['bal_ct_party']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_anl']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_anl']:
                        pass
            elif line_id['kind'] in _PRODUCT:
                if line_id['count_line'] == 1:
                    if line_id['balance_dt'] != line_id['bal_product']:
                        pass
                    if line_id['debit'] != line_id['debit_product']:
                        pass
                    if line_id['credit'] != line_id['credit_product']:
                        pass
                else:
                    if line_id['balance_dt']/line_id['count_line'] != line_id['bal_product']:
                        pass
                    if line_id['debit']/line_id['count_line'] != line_id['debit_product']:
                        pass
                    if line_id['credit']/line_id['count_line'] != line_id['credit_product']:
                        pass
            elif line_id['kind'] == 'money':
                pass
    # Процедура переноса остатков (если есть более поздние)
    def transfer_balance(self, transfer_id, vals):
        balance = self.browse(transfer_id)
        self.write(transfer_id, {
                        'balance_dt': vals.get('balance_dt'),
                        'balance_ct': vals.get('balance_ct'),
                        })
        if balance.transfer and vals.get('transfer', True):
            self.transfer_balance(balance.transfer.id, {
                        'balance_dt':balance.balance_dt_end,
                        'balance_ct':balance.balance_ct_end,
                        'transfer': vals.get('transfer', True),
                        })


    def transfer_balances(self, vals=None):
        '''
            Transfer Balances of account - Перенос остатков.
            period     - словарь идентификаторов периодов (периоды уже отсортированны!!!)
            context    - словарь контекст
        '''
        if vals is None and not vals.get('company'):
            return False
        if vals.get('transfer_analytic',True):
            bal_analytic_obj = self.pool.get('ekd.balances.analytic')
            bal_party_obj = self.pool.get('ekd.balances.party')
            bal_product_obj = self.pool.get('ekd.balances.product')

        balance_ids= {}
        for period in vals.get('periods'):
            if not balance_ids:
                balance_ids = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period)
                            ])
                continue

            for balance_id in balance_ids:
                balance_line = self.browse(balance_id)
                if balance_line.balance_dt_end or balance_line.balance_ct_end:
                    # Перенос остатков по аналитическим счетам
                    if vals.get('transfer_analytic', True):
                        if balance_line.account.kind_analytic == 'analytic':
                            bal_analytic_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })
                        elif balance_line.account.kind_analytic in _PARTY:
                            bal_party_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })
                        elif balance_line.account.kind_analytic in _PRODUCT:
                            bal_product_obj.transfer_balances({
                                            'company': vals.get('company'),
                                            'periods': vals.get('periods'),
                                            'account': balance_line.account.id ,
                                            })

                    if balance_line.transfer:
                        self.transfer_balance(balance_line.transfer.id, {
                                    'balance_dt': balance_line.balance_dt_end,
                                    'balance_ct': balance_line.balance_ct_end,
                                    })
                    else:
                        balance_new_id = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period),
                            ('account','=',balance_line.account.id),
                            ])
                        if balance_new_id:
                            if isinstance(balance_new_id,list):
                                    balance_new_id = balance_new_id[0]
                            self.write(balance_line.id, {
                                    'transfer': balance_new_id,
                                    })
                            self.write(balance_new_id, {
                                    'balance_dt': balance_line.balance_dt_end,
                                    'balance_ct': balance_line.balance_ct_end,
                                    })

                        else:
                            self.write(balance_line.id, {
                                    'transfer': self.create({
                                            'company': vals.get('company'),
                                            'period': period,
                                            'account':  balance_line.account.id ,
                                            'currency': balance_line.currency.id,
                                            'balance_dt': balance_line.balance_dt_end,
                                            'balance_ct': balance_line.balance_ct_end,
                                            })
                                    })

            balance_ids = self.search([
                            ('company','=', vals.get('company')),
                            ('period','=',period)
                            ])

        return True

BalanceAccountYear()

################################################################################
#
# Ежедневные остатки по финансовым счетам (Касса, Банк)
#
class BalanceFinance(ModelSQL, ModelView):
    "Turnover and Balances finance accounts"
    _name = "ekd.balances.finance"
    _description =__doc__

    def get_balance(self, ids, name):
        if not ids:
            return {}
        cr = Transaction().cursor
        cr.execute('select id, balance+debit-credit as balance_end from ekd_balances_finance where id in ('+','.join(map(str,ids))+')')
        result = dict(cr.fetchall())
        for id in ids:
            result.setdefault(id, Decimal('0.0'))
        return result

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    account = fields.Many2One('ekd.account', 'Account', required=True,
                    domain=[
                        ('kind_analytic','in',_MONEY),
                        ('company','=', Eval('company'))
                    ], select=2,
                    on_change=['company', 'date_balance', 'account', 'state'])
    #account_type = fields.Function(fields.Char('Type Account'), 'get_account_type')
    #account_kind = fields.Function(fields.Char('Kind Account'), 'get_account_type')
    account_kind_analytic = fields.Function(fields.Char('Kind Account Analytic'), 'get_account_type')
    #type_balance = fields.Function(fields.Char('Type Balance'), 'get_account_type')
    date_balance = fields.Date('Date Balance', required=True)
    done_date = fields.Date('Done Date')
    balance = fields.Numeric('Balances start period', digits=(16, Eval('currency_digits', 2)),)
    debit = fields.Numeric('Amount debit turnover', digits=(16, Eval('currency_digits', 2)),)
    credit = fields.Numeric('Amount credit turnover', digits=(16, Eval('currency_digits', 2)),)
    balance_end = fields.Function(fields.Numeric('End Balance', digits=(16, Eval('currency_digits', 2))), 'get_balance')
    currency = fields.Many2One('currency.currency', 'Currency account', )
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'), 'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    lines = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Entryes'), 'get_entries_field', setter='set_entries_field')
    income = fields.Function(fields.Numeric('Income', digits=(16, Eval('currency_digits', 2))), 'get_amount_sum')
    expense = fields.Function(fields.Numeric('Expense', digits=(16, Eval('currency_digits', 2))), 'get_amount_sum')
    documents_cash = fields.One2Many('ekd.document.head.cash', 'balance', 
                                    'Document', states=_BALANCE_STATES, 
                                    depends=_BALANCE_DEPENDS,
                                    context={
                                        'company':Eval('company'), 
                                        'date_account':Eval('date_balance'), 
                                        'cash_account':Eval('account'),
                                        'cash_balance':Eval('balance')})
    documents_cash_fnc = fields.Function(fields.One2Many('ekd.document.head.cash', 'balance', 
                                    'Document', states=_BALANCE_STATES, 
                                    depends=_BALANCE_DEPENDS),
                                    'get_document_cash', setter='set_document_cash')

    documents_bank = fields.One2Many('ekd.document.head.bank', 'balance', 'Document', states=_BALANCE_STATES, depends=_BALANCE_DEPENDS,
                                    context={'company':Eval('company'), 'date_account':Eval('date_balance'), 'bank_account':Eval('account')})
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True, readonly=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')
    parent = fields.Many2One('ekd.balances.finance','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.finance','ID Transfer balance')

    def __init__(self):
        super(BalanceFinance, self).__init__()
        self._rpc.update({
                    'button_open': True,
                    'button_done': True,
                    'button_draft': True,
                    'button_restore': True,})

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(1, ('date_balance', 'ASC'))

        self._sql_constraints += [
                 ('balance_finance_uniq', 'UNIQUE(company,date_balance,account)',\
              'company, date_balance, account - must be unique per balance!'),
                           ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceFinance, self).init(module_name)
        table = TableHandler(cursor, self, module_name)
        # Проверяем счетчик
        cursor.execute("SELECT last_value, increment_by FROM %s"%table.sequence_name)
        last_value, increment_by = cursor.fetchall()[0]

        # Устанавливаем счетчик
        if str(last_value)[len(str(last_value))-1] != str(_ID_TABLES_BALANCES[self._table]):
            cursor.execute("SELECT setval('"+table.sequence_name+"', %s, true)"%_ID_TABLES_BALANCES[self._table])
        if increment_by != 10:
            cursor.execute("ALTER SEQUENCE "+table.sequence_name+" INCREMENT 10")

    def create(self, vals):
        if not vals.get('balance', False):
            balance_old_id = self.search([
                                        ('date_balance','<',vals.get('date_balance')),
                                        ('account','=',vals.get('account'))
                                        ], limit=1, order=[('date_balance','DESC')])
            if balance_old_id:
                if isinstance(balance_old_id, list):
                    balance_old_id = balance_old_id[0]
                vals['balance'] = self.browse(balance_old_id).balance_end
        res = super(BalanceFinance, self).create(vals)
        return res

    def default_currency_digits(self):
        return 2

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_active(self):
        return True

    def default_account(self):
        return Transaction().context.get('account') or False

    def default_date_balance(self):
        return Transaction().context.get('date_balance') or datetime.datetime.today()

    def get_rec_name(self, ids, name):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for pr in self.browse(ids):
            res[pr.id] = u"Орг.: %s, Дата: %s, Счет: %s" % (pr.company.shortname, pr.date_balance.strftime('%d.%m.%Y'), pr.account.code)
        return res

    def get_currency_digits(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    res[name][line.id] = line.account.currency_digits
                elif name == 'second_currency_digits':
                    if line.account.second_currency:
                        res[name][line.id] = line.account.second_currency.digits
        return res
    def get_document_cash(self, ids, name):
        res={}.fromkeys(ids, False)
        doc_cash_obj = self.pool.get('ekd.document.head.cash')
        for line in self.browse(ids):
            res[line.id] = doc_cash_obj.search([
                                    ('date_account','=',line.date_balance),
                                    ('cash_account','=',line.account.id)
                                    ])
        return res

    def set_document_cash(self, ids, name, vals):
        doc_cash_obj = self.pool.get('ekd.document.head.cash')
        if name =='document_cash_fnc':
            for value in vals:
                if value[0] == 'add':
                    raise Exception(str(value))
                elif value[0] == 'write':
                    doc_cash_obj.write(value[1], value[2])
                elif value[0] == 'create':
                    value[1]['balance'] = ids[0]
                    doc_cash_obj.create(value[1])
                elif value[0] == 'delete':
                    doc_cash_obj.delete(value[1])
        return
   
    def get_account_type(self, ids, name):
        if name not in ('account_type', 'account_kind', 'account_kind_analytic'):
            raise Exception('Invalid name Balances Finance')
        res = {}
        for line in self.browse(ids):
           if line.account:
            if name == 'account_type':
                res[line.id] = line.account.type.name
            elif name == 'account_kind':
                res[line.id] = line.account.kind
            elif name == 'account_kind_analytic':
                res[line.id] = line.account.kind_analytic
            else:
                res[line.id] = line.account.type_balance
        return res

    def get_entries_field(self, ids, name):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        move_line = self.pool.get('ekd.account.move.line')
        res = {}
        for balance in self.browse(ids):
            if name == 'dt_line':
                res[balance.id] = move_line.search([('dt_balance2','=', balance.id)])
            elif name == 'ct_line':
                res[balance.id] = move_line.search([('ct_balance2','=', balance.id)])
            elif name == 'lines':
                res[balance.id] = move_line.search(['OR',('dt_balance2','=', balance.id), ('ct_balance2','=', balance.id)])
        return res

    def set_entries_field(self, id, name, value):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        if not value:
            return

    def get_amount_sum(self, ids, names):
        if not ids:
            return []
        res={}
        for page in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(page.id, Decimal('0.0'))
                amount_sum = Decimal('0.0')
                for document in page.documents_cash:
                    if document.type_transaction == name and document.state == 'posted':
                        amount_sum += abs(document.amount)
                res[name][page.id] = amount_sum
        return res

    def on_change_account(self, values):
        if not values.get('company') or not values.get('date_balance') or not values.get('account') :
            return {}
        res={}
        template_obj = self.pool.get('ekd.document.template')
        if not values.get('state'):
            values['state'] = 'draft'
        balance_ids = self.search([
                                ('date_balance','<' , values.get('date_balance')),
                                ('account','=' , values.get('account'))], limit=1, order=[('date_balance', 'DESC')])

        if isinstance(balance_ids, list):
            if len(balance_ids) > 0:
                balance_ids = balance_ids[0]
                res['balance'] = self.browse(balance_ids).balance_end
        res['id'] = self.create(values)
        return res

    def button_open(self, ids):
        return self.open(ids)

    def button_done(self, ids):
        return self.post(ids)

    def button_draft(self, ids):
        return self.draft(ids)

    def button_restore(self, ids):
        return self.draft(ids)

    def post(self, ids):
        date_obj = self.pool.get('ir.date')
        return self.write(ids, {
                    'done_date': datetime.datetime.now(),
                    'state': 'done',
                    })

    def draft(self, ids):
        return self.write(ids, {
                    'state': 'draft',
                    })

    def open(self, ids):
        return self.write(ids, {
                    'state': 'open',
                    })

    def restore(self, ids):
        return self.write(ids, {
                    'state': 'draft',
                    })
   # Процедура переноса остатков (если есть более поздние)
    def transfer_balance(self, transfer_id, vals):
        balance = self.browse(transfer_id)
        self.write(transfer_id, {
                        'balance': vals.get('balance'),
                        })
        if balance.transfer and vals.get('transfer',True):
            self.transfer_balance(balance.transfer.id, {
                        'balance':balance.balance_end,
                        'transfer': vals.get('transfer',True)
                        })

BalanceFinance()

class FinanceOpen(Wizard):
    'Finance Open'
    _name = 'ekd.balances.finance.open'
    states = {
            'init': {
                'result': {
                        'type': 'action',
                        'action': '_action_open',
                        'state': 'end',
                        },
                    },
            }

    def _action_open(self, data):
        if not data['ids']:
            return {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        book_cash_obj = self.pool.get('ekd.balances.finance')
        context = Transaction().context
        act_window_id = model_data_obj.get_id('ekd_account', 'act_page_book_cash_form')
        page_cash = book_cash_obj.browse(data['id'])
        res = act_window_obj.read(act_window_id)
        res['pyson_domain'] = [('balance', '=', data['id']),]
        res['pyson_domain'] = PYSONEncoder().encode(res['pyson_domain'])
        res['pyson_context'] = PYSONEncoder().encode({
                'balance': data['id'],
                'date_account': page_cash.date_balance,
                'cash_account': page_cash.account.id,
                'cash_balance': str(page_cash.balance),
            })
        res['name'] +=  u': - ' + page_cash.date_balance.strftime('%d.%m.%Y')+\
                        u' Счет: ' + page_cash.account.rec_name+\
                        u' Остаток на начала: ' +str(page_cash.balance)
        #raise Exception(str(res))
        return res

FinanceOpen()