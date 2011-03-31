# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты.
# Обороты и остатки по активом предприятий 
# - Основные средства 
# - Нематериальные активы
# - Ценные бумаги
# - И то что можете еще придумать!!!
##############################################################################
"Balances Analytic Accounting (Assets)"
from trytond.model import ModelView, ModelSQL, fields
#from trytond.wizard import Wizard
#from trytond.report import Report
from trytond.transaction import Transaction
#from trytond.tools import safe_eval
from trytond.backend import TableHandler
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import Equal, Eval, Not, In
from account import _PRODUCT
#, _LEVEL_ANALYTIC, _ANALYTIC_PARTY
from balance_account import _ID_TABLES_BALANCES, _ID_TABLES_BALANCES_PERIOD
import datetime

#
# Активы организации
#
class BalanceAssets(ModelSQL, ModelView):
    "Turnover and Balances Assets"
    _name = "ekd.balances.assets"
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
    employee = fields.Many2One('company.employee', 'Employee', required=True, select=2)
    product = fields.Many2One('product.product', 'Product Ref.', required=True, select=2)
    product_uom = fields.Many2One('product.uom', 'Unit Ref.', required=True, select=2)
    unit_price = fields.Numeric('Price input', digits=(16, Eval('currency_digits', 2)))
    unit_digits = fields.Function(fields.Integer('Unit Digits', on_change_with=['product_uom']), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                    None, 'Ref entry debit lines'),'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                    None, 'Ref entry credit lines'), 'get_entries_field')
    active = fields.Boolean('Active')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceAssets, self).__init__()

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(2, ('employee', 'ASC'))
        self._order.insert(3, ('product', 'ASC'))
        self._order.insert(4, ('product_uom', 'ASC'))
        self._order.insert(5, ('unit_price', 'ASC'))

        self._sql_constraints += [
                ('balance_assets_uniq', 'UNIQUE (company,account,employee,product,product_uom,unit_price)',\
              'company, account, employee, product, product_uom, unit_price must be unique per balance!')
                           ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAssets, self).init(module_name)
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
        if name not in ('account_type', 'account_kind'):
            raise Exception('Invalid name')
        res = {}
        for line in self.browse(ids):
           if line.account:
            if name == 'account_type':
                res[line.id] = line.account.type.name
            elif name == 'account_kind':
                res[line.id] = line.account.kind_analytic
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

#    def set_entries_field(self, id, name, value):
#        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
#        return

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

BalanceAssets()

