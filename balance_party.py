# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты 
# 3. Тип счетов
# 3. Остатки по аналитическим счетам
##############################################################################
"Balances Analytic Accounting (Party)"
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
class BalanceAnalyticParty(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account"
    _name = "ekd.balances.party"
    _description =__doc__
    _rec_name = 'name_model'

    company = fields.Function(fields.Many2One('company.company', 'Company'), 'get_company')
    account = fields.Many2One('ekd.account', 'Account', required=True,  select=2,
                        order_field="account.code",
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    type_balance = fields.Function(fields.Char('Type Balance'), 'get_account_type')
    level = fields.Selection(_LEVEL_ANALYTIC, 'Level analityc', required=True)
    model_ref = fields.Reference('Analytic', selection='model_ref_get', select=2)
    name_model = fields.Function(fields.Char('Type', ), 'name_model_get')
    name_ref = fields.Function(fields.Char('Analytic Account', ), 'name_model_get')
    parent = fields.Many2One('ekd.balances.party', 'Parent Analytic')
    amount_periods = fields.One2Many('ekd.balances.party.period', 'account', 'Balances and Turnover (Full)')
    amount_years = fields.One2Many('ekd.balances.party.year', 'account', 'Balances and Turnover (Full)')
    childs = fields.One2Many('ekd.balances.party', 'parent', 'Children')
    balance = fields.Function(fields.Numeric('Start Balance',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_dt = fields.Function(fields.Numeric('Debit Start',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_ct = fields.Function(fields.Numeric('Credit Start',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    debit = fields.Function(fields.Numeric('Debit Turnover',
                digits=(16, Eval('currency_digits', 2)),), 'get_balance_period')
    credit = fields.Function(fields.Numeric('Credit Turnover',
                digits=(16, Eval('currency_digits', 2)),), 'get_balance_period')
    balance_end = fields.Function(fields.Numeric('End Balance',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_dt_end = fields.Function(fields.Numeric('Debit End',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    balance_ct_end = fields.Function(fields.Numeric('Credit End',
                digits=(16, Eval('currency_digits', 2))), 'get_balance_period')
    turnover_debit = fields.Function(fields.One2Many('ekd.account.move.line',
                None, 'Entries'), 'get_entry')
    turnover_credit = fields.Function(fields.One2Many('ekd.account.move.line',
                None,'Entries'), 'get_entry')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalanceAnalyticParty, self).__init__()

        self._order.insert(0, ('account', 'ASC'))
        self._order.insert(1, ('level', 'ASC'))
        self._order.insert(2, ('model_ref', 'ASC'))

        self._sql_constraints += [
                ('balance_account_uniq', 'UNIQUE(account,level,model_ref, parent)',\
                 'account, level, model_ref, parent - must be unique per balance!'),
                 ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalanceAnalyticParty, self).init(module_name)
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

    def get_company(self, ids, name):
        res={}
        context = Transaction().context
        res = {}.fromkeys(ids, context.get('company'))
        return res

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

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            if line.account.currency:
                res[line.id] = line.account.currency.digits or 2
            elif line.account.company:
                res[line.id] = line.account.company.currency.digits or 2
        return res

    def get_balance_period(self, ids, names):
        if not ids:
            return {}
        res={}
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        type_balance = self.browse(ids[0]).account.type_balance
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        if context.get('current_period'):
            period_id = period_obj.browse(context.get('current_period'))
            current_period = context.get('current_period')
        elif context.get('current_date'):
            current_period = period_obj.search([
                    ('company','=',context.get('company')),
                    ('start_date','<=',context.get('current_date')),
                    ('end_date','>=',context.get('current_date')),
                    ], limit=1)
        cr = Transaction().cursor
        cr.execute('SELECT id, account, balance_dt, balance_ct, '\
                    'debit, credit, '\
                    ' balance_dt-balance_ct+debit-credit as balance_end, '\
                    ' balance_dt+debit as balance_dt_end, '\
                    ' balance_ct+credit as balance_ct_end '\
                    'FROM ekd_balances_party_period '\
                    'WHERE period=%s AND account in ('%(current_period)+','.join(map(str,ids))+')')
        for amount_id, account, balance_dt, balance_ct,\
            debit, credit, balance_end,\
            balance_dt_end, balance_ct_end in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(balance_dt, Decimal):
                balance_dt = Decimal(str(balance_dt))
            if not isinstance(balance_ct, Decimal):
                balance_ct = Decimal(str(balance_ct))
            if not isinstance(balance_dt_end, Decimal):
                balance_dt = Decimal(str(balance_dt_end))
            if not isinstance(balance_ct_end, Decimal):
                balance_ct = Decimal(str(balance_ct_end))
            if not isinstance(debit, Decimal):
                debit = Decimal(str(debit))
            if not isinstance(credit, Decimal):
                credit = Decimal(str(credit))
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(account, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if name == 'balance_dt_end':
                    if type_balance == 'active':
                        res[name][account] = balance_end
                    #elif type_balance == 'passive':
                    #    res[name][account] = balance_end
                    elif type_balance == 'both':
                        if balance_end > 0:
                            res[name][account] = balance_end
                if name == 'balance_ct_end':
                    if type_balance == 'passive':
                        res[name][account] = -balance_end
                    elif type_balance == 'both':
                        if balance_end < 0:
                            res[name][account] = -balance_end
                elif name == 'balance_end':
                    res[name][account] = balance_end
                elif name == 'balance':
                    res[name][account] = balance_dt-balance_ct
                elif name == 'debit':
                    res[name][account] = debit
                elif name == 'credit':
                    res[name][account] = credit
        return res

    # This Function Test Only!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    def get_balance_year(self, ids, names):
        if not ids:
            return {}
        res={}
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        if context.get('current_period'):
            period_id = period_object.browse(context.get('current_period'))
            start_month = period_id.start_date.strftime('%m')
            end_month = period_id.end_date.strftime('%m')
            fiscalyear = period_id.fiscalyear.id
            if start_month == end_month:
                current_period = context.get('current_period').strftime('%m')
            else:
                begin_period = False
                for month in _MOUNTH:
                    if start_month == month:
                        current_period.append(month)
                        begin_period = True
                    elif begin_period:
                        current_period.append(month)
                    elif end_month == month:
                        current_period.append(month)
                        break
        else:
            if context.get('current_fiscalyear'):
                fiscalyear = context.get('current_fiscalyear')
            else:
                fiscalyear = fiscalyear_obj.search([
                                ('company','=',context.get('company')),
                                ('state','=','current')
                                ], limit=1)
            current_period = datetime.datetime.now().strftime('%m')

        if isinstance(current_period, list):
            field_debit = []
            field_credit = []
            for month in current_period:
                field_debit.append("debit_%s"%(month))
                field_credit.append("credit_%s"%(month))
            field_debits = []
            field_credits = []
            for month in _MOUNTH:
                if month == start_month:
                    break
                field_debits.append("debit_%s"%(month))
                field_credits.append("credit_%s"%(month))
        else:
            field_debit = "debit_%s"%(current_period)
            field_credit = "credit_%s"%(current_period)
            field_debits = []
            field_credits = []
            for month in _MOUNTH:
                if month == current_period:
                    break
                field_debits.append("debit_%s"%(month))
                field_credits.append("credit_%s"%(month))

        cr = Transaction().cursor
        if isinstance(current_period, list):
            cr.execute('SELECT id, balance_dt+'+'+'.join(field_debits)+','\
                    'balance_ct+'+'+'.join(field_credits)+','\
                    '+'.join(field_debit)+' as debit,'\
                    '+'.join(field_credit)+' as credit'\
                    'FROM ekd_balances_party_period'\
                    'WHERE fiscalyear=%s AND account in ('+','.join(map(str,ids))+')'%(field_debit,field_credit,fiscalyear))
        else:
            cr.execute('SELECT id, balance_dt+'+'+'.join(field_debits)+','\
                    'balance_ct+'+'+'.join(field_credits)+','\
                    '%s, %s'\
                    'FROM ekd_balances_party_period'\
                    'WHERE fiscalyear=%s AND account in ('+','.join(map(str,ids))+')'%(field_debit,field_credit,fiscalyear))

        for id, balance_dt, balance_ct, debit, credit in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(balance_dt, Decimal):
                balance_dt = Decimal(str(balance_dt))
            if not isinstance(balance_ct, Decimal):
                balance_ct = Decimal(str(balance_ct))
            if not isinstance(debit, Decimal):
                debit = Decimal(str(debit))
            if not isinstance(credit, Decimal):
                credit = Decimal(str(credit))
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, Decimal('0.0'))
                amount_balance= Decimal('0.0')
                if not balance.amount:
                    continue
                if name == 'balance_dt_end':
                    res[name][balance.id] = balance_end
                elif name == 'balance_ct_end':
                    res[name][balance.id] = balance_end
                elif name == 'balance_end':
                    res[name][balance.id] = balance_end 
                elif name == 'balance':
                    res[name][balance.id] = balance_dt-balance_ct
                elif name == 'debit':
                    res[name][balance.id] = debit
                elif name == 'credit':
                    res[name][balance.id] = credit

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

BalanceAnalyticParty()

class BalancePartyPeriod(ModelSQL, ModelView):
    "Turnover and Balances parties (Period)"
    _name = "ekd.balances.party.period"
    _description =__doc__
    _order_name = 'period.end_date'

    def get_balance_end(self, ids, names):
        if not ids:
            return {}
        res={}
        for balance in self.browse(ids):
            type_balance = balance.account.type_balance
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(balance.id, Decimal('0.0'))
                amount = balance.balance_dt-balance.balance_ct+balance.debit-balance.credit
                if name == 'balance_end':
                    res[name][balance.id] = amount
                elif name == 'balance':
                    res[name][balance.id] = balance.balance_dt-balance.balance_ct
                elif name == 'balance_dt_end':
                    if type_balance == 'active' or (type_balance == 'both' and amount > 0):
                        res[name][balance.id] = amount
                elif name == 'balance_ct_end':
                    if type_balance == 'passive' or (type_balance == 'both' and amount < 0):
                        res[name][balance.id] = -amount

        return res

    account = fields.Many2One('ekd.balances.party', 'Analytic Account', required=True,  select=2, ondelete="CASCADE")
    period = fields.Many2One('ekd.period', 'Period', select=2, 
                    domain=[
                        ('company','=',Eval('company'))
                    ],)
    balance_dt = fields.Numeric('Debit Start', digits=(16, Eval('currency_digits', 2)))
    balance_ct = fields.Numeric('Credit Start', digits=(16, Eval('currency_digits', 2)))
    debit = fields.Numeric('Debit Turnover', digits=(16, Eval('currency_digits', 2)))
    credit = fields.Numeric('Credit Turnover', digits=(16, Eval('currency_digits', 2)))
    balance_end_dt = fields.Numeric('Debit End', digits=(16, Eval('currency_digits', 2)))
    balance_end_ct = fields.Numeric('Credit End', digits=(16, Eval('currency_digits', 2)))
    balance_dt_end = fields.Function(fields.Numeric('Debit End', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    balance_ct_end = fields.Function(fields.Numeric('Credit End', 
                digits=(16, Eval('currency_digits', 2))), 'get_balance_end')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'currency_digits_get')
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
    parent = fields.Many2One('ekd.balances.party.period','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.party.period','ID Transfer balance')
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalancePartyPeriod, self).__init__()

        self._order.insert(0, ('period', 'DESC'))

        self._sql_constraints += [
                 ('balance_party_uniq', 'UNIQUE(account,period)',\
              'period, account - must be unique per balance!'),
                          ]

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalancePartyPeriod, self).init(module_name)
        table = TableHandler(cursor, self, module_name)
        # Проверяем счетчик
        cursor.execute("SELECT last_value, increment_by FROM %s"%table.sequence_name)
        last_value, increment_by = cursor.fetchall()[0]

        # Устанавливаем счетчик
        if str(last_value)[len(str(last_value))-1] != str(_ID_TABLES_BALANCES_PERIOD[self._table]):
            cursor.execute("SELECT setval('"+table.sequence_name+"', %s, true)"%_ID_TABLES_BALANCES_PERIOD[self._table])
        if increment_by != 10:
            cursor.execute("ALTER SEQUENCE "+table.sequence_name+" INCREMENT 10")

    def default_currency_digits(self):
        return 2

    def default_active(self):
        return True

    def default_state(self):
        return 'draft'

    def currency_digits_get(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for line in self.browse(ids):
            if line.account.account.currency:
                res[line.id] = line.account.account.currency.digits or 2
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

    def set_entries_field(self, id, name, value):
        assert name in ('dt_line', 'ct_line', 'lines'), 'Invalid name'
        return

    def search_domain(self, domain, active_test=True):
        domain_new=[]
        if domain[0] == 'AND':
            for (left_val, center_val, rigth_val) in domain[1]:
                if left_val == 'period.start_date':
                    rigth_val = datetime.datetime.now()
                elif left_val == 'period.end_date':
                    rigth_val = datetime.datetime.now()
                domain_new.append((left_val, center_val, rigth_val))
        else:
            for (left_val, center_val, rigth_val) in domain:
                if left_val == 'period.start_date':
                    rigth_val = datetime.datetime.now()
                elif left_val == 'period.end_date':
                    rigth_val = datetime.datetime.now()
                domain_new.append((left_val, center_val, rigth_val))
        return super(BalancePartyPeriod, self).search_domain(domain_new, active_test=active_test)

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
                if balance_line.balance_dt_end or balance_line.balance_ct_end:
                    if balance_line.transfer:
                        self.transfer_balance(balance_line.transfer.id, {
                                    'balance_dt': balance_line.balance_dt_end,
                                    'balance_ct': balance_line.balance_ct_end,
                                    })
                    else:
                        balance_new_id = self.search([
                            ('period','=',period),
                            ('account','=',vals.get('account')),
                            ('party','=',balance_line.party.id),
                            ('model_ref','=',balance_line.model_ref),
                            ])
                        if balance_new_id:
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
                                            'party': balance_line.party.id,
                                            'model_ref': balance_line.model_ref,
                                            'balance_dt': balance_line.balance_dt_end,
                                            'balance_ct': balance_line.balance_ct_end,
                                            })
                                    })

            balance_ids = self.search([
                                ('period','=',period),
                                ('account','=', vals.get('account')),
                                ])

        return True

BalancePartyPeriod()

#
# Остатки и обороты по аналитическим счетам
#
class BalancePartyYear(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account Parties - FiscalYear"
    _name = "ekd.balances.party.year"
    _description =__doc__

    account = fields.Many2One('ekd.balances.party', 'Analytic Account', required=True,  select=2, ondelete="CASCADE")
    fiscalyear = fields.Many2One('ekd.fiscalyear', 'FiscalYear', required=True)
    balance = fields.Numeric('Debit Start', digits=(16, Eval('currency_digits', 2)),)
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
    dt_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry debit lines'), 'get_entries_field')
    ct_line = fields.Function(fields.One2Many('ekd.account.move.line', None, 'Ref entry credit lines'), 'get_entries_field')
    parent = fields.Many2One('ekd.balances.party.year','ID Parent balance')
    transfer = fields.Many2One('ekd.balances.party.year','ID Transfer balance')
    state = fields.Selection([
                 ('draft','Draft'),
                 ('open','Open'),
                 ('done','Closed'),
                 ('deleted','Deleted')
                 ], 'State', required=True)
    deleted = fields.Boolean('Flag Deleting')
    active = fields.Boolean('Active')

    def __init__(self):
        super(BalancePartyYear, self).__init__()

    def init(self, module_name):
        cursor = Transaction().cursor
        super(BalancePartyYear, self).init(module_name)
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
            res.setdefault('currency_digits', {})
            res['currency_digits'][line.id] = line.account.currency_digits or 2
        return res

BalancePartyYear()

class BalanceAnalyticPartyAdd(ModelSQL, ModelView):
    "Turnover and Balances Analytic Account"
    _name = "ekd.balances.party"

    curr_period = fields.Many2One('ekd.balances.party.period', 'account', 
                'Balances and Turnover (Current Period)')
    last_period = fields.Many2One('ekd.balances.party.period', 'account', 
                'Balances and Turnover (Last Period)')
    amount_year = fields.Many2One('ekd.balances.party.year', 'account', 
                'Balances and Turnover (Current FiscalYear)')

BalanceAnalyticPartyAdd()

