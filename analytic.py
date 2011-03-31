# -*- encoding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Analytic Account"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.pyson import Equal, Eval, Not, In, PYSONEncoder
from account import _LEVEL_ANALYTIC, _PARTY, _PRODUCT, _DEPRECATION, _MONEY, _OTHER
from decimal import Decimal
import copy

class AnalyticAccountTemplate(ModelSQL, ModelView):
    'Analytic Account Template'
    _name = 'ekd.account.analytic.template'
    _description = __doc__

    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', select=1)
    full_code = fields.Function(fields.Char('Full Code', select=1), 'get_full_code')
    full_name = fields.Function(fields.Char('Full name', select=1), 'get_full_name')
    active = fields.Boolean('Active', select=2)
    level = fields.Integer('Level Analysts', select=1)
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('consolidation', 'Consolidation'),
        ], 'Type Struct', required=True)

    kind_analytic = fields.Selection([
        ('cost', 'Cost'),
        ('cash_flow_income', 'Cash Flow (Income)'),
        ('cash_flow_expense', 'Cash Flow (Expense)'),
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('expense_future', 'Expense future period'),
        ('income_future', 'Incomes future period'),
        ('type_business', 'Type Business'),
        ('type_payment_budget', 'Types of payments to the budget'),
        ], 'Kind analityc', states={
                'invisible': Not(Equal(Eval('type'), 'root')),
                'required': Equal(Eval('type'), 'root'),
        })

    root = fields.Many2One('ekd.account.analytic.template', 'Root', select=2,
            domain=[('parent', '=', False)],
            states={
                'invisible': Equal(Eval('type'), 'root'),
                'required': Not(Equal(Eval('type'), 'root')),
            })
    parent = fields.Many2One('ekd.account.analytic.template', 'Parent', select=2,
            domain=[('parent', 'child_of', Eval('root'))],
            states={
                'invisible': Equal(Eval('type'), 'root'),
                'required': Not(Equal(Eval('type'), 'root')),
            })
    childs = fields.One2Many('ekd.account.analytic.template', 'parent', 'Children')
    #child_consol_ids =  fields.Many2Many('ekd.account.analytic.consoledate', 'parent', 'child', 'Consolidated Children')
    note = fields.Text('Note')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)

    def __init__(self):
        super(AnalyticAccountTemplate, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_active(self):
        return True

    def default_type(self):
        return 'normal'

    def default_state(self):
        return 'draft'

    def default_display_balance(self):
        return 'credit-debit'

    def default_mandatory(self):
        return False

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for account in self.browse(ids):
            if account.code:
                res[account.id] = account.code + ' - ' + unicode(account.name)
            else:
                res[account.id] = unicode(account.name)
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        else:
            return [(self._rec_name,) + clause[1:]]

    def get_full_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(category):
            if category.id in res:
                return res[category.id]
            elif category.parent:
                return _name(category.parent) + '/' + category.name
            else:
                return category.name
        for category in self.browse(ids):
            res[category.id] = _name(category)
        return res

    def get_full_code(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(account):
            if account.id in res:
                return res[account.id]
            elif account.parent:
                return _name(account.parent) + '.' + account.code
            else:
                return account.code
        for account in self.browse(ids):
            res[account.id] = _name(account)
        return res

AnalyticAccountTemplate()

class AnalyticAccount(ModelSQL, ModelView):
    'Analytic Account'
    _name = 'ekd.account.analytic'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company')
    model_ref = fields.Reference('Reference To', selection='get_model_ref', select=1)
    name = fields.Char('Name', required=True, select=1)
    code = fields.Char('Code', select=1)
    full_code = fields.Function(fields.Char('Full Code', select=1), 'get_full_code')
    full_name = fields.Function(fields.Char('Full name', select=1), 'get_full_name')
    active = fields.Boolean('Active', select=2)
    level = fields.Integer('Level Analysts', select=1)
    party = fields.Many2One('party.party', 'Party')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits', on_change_with=['currency']), 'get_currency_digits')
    type = fields.Selection([
        ('root', 'Root'),
        ('view', 'View'),
        ('normal', 'Normal'),
        ('consolidation', 'Consolidation'),
        ], 'Type Struct', required=True)

    kind_analytic = fields.Selection([
        ('cost', 'Cost'),
        ('cash_flow', 'Cash Flow'),
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('expense_future', 'Expense future period'),
        ('income_future', 'Incomes future period'),
        ('type_business', 'Type Business'),
        ('type_payment_budget', 'Types of payments to the budget'),
        ], 'Kind analityc', states={
                'invisible': Not(In(Eval('type'), ['root','view'])),
                'required': In(Eval('type'), ['root','view']),
        })

    root = fields.Many2One('ekd.account.analytic', 'Root', select=2,
            domain=[('parent', '=', False)],
            states={
                'invisible': Equal(Eval('type'), 'root'),
                'required': Not(Equal(Eval('type'), 'root')),
            })
    parent = fields.Many2One('ekd.account.analytic', 'Parent', select=2,
            domain=[('parent', 'child_of', Eval('root'))],
            states={
                'invisible': Equal(Eval('type'), 'root'),
                'required': Not(Equal(Eval('type'), 'root')),
            })
    childs = fields.One2Many('ekd.account.analytic', 'parent', 'Children')
    child_consol_ids =  fields.Many2Many('ekd.account.analytic.consoledate', 'parent', 'child', 'Consolidated Children')
#    balance = fields.Function('get_balance', digits=(16, Eval('currency_digits', 2)),
#            string='Balance')
#    credit = fields.Function('get_credit_debit', digits=(16, Eval('currency_digits', 2)),
#            string='Credit')
#    debit = fields.Function('get_credit_debit', digits=(16, Eval('currency_digits', 2)),
#            string='Debit')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True)
    note = fields.Text('Note')
    display_balance = fields.Selection([
        ('debit-credit', 'Debit - Credit'),
        ('credit-debit', 'Credit - Debit'),
        ], 'Display Balance', required=True)
    mandatory = fields.Boolean('Mandatory', states={
        'invisible': Not(Equal(Eval('type'), 'root')),
        })

    def __init__(self):
        super(AnalyticAccount, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_active(self):
        return True

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency(self):
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('currency.currency')
        context = Transaction().context
        if context.get('company'):
            company = company_obj.browse( context['company'])
            return company.currency.id
        return False

    def default_type(self):
        return 'normal'

    def default_state(self):
        return 'draft'

    def default_display_balance(self):
        return 'credit-debit'

    def default_mandatory(self):
        return False

    def on_change_with_currency_digits(self, vals):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse( vals['currency'])
            return currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for account in self.browse(ids):
            res[account.id] = account.currency.digits
        return res

    def get_balance(self, ids, names):
        res = {}
        for name in names:
            res.setdefault(name, {})
            for account_id in ids:
                res[name][account_id] = Decimal('0.0')
        return res

    def get_credit_debit(self, ids, names):
        res = {}
        for name in names:
            res.setdefault(name, {})
            for account_id in ids:
                res[name][account_id] = Decimal('0.0')
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for account in self.browse(ids):
            if account.code:
                res[account.id] = account.code + ' - ' + unicode(account.name)
            else:
                res[account.id] = unicode(account.name)
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        else:
            return [(self._rec_name,) + clause[1:]]

    def get_full_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(category):
            if category.id in res:
                return res[category.id]
            elif category.parent:
                return _name(category.parent) + '/' + category.name
            else:
                return category.name
        for category in self.browse(ids):
            res[category.id] = _name(category)
        return res

    def get_full_code(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(account):
            if account.id in res:
                return res[account.id]
            elif account.parent:
                return _name(account.parent) + '.' + account.code
            else:
                return account.code
        for account in self.browse(ids):
            res[account.id] = _name(account)
        return res

    def create(self, vals):
        if vals.get('root'):
            vals['kind_analytic'] = self.browse(vals['root']).kind_analytic
        else:
            vals['kind_analytic'] = self.browse(vals['parent']).kind_analytic
        return super(AnalyticAccount, self).create(vals)

    def write(self, ids, vals):
        if vals.get('parent'):
            vals['kind_analytic'] = self.browse(vals['parent']).kind_analytic
        elif vals.get('root'):
            vals['kind_analytic'] = self.browse(vals['root']).kind_analytic
        return super(AnalyticAccount, self).write(ids, vals)

    def convert_view(self, tree):
        res = tree.xpath('//field[@name=\'analytic_accounts\']')
        if not res:
            return
        element_accounts = res[0]

        root_account_ids = self.search( [
            ('parent', '=', False),
            ])
        if not root_account_ids:
            element_accounts.getparent().getparent().remove(
                    element_accounts.getparent())
            return
        for account_id in root_account_ids:
            newelement = copy.copy(element_accounts)
            newelement.tag = 'label'
            newelement.set('name', 'analytic_account_' + str(account_id))
            element_accounts.addprevious(newelement)
            newelement = copy.copy(element_accounts)
            newelement.set('name', 'analytic_account_' + str(account_id))
            element_accounts.addprevious(newelement)
        parent = element_accounts.getparent()
        parent.remove(element_accounts)

    def analytic_accounts_fields_get(self, field, fields_names=None):
        res = {}
        if fields_names is None:
            fields_names = []

        root_account_ids = self.search([('parent', '=', False),])
        for account in self.browse(root_account_ids):
            name = 'analytic_account_' + str(account.id)
            if name in fields_names or not fields_names:
                res[name] = field.copy()
                #res[name]['required'] = account.mandatory
                res[name]['string'] = account.name
                res[name]['relation'] = self._name
                res[name]['domain'] = [('root', '=', account.id),
                        ('type', '=', 'normal')]
        return res


    def get_model_ref(self):
        res = []
        res.append(['party.party', 'Partner'])
        res.append(['company.employee', 'Employee'])
        res.append(['product.product', 'Product'])
        res.append(['ekd.document', 'Document'])
        res.append(['project.project', 'Project'])
        return res

AnalyticAccount()

class OpenTurnoverAnalyticAccountInit(ModelView):
    'Open Turnovers of Analytic Accounts Init'
    _name = 'ekd.account.analytic.open_turnover_analytic.init'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', readonly=True)
    account = fields.Many2One('ekd.account','Account',
                    domain=[
                        ('company','=',Eval('company')),
                        ('kind_analytic','in', _PARTY+_MONEY+_PRODUCT+_DEPRECATION+_OTHER),
                    ])
    level_analytic = fields.Selection([('','')]+_LEVEL_ANALYTIC,'Level', sort=False)
    current_period = fields.Many2One('ekd.period','Current Period',
                        domain=[
                        ('company','=',Eval('company')),
                    ])
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    as_tree = fields.Boolean('As Tree')

    def default_current_period(self):
        return Transaction().context.get('current_period') or False

    def default_start_date(self):
        return Transaction().context.get('start_period') or False

    def default_level_analytic(self):
        return '01'

    def default_end_date(self):
        return Transaction().context.get('end_period') or False

    def default_company(self):
        return Transaction().context.get('company') or False

OpenTurnoverAnalyticAccountInit()


class OpenTurnoverAccount(Wizard):
    'Open Turnover Of Analytic Account'
    _name = 'ekd.account.analytic.open_turnover_analytic'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.analytic.open_turnover_analytic.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_turnover',
                'state': 'end',
            },
        },
    }

    def _action_open_turnover(self, data):
        res={}
        account_obj = self.pool.get('ekd.account')
        bal_party_obj = self.pool.get('ekd.balances.party')
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        account = account_obj.browse(data['form']['account'])
        if account.kind_analytic in _PRODUCT:
            if data['form']['as_tree']:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_analytic_party_tree1')
            else:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_goods_form')
            res = act_window_obj.read(act_window_id)
            if data['form']['level_analytic']:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account'])])
            else:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account'])])

            res['pyson_context'] = PYSONEncoder().encode({
                'balance_period': data['form']['current_period'],
                'account': data['form']['account'],
                'start_date': data['form']['start_date'],
                'end_date': data['form']['end_date'],
                })
        elif account.kind_analytic in _PARTY:
            if data['form']['as_tree']:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_analytic_party_tree1')
            else:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_analytic_party_form')
            res = act_window_obj.read(act_window_id)
            if data['form']['level_analytic']:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account']),
                    ('level', '=', data['form']['level_analytic']) ])
            else:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account'])])

            res['pyson_context'] = PYSONEncoder().encode({
                'current_period': data['form']['current_period'],
                'account': data['form']['account'],
                'start_date': data['form']['start_date'],
                'end_date': data['form']['end_date'],
                })
        elif account.kind_analytic in _OTHER:
            if data['form']['as_tree']:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_analytic_ext_tree1')
            else:
                act_window_id = model_data_obj.get_id('ekd_account',
                    'act_balances_analytic_ext_form')
            res = act_window_obj.read(act_window_id)
            if data['form']['level_analytic']:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account']),
                    ('level', '=', data['form']['level_analytic']) ])
            else:
                res['pyson_domain'] = PYSONEncoder().encode(
                    [('account', '=', data['form']['account'])])

            res['pyson_context'] = PYSONEncoder().encode({
                'current_period': data['form']['current_period'],
                'account': data['form']['account'],
                'start_date': data['form']['start_date'],
                'end_date': data['form']['end_date'],
                })
        elif account.kind_analytic in _MONEY:
            raise Exception('Sorry', "This function don't released")

        return res