class BalanceAssetsPeriod(ModelSQL, ModelView):
    "Turnover and Balances Assets (Period)"
    _name = "ekd.balances.assets.period"
    _description =__doc__
    _inherits = {'ekd.balances.assets': 'assets'}

    def get_balance(self, ids, names):
        if not ids:
            return {}
        cr = Transaction().cursor
        cr.execute('select id, COALESCE(balance, 0)+COALESCE(debit, 0)-COALESCE(credit, 0) as balance_end, '\
                    'COALESCE(balance_quantity, 0)+COALESCE(debit_quantity, 0)-COALESCE(credit_quantity, 0) '\
                    'as balance_quantity_end from ekd_balances_assets_period where id in ('+','.join(map(str,ids))+')')
        res = {}
        for account_id, balance_end, balance_qt_end in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(balance_end, Decimal):
                balance_end = Decimal(str(balance_end))
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(account, Decimal('0.0'))
                if name == 'balance_end':
                    res[name][account_id] = balance_end
                elif name == 'balance_quantity_end':
                    res[name][account_id] = balance_qt_end

        return res

    assets = fields.Many2One('ekd.balances.assets', 'Analytic Account', required=True,  select=2,)
    period = fields.Many2One('ekd.period', 'Period')
    period_state = fields.Function(fields.Char('ekd.period', 
                                'Period State'), 'get_period_state')

    uom = fields.Many2One('product.uom', 'UoM', required=True, select=2,)
    unit_digits = fields.Function(fields.Integer('Unit Digits'), 'get_unit_digits')
    balance = fields.Numeric('Start Balance', digits=(16, Eval('currency_digits', 2)))
    qbalance = fields.Float('Start Quantity', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount Income', digits=(16, Eval('currency_digits', 2)))
    qdebit = fields.Float('Quantity Income', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount Expense', digits=(16, Eval('currency_digits', 2)))
    qcredit = fields.Float('Quantity Expense', digits=(16, Eval('unit_digits', 2)))
    balance_end = fields.Function(fields.Numeric('End Balance', 
            digits=(16, Eval('currency_digits', 2))), 'get_balance')
    qbalance_end = fields.Function(fields.Float('End Quantity', 
            digits=(16, Eval('unit_digits', 2))), 'get_balance')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 
            'Ref entry debit lines'), 'get_entry')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 
            'Ref entry credit lines'), 'get_entry')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    parent = fields.Many2One('ekd.balances.assets.period','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.assets.period','ID Transfer balance')
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAssetsPeriod, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAssetsPeriod, self).init(module_name)
        table = TableHandler(cursor, self, module_name)
        # Проверяем счетчик
        cursor.execute("SELECT last_value, increment_by FROM %s"%table.sequence_name)
        last_value, increment_by = cursor.fetchall()[0]

        # Устанавливаем счетчик
        if str(last_value)[len(str(last_value))-1] != str(_ID_TABLES_BALANCES_PERIOD[self._table]):
            cursor.execute("SELECT setval('"+table.sequence_name+"', %s, true)"%_ID_TABLES_BALANCES_PERIOD[self._table])
        if increment_by != 10:
            cursor.execute("ALTER SEQUENCE "+table.sequence_name+" INCREMENT 10")

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_currency_digits(self):
        return 2

    def default_active(self):
        return True

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[name][line.id] = line.account.currency_digits
        return res

    def get_entry(self, ids, name):
        move_line = self.pool.get('ekd.account.move.line')
        move_line_analytic_dt = self.pool.get('ekd.account.move.line.analytic_dt')
        move_line_analytic_ct = self.pool.get('ekd.account.move.line.analytic_ct')
        res = {}
        for balance in self.browse(ids):
            if name == 'dt_line':
                line_analytic_dt = move_line_analytic_dt.search([('ref_period','=', balance.id)])
                res[balance.id] = move_line_analytic_dt.read(line_analytic_ct, ['move_line'])
            elif name == 'ct_line':
                line_analytic_ct = move_line_analytic_ct.search([('ref_period','=', balance.id)])
                res[balance.id] = move_line_analytic_ct.read(line_analytic_ct, ['move_line'])
        return res

    def get_period_state(self, ids, name):
        res = {}.fromkeys(ids, 'done')
        for line_period in self.browse(ids):
            res[line_period.id] = line_period.period.state
        return res

    def get_account_type(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, False)
                if name == 'account_type':
                    res[name][line.id] = line.account.type.name
                elif name == 'account_kind':
                    res[name][line.id] = line.account.kind_analytic
        return res

    # Процедура переноса остатков (если есть более поздние)
    def transfer_balance(self, transfer_id, vals):
        balance = self.browse(transfer_id)
        self.write(transfer_id, {
                        'balance': vals.get('balance'),
                        })
        if balance.transfer and vals.get('transfer', True):
            self.transfer_balance(balance.transfer.id, {
                        'balance':balance.balance_end,
                        'transfer': vals.get('transfer', True),
                        })

    def transfer_balances(self, vals=None):
        '''
            Transfer Balances of account - Перенос остатков.
            period     - словарь идентификаторов периодов (периоды уже отсортированны!!!)
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
                    if balance_line.transfer:
                        self.transfer_balance(balance_line.transfer.id, {
                                    'balance': balance_line.balance_end,
                                    })
                    else:
                        balance_new_id = self.search([
                            ('period','=',period),
                            ('account','=',vals.get('account')),
                            ])
                        if balance_new_id:
                            self.write(balance_line.id, {
                                    'transfer': balance_new_id,
                                    })
                            self.write(balance_new_id, {
                                    'balance': balance_line.balance_end,
                                    })

                        else:
                            self.write(balance_line.id, {
                                    'transfer': self.create({
                                            'company': vals.get('company'),
                                            'period': period,
                                            'account':  balance_line.account.id ,
                                            'analytic': balance_line.analytic.id,
                                            'balance': balance_line.balance_end,
                                            })
                                    })

            balance_ids = self.search([
                                ('period','=',period),
                                ('account','=', vals.get('account')),
                                ])

        return True

BalanceAssetsPeriod()

#
# Остатки по счетам основных средств за периоды (Товарно-материальные ценности)
#
class BalanceProductFixedAssets(ModelSQL, ModelView):
    "Turnover and Balances Fixed Assets"
    _name = "ekd.balances.fixed_assets"
    _description =__doc__
    _inherits = {'ekd.balances.assets': 'assets'}

    assets = fields.Many2One('ekd.balances.assets', 'Assets', required=True,
            ondelete='CASCADE')

    date_income = fields.Date('Date Income', required=True)
    date_expense = fields.Date('Date Expense')
    period_income = fields.Many2One('ekd.period', 'Period Income', required=True, select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    period_expense = fields.Many2One('ekd.period', 'Period Expense', select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    initial_cost = fields.Numeric('Initial cost', digits=(16, Eval('currency_digits', 2)))
    replacement = fields.Numeric('Replacement value', digits=(16, Eval('currency_digits', 2)))
    residual = fields.Numeric('Residual value', digits=(16, Eval('currency_digits', 2)))
    deprecation = fields.Many2Many("ekd.balances.fixed_assets.deprecation", 'fixed_assets', 'move_line', 'Deprecation')

    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductFixedAssets, self).__init__()

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency_digits(self):
        return 2

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for balance in self.browse(ids):
            res[balance.id] = balance.product.name
        return res

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        company_id = Transaction().context.get('company')
        company = self.pool.get('company.company').browse(company_id)
        for line in self.browse(ids):
            if line.account.currency:
                res[line.id] = line.account.currency.currency_digits
            elif company.currency:
                res[line.id] = company.currency.currency_digits

BalanceProductFixedAssets()

class BalanceProductFixedAssetsDeprecation(ModelSQL, ModelView):
    "Deprecation Fixed Assets"
    _name = "ekd.balances.fixed_assets.deprecation"
    _description =__doc__

    fixed_assets = fields.Many2One('ekd.balances.fixed_assets', 'Assets', required=True,
            ondelete='CASCADE')
    move_line = fields.Many2One('ekd.account.move.line', 'Move Line')
    account = fields.Many2One('ekd.account', 'Account Deprecation')
    amount = fields.Numeric('Amount Deprecation', digits=(16, Eval('currency_digits', 2)))
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        company_id = Transaction().context.get('company')
        company = self.pool.get('company.company').browse(company_id)
        for line in self.browse(ids):
            if line.account.currency:
                res[line.id] = line.account.currency.currency_digits
            elif company.currency:
                res[line.id] = company.currency.currency_digits

        return res

BalanceProductFixedAssetsDeprecation()
#
# Остатки по счетам нематериальных активов за периоды (Товарно-материальные ценности)
#
class BalanceProductIntangible(ModelSQL, ModelView):
    "Turnover and Balances product (Intangible Assets)"
    _name = "ekd.balances.intangible_assets"
    _description =__doc__
    _inherits = {'ekd.balances.assets': 'assets'}

    assets = fields.Many2One('ekd.balances.assets', 'Assets', required=True,
            ondelete='CASCADE')
    period = fields.Many2One('ekd.period', 'Period', required=True, select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    party = fields.Many2One('party.party', 'Party Ref.', required=True,
                domain=[
                  ('employee', '=', True)
                ], select=2)
    qbalance = fields.Float('Quantity start balance', digits=(16, Eval('unit_digits', 2)))
    balance = fields.Numeric('Balances start period', digits=(16, Eval('currency_digits', 2)))
    qdebit = fields.Float('Quantity input turnover', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount input turnover', digits=(16, Eval('currency_digits', 2)))
    qcredit = fields.Float('Quantity revenue turnover', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount revenue turnover', digits=(16, Eval('currency_digits', 2)))
    qbalance_end = fields.Function(fields.Numeric('Quantity balance end period', digits=(16,2)), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('Balance end period', digits=(16,2)), 'get_balance_end')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductIntangible, self).__init__()

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency_digits(self):
        return 2

BalanceProductIntangible()

class BalanceSecurities(ModelSQL, ModelView):
    "Turnover and Balances Securities"
    _name = "ekd.balances.securities"
    _description =__doc__
    _inherits = {'ekd.balances.assets': 'assets'}

    assets = fields.Many2One('ekd.balances.assets', 'Assets', required=True,
            ondelete='CASCADE')

    period = fields.Many2One('ekd.period', 'Period', required=True, select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    party = fields.Many2One('party.party', 'Party Ref.', required=True,
                domain=[
                  ('employee', '=', True)
                ], select=2)
    product = fields.Many2One('product.product', 'Product Ref.', required=True, select=2)
    product_uom = fields.Many2One('product.uom', 'Unit Ref.', required=True, select=2)
    unit_price = fields.Numeric('Price input', digits=(16, Eval('currency_digits', 2)))
    qbalance = fields.Float('Quantity start balance', digits=(16, Eval('unit_digits', 2)))
    balance = fields.Numeric('Balances start period', digits=(16, Eval('currency_digits', 2)))
    qdebit = fields.Float('Quantity input turnover', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount input turnover', digits=(16, Eval('currency_digits', 2)))
    qcredit = fields.Float('Quantity revenue turnover', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount revenue turnover', digits=(16, Eval('currency_digits', 2)))
    qbalance_end = fields.Function(fields.Numeric('Quantity balance end period', digits=(16,2)), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('Balance end period', digits=(16,2)), 'get_balance_end')
    unit_digits = fields.Function(fields.Integer('Unit Digits', on_change_with=['product_uom']), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'),'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceSecurities, self).__init__()

    def default_state(self):
        return Transaction().context.get('state') or 'draft'

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency_digits(self):
        return 2

BalanceSecurities()

