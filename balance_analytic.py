# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты 
# 3. Тип счетов
# 3. Остатки по аналитическим счетам
##############################################################################
"Balances Analytic Accounting"
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.backend import TableHandler
from trytond.tools import safe_eval
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import Equal, Eval, Not, In
from account import _PARTY, _PRODUCT, _MONEY, _LEVEL_ANALYTIC
from balance_account import _ID_TABLES_BALANCES, _ID_TABLES_BALANCES_PERIOD
import datetime

_BALANCE_STATES = {
        'readonly': In(Eval('state'), ['draft', 'done']),
                }
_BALANCE_DEPENDS = ['state']

_MOUNTH=['01','02','03','04','05','06','07','08','09','10','11','12',]

_QUARTER={
'1': ['01','02','03',],
'2': ['04','05','06',],
'3': ['07','08','09',],
'4': ['10','11','12',],
}

_SIDE=['debit_','credit_']

#
# Дерево аналитических счетов
#
class BalanceAnalyticAccount(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account"
    _name = "ekd.balances.analytic"
    _description =__doc__
    _rec_name = 'name_model'

    account = fields.Many2One('ekd.account', 'Account', required=True,  select=2,
                        order_field="account.code",
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    level = fields.Selection(_LEVEL_ANALYTIC, 'Level analityc', required=True)
    model_ref = fields.Reference('Analytic', selection='model_ref_get', select=2)
    name_model = fields.Function(fields.Char('Name Analytic Account', ), 'name_model_get')
    name_ref = fields.Function(fields.Char('Name Analytic Account', ), 'name_model_get')
    parent = fields.Many2One('ekd.balances.analytic', 'Parent Analytic')
    amount_periods = fields.One2Many('ekd.balances.analytic.period', 'account', 'Balances and Turnover Analytic (Full)')
    childs = fields.One2Many('ekd.balances.analytic', 'parent', 'Children')
    balance = fields.Function(fields.Numeric('Start Balance', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_qty = fields.Function(fields.Float('Start Quantity', 
                digits=(16, Eval('unit_digits', 2)),), 'get_balance_period')
    debit = fields.Function(fields.Numeric('Debit Turnover', 
                digits=(16, Eval('currency_digits', 2)),), 'get_balance_period')
    debit_qty = fields.Function(fields.Float('Quantity Income', 
                digits=(16, Eval('unit_digits', 2)),), 'get_balance_period')
    credit = fields.Function(fields.Numeric('Credit Turnover', 
                digits=(16, Eval('currency_digits', 2)),), 'get_balance_period')
    credit_qty = fields.Function(fields.Float('Quantity Expense',
                digits=(16, Eval('unit_digits', 2)),), 'get_balance_period')
    balance_end = fields.Function(fields.Numeric('End Balance', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_qty_end = fields.Function(fields.Float('End Quantity', 
                digits=(16, Eval('unit_digits', 2)),), 'get_balance_period')
    turnover_debit = fields.Function(fields.One2Many('ekd.account.move.line', 
                None, 'Entryies'), 'get_entry')
    turnover_credit = fields.Function(fields.One2Many('ekd.account.move.line', 
                None,'Entryies'), 'get_entry')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    unit_digits = fields.Function(fields.Integer('Currency Digits'), 'get_unit_digits')
    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAnalyticAccount, self).__init__()

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(1, ('level', 'ASC'))
        self._order.insert(2, ('model_ref', 'ASC'))

        self._sql_constraints += [
                ('balance_account_uniq', 'UNIQUE(account,level,model_ref)',\
                 'account, level, model_ref - must be unique per balance!'),
                 ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAnalyticAccount, self).init(module_name)
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

    def default_currency(self):
        return Transaction().context.get('currency')

    def default_active(self):
        return True

    def model_ref_get(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.level_analytic'),
                    ('pole', '=', 'type_analytic'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def name_model_get(self, ids, names):
        group_model={}
        group_name_model={}
        res={}
        res['name_model']={}.fromkeys(ids, False)
        res['name_ref']={}.fromkeys(ids, False)
        tmp_res={}
        for line in self.browse(ids):
            res['name_model'][line.id] = line.model_ref
            if line.model_ref not in tmp_res.keys():
                tmp_res[line.model_ref] = [line.id,]
            else:
                tmp_res[line.model_ref].append(line.id)
            ref_model, ref_id = line.model_ref.split(',',1)
            if ref_id == '0':
                continue
            if ref_model not in group_model.keys():
                group_model[ref_model] = [int(ref_id),]
            else:
                group_model[ref_model].append(int(ref_id))
        ir_model_obj = self.pool.get('ir.model')
        search_model_ids = ir_model_obj.search([('model','in',group_model.keys())])
        for ir_model_id in ir_model_obj.browse(search_model_ids):
            group_name_model[ir_model_id.model] = ir_model_id.rec_name
        for model in group_model.keys():
            model_obj = self.pool.get(model)
            for model_line in model_obj.browse(group_model[model]):
                rec_id = tmp_res['%s,%s'%(model,str(model_line.id))]
                if isinstance(rec_id, (int,long)):
                    res['name_model'][rec_id] = group_name_model[model]
                    res['name_ref'][rec_id] = model_line.rec_name
                else:
                    for rec_id_ in rec_id: 
                        res['name_model'][rec_id_] = group_name_model[model]
                        res['name_ref'][rec_id_ ] = model_line.rec_name
        return res

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.account.currency.currency_digits or 2
        return res

    def get_unit_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        #for line in self.browse(ids):
        #    res[line.id] = line.currency.currency_digits or 2
        return res

    def get_entry(self, ids, names):
        move_line = self.pool.get('ekd.account.move.line')
        move_line_analytic_dt = self.pool.get('ekd.account.move.line.analytic_dt')
        move_line_analytic_ct = self.pool.get('ekd.account.move.line.analytic_ct')
        res = {}
        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                if name == 'turnover_debit':
                    line_analytic_dt = move_line_analytic_dt.search([('ref_analytic','=', balance.id)])
                    res[name][balance.id] = [ x.get('move_line') for x in move_line_analytic_dt.read(line_analytic_dt, ['move_line']) ]
                elif name == 'turnover_credit':
                    line_analytic_ct = move_line_analytic_ct.search([('ref_analytic','=', balance.id)])
                    res[name][balance.id] = [ x.get('move_line') for x in move_line_analytic_ct.read(line_analytic_ct, ['move_line']) ]
        return res

    def get_balance_period(self, ids, names):
        if not ids:
            return {}
        res={}
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context.get('current_period'):
            period = period_obj.browse(context.get('current_period'))
        cr = Transaction().cursor
        #raise Exception(','.join(map(str,ids)))
        cr.execute('SELECT id, account, balance, balance_quantity, '\
                    'debit, debit_quantity, '\
                    'credit, credit_quantity, '\
                    ' balance+debit-credit as balance_end, '\
                    ' balance_quantity+debit_quantity-credit_quantity as balance_quantity_end '\
                    'FROM ekd_balances_analytic_period '\
                    'WHERE period=%s AND account in (%s)'%(period.id, ','.join(map(str,ids))))
        for amount_id, account, balance, balance_quantity, debit, debit_quantity,\
                 credit, credit_quantity, \
                 balance_end, balance_quantity_end in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(balance, Decimal):
                balance = Decimal(str(balance))
            if not isinstance(balance_end, Decimal):
                balance_end = Decimal(str(balance_end))
            if not isinstance(debit, Decimal):
                debit = Decimal(str(debit))
            if not isinstance(credit, Decimal):
                credit = Decimal(str(credit))
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(account, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if name == 'balance_end':
                    res[name][account] = balance_end
                elif name == 'balance_qty_end':
                    res[name][account] = balance_quantity_end
                elif name == 'balance_qty':
                    res[name][account] = balance_quantity
                elif name == 'balance':
                    res[name][account] = balance
                elif name == 'debit':
                    res[name][account] = debit
                elif name == 'credit':
                    res[name][account] = credit
                elif name == 'debit_qty':
                    res[name][account] = debit_quantity
                elif name == 'credit_qty':
                    res[name][account] = credit_quantity
        return res

    # This Function for test only !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def get_balance_year(self, ids, names):
        if not ids:
            return {}
        res={}
        context = Transaction().context
        current_period = datetime.datetime.now().strftime('%m')
        field_debit = "debit_%s"%(current_period)
        field_credit = "credit_%s"%(current_period)
        month_compute=[]
        for month in _MOUNTH:
            if month == current_period:
                break
            month_compute.append(month)
        for balance in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if not balance.amount:
                    continue
                if name == 'balance_end':
                    res[name][balance.id] = balance.amount['balance']
                    for month in month_compute:
                        res[name][balance.id] += balance.amount["debit_%s"%(month)]-\
                                                balance.amount["credit_%s"%(month)]
                    res[name][balance.id] +=    balance.amount[field_debit]-\
                                                balance.amount[field_credit]

                elif name == 'balance':
                    res[name][balance.id] = balance.amount.balance
                    if len(month_compute) != 1:
                        for month in month_compute:
                            res[name][balance.id] += balance.amount["debit_%s"%(month)]-\
                                                     balance.amount["credit_%s"%(month)]
                elif name == 'debit':
                    res[name][balance.id] = balance.amount[field_debit]
                elif name == 'credit':
                    res[name][balance.id] = balance.amount[field_credit]

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

BalanceAnalyticAccount()

class BalanceAnalyticPeriod(ModelSQL, ModelView):
    "Turnover and Balances analytic accounts (Period)"
    _name = "ekd.balances.analytic.period"
    _description =__doc__

    def get_balance(self, ids, names):
        if not ids:
            return {}
        cr = Transaction().cursor
        cr.execute('select id, COALESCE(balance, 0)+COALESCE(debit, 0)-COALESCE(credit, 0) as balance_end, '\
                    'COALESCE(balance_quantity, 0)+COALESCE(debit_quantity, 0)-COALESCE(credit_quantity, 0) '\
                    'as balance_quantity_end from ekd_balances_analytic where id in ('+','.join(map(str,ids))+')')
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

    account = fields.Many2One('ekd.balances.analytic', 'Analytic Account', required=True,  select=2,)
    period = fields.Many2One('ekd.period', 'Period')
    uom = fields.Many2One('product.uom', 'UoM', select=2,)
    unit_digits = fields.Function(fields.Integer('Unit Digits'), 'get_unit_digits')
    balance = fields.Numeric('Start Balance', digits=(16, Eval('currency_digits', 2)))
    balance_quantity = fields.Float('Start Quantity', digits=(16, Eval('unit_digits', 2)))
    debit = fields.Numeric('Amount debit turnover', digits=(16, Eval('currency_digits', 2)))
    debit_quantity = fields.Float('Quantity income', digits=(16, Eval('unit_digits', 2)))
    credit = fields.Numeric('Amount credit turnover', digits=(16, Eval('currency_digits', 2)))
    credit_quantity = fields.Float('Quantity expense', digits=(16, Eval('unit_digits', 2)))
    balance_end = fields.Function(fields.Numeric('End Balance', 
            digits=(16, Eval('currency_digits', 2))), 'get_balance')
    balance_quantity_end = fields.Function(fields.Float('End Balance', 
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
    parent = fields.Many2One('ekd.balances.analytic.period','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.analytic.period','ID Transfer balance')
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAnalyticPeriod, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAnalyticPeriod, self).init(module_name)
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

BalanceAnalyticPeriod()

#
# Остатки и обороты по аналитическим счетам
#
class BalanceAnalyticYear(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account (FiscalYear)"
    _name = "ekd.balances.analytic.year"
    _description =__doc__

    account = fields.Many2One('ekd.balances.analytic', 'Analytic Account', required=True,  select=2,)
    fiscalyear = fields.Many2One('ekd.fiscalyear', 'FiscalYear', required=True)
    unit_price = fields.Numeric('Unit Price', digits=(16, Eval('currency_digits', 2)),)
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    uom = fields.Many2One('product.uom', 'UoM', required=True,  select=2,)
    unit_digits = fields.Function(fields.Integer('Unit Digits'), 'get_unit_digits')
    balance = fields.Numeric('Debit Start', digits=(16, Eval('currency_digits', 2)),)
    balance_quantity = fields.Float('Debit Start', digits=(16, Eval('currency_digits', 2)),)
    debit_01 = fields.Numeric('Debit Turnover 01', digits=(16, Eval('currency_digits', 2)),)
    credit_01 = fields.Numeric('Credit Turnover 01', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_01 = fields.Float('Debit Turnover 01', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_01 = fields.Float('Credit Turnover 01', digits=(16, Eval('unit_digits', 2)),)
    debit_02 = fields.Numeric('Debit Turnover 02', digits=(16, Eval('currency_digits', 2)),)
    credit_02 = fields.Numeric('Credit Turnover 02', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_02 = fields.Float('Debit Turnover 02', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_02 = fields.Float('Credit Turnover 02', digits=(16, Eval('unit_digits', 2)),)
    debit_03 = fields.Numeric('Debit Turnover 03', digits=(16, Eval('currency_digits', 2)),)
    credit_03 = fields.Numeric('Credit Turnover 03', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_03 = fields.Float('Debit Turnover 03', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_03 = fields.Float('Credit Turnover 03', digits=(16, Eval('unit_digits', 2)),)
    debit_04 = fields.Numeric('Debit Turnover 04', digits=(16, Eval('currency_digits', 2)),)
    credit_04 = fields.Numeric('Credit Turnover 04', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_04 = fields.Float('Debit Turnover 04', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_04 = fields.Float('Credit Turnover 04', digits=(16, Eval('unit_digits', 2)),)
    debit_05 = fields.Numeric('Debit Turnover 05', digits=(16, Eval('currency_digits', 2)),)
    credit_05 = fields.Numeric('Credit Turnover 05', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_05 = fields.Float('Debit Turnover 05', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_05 = fields.Float('Credit Turnover 05', digits=(16, Eval('unit_digits', 2)),)
    debit_06 = fields.Numeric('Debit Turnover 06', digits=(16, Eval('currency_digits', 2)),)
    credit_06 = fields.Numeric('Credit Turnover 06', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_06 = fields.Float('Debit Turnover 06', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_06 = fields.Float('Credit Turnover 06', digits=(16, Eval('unit_digits', 2)),)
    debit_07 = fields.Numeric('Debit Turnover 07', digits=(16, Eval('currency_digits', 2)),)
    credit_07 = fields.Numeric('Credit Turnover 07', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_07 = fields.Float('Debit Turnover 07', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_07 = fields.Float('Credit Turnover 07', digits=(16, Eval('unit_digits', 2)),)
    debit_08 = fields.Numeric('Debit Turnover 08', digits=(16, Eval('currency_digits', 2)),)
    credit_08 = fields.Numeric('Credit Turnover 08', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_08 = fields.Float('Debit Turnover 08', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_08 = fields.Float('Credit Turnover 08', digits=(16, Eval('unit_digits', 2)),)
    debit_09 = fields.Numeric('Debit Turnover 09', digits=(16, Eval('currency_digits', 2)),)
    credit_09 = fields.Numeric('Credit Turnover 09', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_09 = fields.Float('Debit Turnover 09', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_09 = fields.Float('Credit Turnover 09', digits=(16, Eval('unit_digits', 2)),)
    debit_10 = fields.Numeric('Debit Turnover 10', digits=(16, Eval('currency_digits', 2)),)
    credit_10 = fields.Numeric('Credit Turnover 10', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_10 = fields.Float('Debit Turnover 10', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_10 = fields.Float('Credit Turnover 10', digits=(16, Eval('unit_digits', 2)),)
    debit_11 = fields.Numeric('Debit Turnover 11', digits=(16, Eval('currency_digits', 2)),)
    credit_11 = fields.Numeric('Credit Turnover 11', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_11 = fields.Float('Debit Turnover 11', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_11 = fields.Float('Credit Turnover 11', digits=(16, Eval('unit_digits', 2)),)
    debit_12 = fields.Numeric('Debit Turnover 12', digits=(16, Eval('currency_digits', 2)),)
    credit_12 = fields.Numeric('Credit Turnover 12', digits=(16, Eval('currency_digits', 2)),)
    debit_quantity_12 = fields.Float('Debit Turnover 12', digits=(16, Eval('unit_digits', 2)),)
    credit_quantity_12 = fields.Float('Credit Turnover 12', digits=(16, Eval('unit_digits', 2)),)
    #dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'), 'get_entries_field')
    #ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    parent = fields.Many2One('ekd.balances.analytic.year','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.analytic.year','ID Transfer balance')
    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAnalyticYear, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAnalyticYear, self).init(module_name)
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

    def default_active(self):
        return True

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.account.currency_digits or 2
        return res

    def get_unit_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            res[line.id] = line.account.currency_digits
        return res

BalanceAnalyticYear()

class BalanceAnalyticAdd(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account"
    _name = "ekd.balances.analytic"

    curr_period = fields.Many2One('ekd.balances.analytic.period', 'Balances and Turnover  Analytic (Current Period)')
    last_period = fields.Many2One('ekd.balances.analytic.period', 'Balances and Turnover  Analytic (Last Period)')

BalanceAnalyticAdd()
