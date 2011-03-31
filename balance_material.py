# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты.
# 3. Тип счетов
# 3. Остатки по аналитическим счетам
##############################################################################
"Balances Analytic Accounting (Material)"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.tools import safe_eval
from trytond.backend import TableHandler
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import Equal, Eval, Not, In
from account import _PARTY, _PRODUCT, _MONEY, _LEVEL_ANALYTIC, _ANALYTIC_PARTY
from balance_account import _ID_TABLES_BALANCES, _ID_TABLES_BALANCES_PERIOD
import datetime

################################################################################
#
# Остатки по товарным счетам за периоды (Товарно-материальные ценности)
#

class BalanceProductMaterial(ModelSQL, ModelView):
    "Turnover and Balances product (Material)"
    _name = "ekd.balances.material"
    _description =__doc__

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    account = fields.Many2One('ekd.account', 'Account', required=True,
               domain=[
                    ('kind_analytic', 'in', _PRODUCT),['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False)
                ]], select=2)
    account_type = fields.Function(fields.Char('Type Account'), 'get_account_type')
    account_kind = fields.Function(fields.Char('Kind Account'), 'get_account_type')
    type_balance = fields.Function(fields.Char('Type Balance'), 'get_account_type')
    department = fields.Many2One('ekd.company.department', 'Location', required=True,
                domain=[
                  ('company', '=', Eval('company'))
                ], select=2)
    party = fields.Many2One('party.party', 'Party Ref.', required=True,
                domain=[
                  ('employee', '=', True)
                ], select=2)
    product = fields.Many2One('product.product', 'Product Ref.', required=True, select=2)
    product_uom = fields.Many2One('product.uom', 'Unit Ref.', required=True, select=2)
    periods = fields.One2Many('ekd.balances.material.period', 'account', 'Periods')

    qbalance = fields.Function(fields.Float('Quantity start balance', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_end')
    balance = fields.Function(fields.Numeric('Balances start period', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    qdebit = fields.Function(fields.Float('Quantity input turnover', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_end')
    debit = fields.Function(fields.Numeric('Amount input turnover', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    qcredit = fields.Function(fields.Float('Quantity revenue turnover', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_end')
    credit = fields.Function(fields.Numeric('Amount revenue turnover', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    qbalance_end = fields.Function(fields.Numeric('Quantity balance end period', 
                        digits=(16,2)), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('Balance end period', 
                        digits=(16,2)), 'get_balance_end')
    unit_digits = fields.Function(fields.Integer('Unit Digits', 
                        on_change_with=['product_uom']), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 
                        'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                        None, 'Ref entry debit lines'),'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                        None, 'Ref entry credit lines'), 'get_entries_field')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    active = fields.Boolean('Active')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductMaterial, self).__init__()

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(1, ('party', 'ASC'))
        self._order.insert(2, ('department', 'ASC'))
        self._order.insert(3, ('product', 'ASC'))
        self._order.insert(4, ('product_uom', 'ASC'))

        self._sql_constraints += [
                ('balance_product_uniq', 'UNIQUE (account,department,party,product,product_uom)',\
              'account, department, party ,product, product_uom must be unique per analytic account period (Material)!!')
                           ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceProductMaterial, self).init(module_name)
        table = TableHandler(cursor, self, module_name)
        # Проверяем счетчик
        cursor.execute("SELECT last_value, increment_by FROM %s"%table.sequence_name)
        last_value, increment_by = cursor.fetchall()[0]

        # Устанавливаем счетчик
        if str(last_value)[len(str(last_value))-1] != str(_ID_TABLES_BALANCES[self._table]):
            cursor.execute("SELECT setval('"+table.sequence_name+"', %s, true)"%_ID_TABLES_BALANCES[self._table])
        if increment_by != 10:
            cursor.execute("ALTER SEQUENCE "+table.sequence_name+" INCREMENT 10")

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency_digits(self):
        return 2

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
                res[line.id] = line.account.kind_analytic
            else:
                res[line.id] = line.account.type_balance
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for balance in self.browse(ids):
            res[balance.id] = balance.product.name
        return res

    def get_balance_end(self, ids, names):
        if not ids:
            return {}
        res={}
        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
#                res[name].setdefault(balance.id, 0.0)
                if name == 'balance_end':
                    res[name][balance.id] = balance.balance-balance.credit+balance.debit
                elif name == 'qbalance_end':
                    res[name].setdefault(balance.id, 0.0)
                    res[name][balance.id] = Decimal(str(balance.qbalance+balance.qdebit-balance.qcredit))

        return res

    def get_entry(self, ids, name):
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

    def on_change_with_unit_digits(self, vals):
        uom_obj = self.pool.get('product.uom')
        if vals.get('uom'):
            uom = uom_obj.browse(vals['uom'])
            return uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        res = {}
        for balance in self.browse(ids):
            res[balance.id] = balance.product_uom.digits
        return res

    # Процедура переноса остатков (если есть более поздние)
    def transfer_balance(self, transfer_id, vals):
        balance = self.browse(transfer_id)
        self.write(transfer_id, {
                        'qbalance': vals.get('qbalance'),
                        'balance': vals.get('balance'),
                        })
        if balance.transfer and vals.get('transfer', True):
            self.transfer_balance(balance.transfer.id, {
                        'qbalance':balance.qbalance_end,
                        'balance':balance.balance_end,
                        'transfer': vals.get('transfer', True),
                        })

    def transfer_balances(self, vals=None):
        '''
            Transfer Balances of account - Перенос остатков.
            cr         - курсор
            uid        - ИД пользователя
            period     - словарь идентификаторов периодов (периоды уже отсортированны!!!)
            context    - словарь контекст
        '''
        if vals is None and not vals.get('company', False) and not vals.get('account', False):
            return False

        balance_ids= {}
        for period in vals.get('periods'):
            if not balance_ids:
                balance_ids = self.search([
                                ('period','=',period),
                                ('account','=', vals.get('account')),
                                ])
                continue
            for balance_id in balance_ids:
                balance_line = self.browse(balance_id)
                if balance_line.balance_end:
                    if balance_line.transfer and vals.get('transfer_analytic', True):
                        self.transfer_balance(balance_line.transfer.id, {
                                    'qbalance': balance_line.qbalance_end,
                                    'balance': balance_line.balance_end,
                                    'transfer_analityc': vals.get('transfer_analytic', True),
                                    })
                    else:
                        balance_new_id = self.search([
                            ('period','=',period),
                            ('account','=',vals.get('account')),
                            ('party','=',balance_line.party.id),
                            ('product','=', balance_line.product.id),
                            ('product_uom','=', balance_line.product_uom.id),
                            ('unit_price','=', balance_line.unit_price),
                            ])
                        if balance_new_id:
                            self.write(balance_line.id, {
                                    'transfer': balance_new_id,
                                    })
                            self.write(balance_new_id, {
                                    'qbalance': balance_line.qbalance_end,
                                    'balance': balance_line.balance_end,
                                    })

                        else:
                            self.write(balance_line.id, {
                                    'transfer': self.create({
                                            'company': vals.get('company'),
                                            'period': period,
                                            'account':  balance_line.account.id ,
                                            'party': balance_line.party.id,
                                            'product': balance_line.product.id,
                                            'product_uom': balance_line.product_uom,
                                            'unit_price': balance_line.unit_price,
                                            'qbalance': balance_line.qbalance_end,
                                            'balance': balance_line.balance_end,
                                            })
                                    })

            balance_ids = self.search([
                                ('period','=',period),
                                ('account','=', vals.get('account')),
                                ])

        return True

BalanceProductMaterial()

class BalanceProductMaterialPeriod(ModelSQL, ModelView):
    "Turnover and Balances Material (Period)"
    _name = "ekd.balances.material.period"
    _description =__doc__

    account = fields.Many2One('ekd.balances.material', 'Material', required=True, select=2)
    period = fields.Many2One('ekd.period', 'Period', required=True, select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    amount_periods = fields.One2Many('ekd.balances.material.balance', 'period_product', 
                                'Turnover Material in Period (Full)')
    balance_fifo = fields.Function(fields.One2Many('ekd.balances.material.balance', 
                                None, 'Turnover Material in Period'),
                                'get_amount_fifo', setter='set_amount_fifo')
    balance_lifo = fields.Function(fields.One2Many('ekd.balances.material.balance', 
                                None, 'Turnover Material in Period'),
                                'get_amount_fifo', setter='set_amount_fifo')
    balance_date_income = fields.Function(fields.One2Many('ekd.balances.material.balance', 
                                None, 'Turnover Material in Period'),
                                'get_amount_input', setter='set_amount_input')
    balance_fixed = fields.Function(fields.One2Many('ekd.balances.material.balance', 
                                None, 'Turnover Material in Period'),
                                'get_amount_fixed', setter='set_amount_fixed')
    balance_average = fields.Function(fields.Many2One('ekd.balances.material.balance',
                                'Turnover Material in Period'),
                                'get_amount_average', setter='set_amount_average')
    balance_partion = fields.Function(fields.One2Many('ekd.balances.material.balance', 
                                None, 'Turnover Material in Period'),
                                'get_amount_partion', setter='set_amount_partion')

    state = fields.Function(fields.Char('State'), 'get_period_state')
    active = fields.Boolean('Active')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductMaterialPeriod, self).__init__()

        #self._order.insert(0, ('account', 'ASC'))
        #self._order.insert(1, ('period', 'ASC'))

        self._sql_constraints += [
                ('period_uniq', 'UNIQUE (account,period)',\
                    'account, period must be unique per analytic account period (Material)!')
                ]

    def default_active(self):
        return True

    def get_period_state(self, ids, name):
        res = {}.fromkeys(ids, 'done')
        for line_period in self.browse(ids):
            res[line_period.id] = line_period.period.state
        return res

    def get_amount_fifo(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ], order=[('date_income','DESC')])
        return res

    def set_amount_fifo(self, ids, name, vals):
        pass

    def get_amount_lifo(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids),
                            ], order=[('date_income','ASC')])
        return res

    def set_amount_lifo(self, ids, name, vals):
        pass

    def get_amount_input(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids),
                            ], order=[('date_income','ASC')])
        return res

    def set_amount_input(self, ids, name, vals):
        pass

    def get_amount_fixed(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ])
        return res

    def set_amount_fixed(self, ids, name, vals):
        pass

    def get_amount_partion(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ])
        return res

    def set_amount_partion(self, ids, name, vals):
        pass

    def get_amount_average(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.material.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
                res[amount_line.id] = amount_obj.search([
                                    ('period_product','in', ids)
                                    ], limit=1)
        return res

    def set_amount_average(self, ids, name, vals):
        pass

BalanceProductMaterialPeriod()

class BalanceProductMaterialBalance(ModelSQL, ModelView):
    "Turnover and Balances Material (Balance)"
    _name = "ekd.balances.material.balance"
    _description =__doc__

    period_product = fields.Many2One('ekd.balances.material.period', 'Material', required=True, select=2)
    # Партионный учет
    #partion = fields.Many2One('Partionny', digits=(16, Eval('currency_digits', 2)))
    # Для ФИФО, ЛИФО, Дата прихода,
    date_income = fields.Date('Date Income')
    # Для учетных цен
    unit_price = fields.Numeric('Price input', digits=(16, Eval('currency_digits', 2)))
    qbalance = fields.Float('Quantity Start Period', digits=(16, Eval('unit_digits', 2)))
    balance = fields.Numeric('Balances Start Period', digits=(16, Eval('currency_digits', 2)))
    qdebit = fields.Float('Quantity income', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount income', digits=(16, Eval('currency_digits', 2)))
    qcredit = fields.Float('Quantity revenue', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount revenue', digits=(16, Eval('currency_digits', 2)))
    qbalance_end = fields.Function(fields.Numeric('Quantity End Period', digits=(16,2)), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('Amount End Period', digits=(16,2)), 'get_balance_end')
    unit_digits = fields.Function(fields.Integer('Unit Digits', on_change_with=['product_uom']), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'),'get_entry')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entry')
    parent = fields.Many2One('ekd.balances.material.balance','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.material.balance','ID Transfer balance')
    active = fields.Boolean('Active')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductMaterialBalance, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceProductMaterialBalance, self).init(module_name)
        table = TableHandler(cursor, self, module_name)
        # Проверяем счетчик
        cursor.execute("SELECT last_value, increment_by FROM %s"%table.sequence_name)
        last_value, increment_by = cursor.fetchall()[0]

        # Устанавливаем счетчик
        if str(last_value)[len(str(last_value))-1] != str(_ID_TABLES_BALANCES_PERIOD[self._table]):
            cursor.execute("SELECT setval('"+table.sequence_name+"', %s, true)"%_ID_TABLES_BALANCES_PERIOD[self._table])
        if increment_by != 10:
            cursor.execute("ALTER SEQUENCE "+table.sequence_name+" INCREMENT 10")

    def default_active(self):
        return True

BalanceProductMaterialBalance()

class BalanceProductMaterialAdd(ModelSQL, ModelView):
    _name = "ekd.balances.material"

    curr_period = fields.Many2One('ekd.balances.material.period', 'Current Period')
    last_period = fields.Many2One('ekd.balances.material.period', 'Last Period')

BalanceProductMaterialAdd()

