# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты.
# Обороты по товарным счетам за период
##############################################################################
"Balances Analytic Accounting (Goods)"
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
# Аналитические счета по товарным счетам (Товарно-материальные ценности)
#
class BalanceProductGoods(ModelSQL, ModelView):
    "Turnover and Balances product (Goods)"
    _name = "ekd.balances.goods"
    _description =__doc__

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    period = fields.Function(fields.Many2One('ekd.period', 'Period'),'get_period')
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
    #periods = fields.One2Many('ekd.balances.goods.balance', 'goods', 'Periods')

    qbalance = fields.Function(fields.Float('Quantity Start', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_period')
    balance = fields.Function(fields.Numeric('Balances Start', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    qdebit = fields.Function(fields.Float('Quantity Income', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_period')
    debit = fields.Function(fields.Numeric('Amount Income', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    qcredit = fields.Function(fields.Float('Quantity Expense', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_period')
    credit = fields.Function(fields.Numeric('Amount Expense', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    qbalance_end = fields.Function(fields.Numeric('Quantity End', 
                        digits=(16, Eval('unit_digits', 2))), 'get_balance_period')
    balance_end = fields.Function(fields.Numeric('Balance End', 
                        digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    unit_digits = fields.Function(fields.Integer('Unit Digits', 
                        on_change_with=['product_uom']), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 
                        'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                        None, 'Ref entry debit lines'),'get_entry')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                        None, 'Ref entry credit lines'), 'get_entry')
    #balance_line = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
    #                    None, 'Lines Balance of Goods'), 'get_balance_line')
    balance_line = fields.One2Many('ekd.balances.goods.balance', 
                        'goods', 'Lines Balance of Goods')

    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State', required=True)
    active = fields.Boolean('Active')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductGoods, self).__init__()

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(1, ('party', 'ASC'))
        self._order.insert(2, ('department', 'ASC'))
        self._order.insert(3, ('product', 'ASC'))
        self._order.insert(4, ('product_uom', 'ASC'))

        self._sql_constraints += [
                ('balance_product_uniq', 'UNIQUE (account,department,party,product,product_uom)',\
              'account, department, party ,product, product_uom must be unique per analytic account period (Goods)!!')
                           ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceProductGoods, self).init(module_name)
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

    def get_period(self, ids, name):
        if not ids:
            return {}
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        if context.get('balance_period'):
            return {}.fromkeys(ids, context.get('balance_period'))
        elif context.get('start_date'):
            current_period = period_obj.search([
                    ('company','=',context.get('company')),
                    ('start_date','<=',context.get('start_date')),
                    ('end_date','>=',context.get('end_date')),
                    ], limit=1)
            return {}.fromkeys(ids, current_period)

        elif context.get('current_period'):
            return {}.fromkeys(ids, context.get('current_period'))

    #def get_balance_line(self, ids, name):
    #    if not ids:
    #        return {}
    #    res={}.fromkeys(ids, [])
    #    balance_goods_obj = self.pool.get('ekd.balances.goods.balance')
    #    period_obj = self.pool.get('ekd.period')
    #    context = Transaction().context
    #    if context.get('balance_period'):
    #        period_id = period_obj.browse(context.get('balance_period'))
    #        current_period = context.get('balance_period')
    #    elif context.get('start_date'):
    #        current_period = period_obj.search([
    #                ('company','=',context.get('company')),
    #                ('start_date','<=',context.get('start_date')),
    #                ('end_date','>=',context.get('end_date')),
    #                ], limit=1)
    #    elif context.get('current_period'):
    #        period_id = period_obj.browse(context.get('current_period'))
    #        current_period = context.get('current_period')
    #    for goods in self.browse(ids):
    #        res[goods.id] = balance_goods_obj.search([
    #                            ('account','=', goods.id)
    #                            ])
    #    return res

    def get_balance_period(self, ids, names):
        if not ids:
            return {}
        res={}
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        type_balance = self.browse(ids[0]).account.type_balance
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        #raise Exception(str(context))
        if context.get('balance_period'):
            period_id = period_obj.browse(context.get('balance_period'))
            current_period = context.get('balance_period')
        elif context.get('start_date'):
            current_period = period_obj.search([
                    ('company','=',context.get('company')),
                    ('start_date','<=',context.get('start_date')),
                    ('end_date','>=',context.get('end_date')),
                    ], limit=1)
        elif context.get('current_period'):
            period_id = period_obj.browse(context.get('current_period'))
            current_period = context.get('current_period')

        cr = Transaction().cursor
        cr.execute('SELECT y.goods, SUM(COALESCE(x.qbalance, 0)), SUM(COALESCE(x.balance, 0)), '\
                    'SUM(COALESCE(x.qdebit, 0)), SUM(COALESCE(x.debit, 0)), '\
                    'SUM(COALESCE(x.qcredit, 0)), SUM(COALESCE(x.credit, 0)), '\
                    'SUM(COALESCE(x.qbalance, 0)+COALESCE(x.qdebit, 0)-COALESCE(x.qcredit, 0)) as qbalance_end, '\
                    'SUM(COALESCE(x.balance, 0)+COALESCE(x.debit, 0)-COALESCE(x.credit, 0)) as balance_end '\
                    'FROM ekd_balances_goods_period y '\
                    'LEFT JOIN ekd_balances_goods_balance x ON y.id = x.period_product '\
                    'WHERE y.period=%s AND y.goods in ('%(current_period)+','.join(map(str,ids))+')'\
                    'GROUP BY y.goods')
        result =  cr.fetchall()
        #raise Exception(str(result))
        for account, qbalance, balance,\
            qdebit, debit, qcredit, credit,\
             qbalance_end, balance_end in result:
            # SQLite uses float for SUM
            if not isinstance(balance, Decimal):
                balance = Decimal(str(balance))
            if not isinstance(balance_end, Decimal):
                balance_end = Decimal(str(balance_end))
            if not isinstance(debit, Decimal):
                debit = Decimal(str(debit))
            if not isinstance(credit, Decimal):
                credit = Decimal(str(credit))
            if not isinstance(qbalance, Decimal):
                qbalance = Decimal(str(qbalance))
            if not isinstance(qbalance_end, Decimal):
                qbalance_end = Decimal(str(qbalance_end))
            if not isinstance(qdebit, Decimal):
                qdebit = Decimal(str(qdebit))
            if not isinstance(qcredit, Decimal):
                qcredit = Decimal(str(qcredit))
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(account, Decimal('0.0'))
                if name == 'qbalance_end':
                    res[name][account] = qbalance_end
                elif name == 'balance_end':
                    res[name][account] = balance_end
                elif name == 'qbalance':
                    res[name][account] = qbalance
                elif name == 'balance':
                    res[name][account] = balance
                elif name == 'debit':
                    res[name][account] = debit
                elif name == 'credit':
                    res[name][account] = credit
                elif name == 'qdebit':
                    res[name][account] = qdebit
                elif name == 'qcredit':
                    res[name][account] = qcredit
        return res

    def get_entry(self, ids, names):
        move_line = self.pool.get('ekd.account.move.line')
        move_line_analytic_dt = self.pool.get('ekd.account.move.line.analytic_dt')
        move_line_analytic_ct = self.pool.get('ekd.account.move.line.analytic_ct')
        res = {}
        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, [])
                if name == 'dt_line':
                    line_analytic_dt = move_line_analytic_dt.search([('ref_analytic','=', balance.id)])
                    for x in move_line_analytic_dt.read(line_analytic_dt, ['move_line']):
                        if x.get('move_line') not in res[name][balance.id]:
                            res[name][balance.id].append(x.get('move_line'))
                elif name == 'ct_line':
                    line_analytic_ct = move_line_analytic_ct.search([('ref_analytic','=', balance.id)])
                    for x in move_line_analytic_ct.read(line_analytic_ct, ['move_line']):
                        if x.get('move_line') not in res[name][balance.id]:
                            res[name][balance.id].append(x.get('move_line')) 
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

BalanceProductGoods()

class BalanceProductGoodsPeriod(ModelSQL, ModelView):
    "Turnover and Balances Goods (Period)"
    _name = "ekd.balances.goods.period"
    _description =__doc__
    _inherits = {'ekd.balances.goods': 'goods'}

    goods = fields.Many2One('ekd.balances.goods', 'Goods', 
                required=True, select=2, ondelete="CASCADE")
    period = fields.Many2One('ekd.period', 'Period', required=True, select=2, 
                domain=[
                    ('company','=',Eval('company'))
                ])
    period_state = fields.Function(fields.Char('Period State'), 'get_period_state')
    period_amounts = fields.One2Many('ekd.balances.goods.balance', 'period_product', 
                                'Turnover Goods in Period (Full)')

    '''
    balance_fixed = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
                                None, 'Turnover Goods in Period'),
                                'get_amount_fixed', setter='set_amount_fixed')
    balance_average = fields.Function(fields.Many2One('ekd.balances.goods.balance',
                                'Turnover Goods in Period'),
                                'get_amount_average', setter='set_amount_average')
    balance_fifo = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
                                None, 'Turnover Goods in Period'),
                                'get_amount_fifo', setter='set_amount_fifo')
    balance_lifo = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
                                None, 'Turnover Goods in Period'),
                                'get_amount_fifo', setter='set_amount_fifo')
    balance_date_income = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
                                None, 'Turnover Goods in Period'),
                                'get_amount_input', setter='set_amount_input')
    balance_partion = fields.Function(fields.One2Many('ekd.balances.goods.balance', 
                                None, 'Turnover Goods in Period'),
                                'get_amount_partion', setter='set_amount_partion')
    '''
    active = fields.Boolean('Active')
    state = fields.Function(fields.Char('State'), 'get_period_state')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductGoodsPeriod, self).__init__()

        self._sql_constraints += [
                ('period_uniq', 'UNIQUE (account,period)',\
                    'account, period must be unique per analytic account period (Goods)!')
                ]

    def default_active(self):
        return True

    def get_period_state(self, ids, name):
        res = {}
        for line_period in self.browse(ids):
            res[line_period.id] = line_period.period.state
        return res

    def get_amount_fifo(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ], order=[('date_income','DESC')])
        return res

    def set_amount_fifo(self, ids, name, vals):
        pass

    def get_amount_lifo(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids),
                            ], order=[('date_income','ASC')])
        return res

    def set_amount_lifo(self, ids, name, vals):
        pass

    def get_amount_input(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids),
                            ], order=[('date_income','ASC')])
        return res

    def set_amount_input(self, ids, name, vals):
        pass

    def get_amount_fixed(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ])
        return res

    def set_amount_fixed(self, ids, name, vals):
        pass

    def get_amount_partion(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
            res[amount_line.id] = amount_obj.search([
                            ('period_product','in', ids)
                            ])
        return res

    def set_amount_partion(self, ids, name, vals):
        pass

    def get_amount_average(self, ids, name):
        amount_obj = self.pool.get('ekd.balances.goods.balance')
        res = {}.fromkeys(ids, False)
        for amount_line in self.browse(ids):
                res[amount_line.id] = amount_obj.search([
                                    ('period_product','in', ids)
                                    ], limit=1)
        return res

    def set_amount_average(self, ids, name, vals):
        pass

BalanceProductGoodsPeriod()

class BalanceProductGoodsBalance(ModelSQL, ModelView):
    "Turnover and Balances Goods (Balance)"
    _name = "ekd.balances.goods.balance"
    _description =__doc__
    _inherits = {'ekd.balances.goods.period': 'period_product'}

    period_product = fields.Many2One('ekd.balances.goods.period', 'Goods', 
                        required=True, select=2, ondelete="CASCADE")
    # Партионный учет
    #partion = fields.Many2One('Partionny', digits=(16, Eval('currency_digits', 2)))
    # Для ФИФО, ЛИФО, Дата прихода,
    date_income = fields.Date('Date Income')
    # Для учетных цен
    unit_price = fields.Numeric('Price input', digits=(16, Eval('currency_digits', 2)))
    qbalance = fields.Float('Quantity Start', digits=(16, Eval('unit_digits', 2)))
    balance = fields.Numeric('Balances Start', digits=(16, Eval('currency_digits', 2)))
    qdebit = fields.Float('Quantity Income', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount Income', digits=(16, Eval('currency_digits', 2)))
    qcredit = fields.Float('Quantity Expense', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount Expense', digits=(16, Eval('currency_digits', 2)))
    qbalance_end = fields.Function(fields.Float('Quantity End',
                    digits=(16, Eval('unit_digits', 2))), 'get_balance_end')
    balance_end = fields.Function(fields.Numeric('Amount End', 
                    digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    unit_digits = fields.Function(fields.Integer('Unit Digits'), 'get_unit_digits')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                    None, 'Ref entry debit lines'),'get_entry')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', 
                    None, 'Ref entry credit lines'), 'get_entry')
    parent = fields.Many2One('ekd.balances.goods.balance','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.goods.balance','ID Transfer balance')
    active = fields.Boolean('Active')
    state = fields.Selection([
                ('draft','Draft'),
                ('open','Open'),
                ('done','Closed'),
                ('deleted','Deleted')
                ], 'State')
    deleted = fields.Boolean('Flag Deleting')

    def __init__(self):
        super(BalanceProductGoodsBalance, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceProductGoodsBalance, self).init(module_name)
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

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.period_product.goods.account.currency_digits
        return res

    def get_rec_name(self, ids, name):
        res = {}.fromkeys(ids, u'Пусто')
        for line in self.browse(ids):
            res[line.id] = line.period_product.goods.product.rec_name
        return res

    def get_unit_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.period_product.goods.product_uom.digits
        return res

    def get_entry(self, ids, name):
        move_line = self.pool.get('ekd.account.move.line')
        move_line_analytic_dt = self.pool.get('ekd.account.move.line.analytic_dt')
        move_line_analytic_ct = self.pool.get('ekd.account.move.line.analytic_ct')
        res = {}
        for balance in self.browse(ids):
            if name == 'dt_line':
                line_analytic_dt = move_line_analytic_dt.search([('ref_period','=', balance.id)])
                res[balance.id] = move_line_analytic_dt.read(line_analytic_dt, ['move_line'])
            elif name == 'ct_line':
                line_analytic_ct = move_line_analytic_ct.search([('ref_period','=', balance.id)])
                res[balance.id] = move_line_analytic_ct.read(line_analytic_ct, ['move_line'])
        return res

    def get_balance_end(self, ids, names):
        if not ids:
            return {}
        res={}
        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                if name == 'balance_end':
                    res[name][balance.id] = balance.balance-balance.credit+balance.debit
                elif name == 'qbalance_end':
                    res[name].setdefault(balance.id, 0.0)
                    res[name][balance.id] = Decimal(str(balance.qbalance+balance.qdebit-balance.qcredit))

        return res

BalanceProductGoodsBalance()

class BalanceProductGoodsAdd(ModelSQL, ModelView):
    _name = "ekd.balances.goods"

    curr_period = fields.Many2One('ekd.balances.goods.period', 'Current Period')
    last_period = fields.Many2One('ekd.balances.goods.period', 'Last Period')

BalanceProductGoodsAdd()