OpenTurnoverAccount()


class AccountSelection(ModelSQL, ModelView):
    'Analytic Account Selection'
    _name = 'ekd.account.analytic.selection'
    _description = __doc__
    _rec_name = 'id'

    accounts = fields.Many2Many(
            'ekd.account.analytic-analytic.selection',
            'selection', 'account', 'Accounts')

    def __init__(self):
        super(AccountSelection, self).__init__()
        self._constraints += [
            ('check_root', 'root_account'),
        ]
        self._error_messages.update({
            'root_account': 'Can not have many accounts with the same root ' \
                    'or a missing mandatory root account!',
        })

    def check_root(self, ids):
        "Check Root"
        account_obj = self.pool.get('ekd.account.analytic')

        root_account_ids = account_obj.search([('parent', '=', False),])
        root_accounts = account_obj.browse( root_account_ids)

        selections = self.browse( ids)
        for selection in selections:
            roots = []
            for account in selection.accounts:
                if account.root.id in roots:
                    return False
                roots.append(account.root.id)
            if user: #Root can by pass
                for account in root_accounts:
                    if account.mandatory:
                        if not account.id in roots:
                            return False
        return True

AccountSelection()

class AccountAccountSelection(ModelSQL):
    'Analytic Account - Analytic Account Selection'
    _name = 'ekd.account.analytic-analytic.selection'
    _description = __doc__

    selection = fields.Many2One('ekd.account.analytic.selection',
            'Selection', ondelete='CASCADE', required=True, select=1)
    account = fields.Many2One('ekd.account.analytic', 'Account',
            ondelete='RESTRICT', required=True, select=1)

AccountAccountSelection()

class AnalyticAccountConsolidate(ModelSQL):
    'Analytic Account Consolidate'
    _name = 'ekd.account.analytic.consolidate'
    _description = __doc__

    account = fields.Many2One('ekd.account.analytic',
            'Parent', ondelete='CASCADE', required=True, select=1)
    child = fields.Many2One('ekd.account.analytic', 'Child',
            ondelete='RESTRICT', required=True, select=1)

AnalyticAccountConsolidate()
