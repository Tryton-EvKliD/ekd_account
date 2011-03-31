# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms
"Account"
from __future__ import with_statement
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.tools import reduce_ids
from trytond.pyson import Equal, Eval, Or, In, Not, PYSONEncoder, Date
from trytond.transaction import Transaction
from decimal import Decimal
import datetime
import time
import os
import logging

_KIND_OFF_BALANCE=[
    ('off_balance', 'Off-balance'),
    ('off_balance_out', 'Off-balance (Outside of period)')]

_ANALYTIC_PRODUCT=[
    ('product_other', 'Product (Other)'),
    ('material', 'Product (Materials)'),
    ('fixed_assets', 'Product (Fixed Assets)'),
    ('intangible_assets', 'Product (Intangible assets)'),
    ('goods', 'Product (Goods)'),]

_ANALYTIC_BUDGET=[
    ('budget_items', 'Budget Items'),
    ('budget_items_income', 'Budget Items (Income)'),
    ('budget_items_expense', 'Budget Items (Expense)'),]

_ANALYTIC_DEPRECATION=[
    ('dep_fixed_assets', 'Depreciation of fixed assets'),
    ('dep_intangible', 'Amortization of intangible assets'),
    ]

_ANALYTIC_PARTY=[
    ('party_other', 'Party (Other)'),
    ('party_supplier', 'Party (Supplier)'),
    ('party_customer', 'Party (Customer)'),
    ('party_employee', 'Party (Employee)'),]

_ANALYTIC_MONEY=[
    ('money_other', 'Money (Other)'),
    ('money_cash', 'Money Cash'),
    ('money_bank', 'Money Bank'),]

_ANALYTIC_OTHER=[
    ('analytic', 'Analytic'),
    ('tax', 'Tax'),
    ]

_PRODUCT = [x[0] for x in _ANALYTIC_PRODUCT]

_PARTY =  [x[0] for x in _ANALYTIC_PARTY]

_BUDGET =  [x[0] for x in _ANALYTIC_BUDGET]

_DEPRECATION =  [x[0] for x in _ANALYTIC_DEPRECATION]

_OTHER =  [x[0] for x in _ANALYTIC_OTHER]

_MONEY =  [x[0] for x in _ANALYTIC_MONEY]

_LEVEL_ANALYTIC=[
        ('01', '01 - First level'),
        ('02', '02 - Second level'),
        ('03', '03 - Third level'),
        ('04', '04 - Fourth level'),
        ('05', '05 - Fifth level'),
        ('06', '06 - Sixth level'),
        ('07', '07 - Seventh level'),
        ]
_ICONS = {
    'open': 'tryton-open',
    'close': 'tryton-readonly',
    }

ICONS = [(x, x) for x in [
    'tryton-accessories',
    'tryton-attachment',
    'tryton-clear',
    'tryton-close',
    'tryton-calculator',
    'tryton-calendar',
    'tryton-clock',
    'tryton-connect',
    'tryton-copy',
    'tryton-currency',
    'tryton-delete',
    'tryton-development',
    'tryton-dialog-error',
    'tryton-dialog-information',
    'tryton-dialog-warning',
    'tryton-disconnect',
    'tryton-executable',
    'tryton-find',
    'tryton-find-replace',
    'tryton-folder-new',
    'tryton-folder-saved-search',
    'tryton-fullscreen',
    'tryton-graph',
    'tryton-go-home',
    'tryton-go-jump',
    'tryton-go-next',
    'tryton-go-previous',
    'tryton-help',
    'tryton-image-missing',
    'tryton-information',
    'tryton-lock',
    'tryton-list',
    'tryton-list-add',
    'tryton-list-remove',
    'tryton-locale',
    'tryton-log-out',
    'tryton-mail-message-new',
    'tryton-new',
    'tryton-noimage',
    'tryton-open',
    'tryton-package',
    'tryton-preferences',
    'tryton-preferences-system',
    'tryton-preferences-system-session',
    'tryton-presentation',
    'tryton-print',
    'tryton-readonly',
    'tryton-refresh',
    'tryton-save-as',
    'tryton-save',
    'tryton-spreadsheet',
    'tryton-start-here',
    'tryton-tree',
    'tryton-system',
    'tryton-system-file-manager',
    'tryton-users',
    'tryton-web-browser',
]]

class TypeTemplate(ModelSQL, ModelView):
    'Account Type Template'
    _name = 'ekd.account.type.template'
    _description = __doc__
    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    parent = fields.Many2One('ekd.account.type.template', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('ekd.account.type.template', 'parent', 'Children')
    sequence = fields.Integer('Sequence', required=True)
#    balance_sheet = fields.Boolean('Balance Sheet')
#    income_statement = fields.Boolean('Income Statement')
    type_balance = fields.Selection([
        ('active', 'Active'),
        ('passive', 'Passive'),
        ('both', 'Active - Passive'),
        ], 'Type Balance', required=True)

    def __init__(self):
        super(TypeTemplate, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_display_balance(self):
        return 'active'

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(type):
            if type.parent:
                return _name(type.parent) + '\\' + type.name
            else:
                return type.name
        for type in self.browse(ids):
            res[type.id] = _name(type)
        return res

    def _get_type_value(self, template, type=None):
        '''
        Set the values for account creation.

        :param template: the BrowseRecord of the template
        :param type: the BrowseRecord of the type to update
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        if not type or type.name != template.name:
            res['name'] = template.name
        if not type or type.sequence != template.sequence:
            res['sequence'] = template.sequence
#        if not type or type.balance_sheet != template.balance_sheet:
#            res['balance_sheet'] = template.balance_sheet
#        if not type or type.income_statement != template.income_statement:
#            res['income_statement'] = template.income_statement
        if not type or type.type_balance != template.type_balance:
            res['type_balance'] = template.type_balance
        if not type or type.template.id != template.id:
            res['template'] = template.id
        return res

    def create_type(self, template, company,
            template2type=None, parent=False):
        '''
        Create recursively types based on template.

        :param template: the template id or the BrowseRecord of the template
                used for type creation
        :param company: the id of the company for which types are created
        :param template2type: a dictionary with template id as key
                and type id as value, used to convert template id
                into type. The dictionary is filled with new types
        :param parent: the type id of the parent of the types that must
                be created
        :return: id of the type created
        '''
        type_obj = self.pool.get('ekd.account.type')
        lang_obj = self.pool.get('ir.lang')

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2type:
            vals = self._get_type_value(template)
            vals['company'] = company
            vals['parent'] = parent

            new_id = type_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        type_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2type[template.id] = new_id
        else:
            new_id = template2type[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_type(child, company,
                template2type=template2type, parent=new_id))
        return new_id

TypeTemplate()


class Type(ModelSQL, ModelView):
    'Account Type'
    _name = 'ekd.account.type'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None)
    parent = fields.Many2One('ekd.account.type', 'Parent',
            ondelete="RESTRICT")
    childs = fields.One2Many('ekd.account.type', 'parent', 'Children')
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order the account type')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    amount = fields.Function(fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']), 'get_amount')
#    balance_sheet = fields.Boolean('Balance Sheet')
#    income_statement = fields.Boolean('Income Statement')
    type_balance = fields.Selection([
        ('active', 'Active'),
        ('passive', 'Passive'),
        ('both', 'Active - Passive'),
        ], 'Type Balance', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete="RESTRICT")
    template = fields.Many2One('ekd.account.type.template', 'Template')

    def __init__(self):
        super(Type, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

#    def default_balance_sheet(self):
#        return False

#    def default_income_statement(self):
#        return False

    def default_type_balance(self):
        return 'active'

    def get_currency_digits(self, ids, name):
        res = {}
        for type in self.browse(ids):
            res[type.id] = type.company.currency.digits
        return res

    def get_amount(self, ids, name):
        account_obj = self.pool.get('ekd.account')
        currency_obj = self.pool.get('currency.currency')

        res = {}
        for type in ids:
            res[type] = Decimal('0.0')

#        child = self.search([
#            ('parent', 'child_of', ids),
#            ])
#        type_sum = {}
#        for type in child:
#            type_sum[type] = Decimal('0.0')

#        account = account_obj.search([
#            ('type', 'in', child),
#            ])
#        for account in account_obj.browse(account,
#                ):
#            type_sum[account.type.id] += currency_obj.round(
#                    account.company.currency, account.debit - account.credit)

#        types = self.browse(ids)
#        for type in types:
#            child = self.search([
#                ('parent', 'child_of', [type.id]),
#                ])
#            for child in child:
#                res[type.id] += type_sum[child]
#            res[type.id] = currency_obj.round(
#                        type.company.currency, res[type.id])
#            if type.display_balance == 'credit':
#                res[type.id] = - res[type.id]
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        def _name(type):
            if type.parent:
                return _name(type.parent) + '\\' + type.name
            else:
                return type.name
        for type in self.browse(ids):
            res[type.id] = _name(type)
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        type = self.search([
            ('parent', 'child_of', ids),
            ])
        return super(Type, self).delete(type)

    def update_type(self, type, template2type=None):
        '''
        Update recursively types based on template.

        :param type: a type id or the BrowseRecord of the type
        :param template2type: a dictionary with template id as key
                and type id as value, used to convert template id
                into type. The dictionary is filled with new types
        '''
        template_obj = self.pool.get('ekd.account.type.template')
        lang_obj = self.pool.get('ir.lang')

        if template2type is None:
            template2type = {}

        if isinstance(type, (int, long)):
            type = self.browse(type)

        if type.template:
            vals = template_obj._get_type_value(type.template, type=type)
            if vals:
                self.write(type.id, vals)

            prev_lang = type._context.get('language') or 'en_US'
            ctx = Transaction().context.copy()
            for lang in lang_obj.get_translatable_languages(
                    ):
                if lang == prev_lang:
                    continue
                ctx['language'] = lang
                type.setLang(lang)
                data = template_obj._get_type_value(type.template, type=type)
                if data:
                    self.write(type.id, data)
            type.setLang(prev_lang)
            template2type[type.template.id] = type.id

        for child in type.childs:
            self.update_type(child,
                    template2type=template2type)

Type()

class AccountTemplate(ModelSQL, ModelView):
    'Account Template'
    _name = 'ekd.account.template'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True,
            select=1)
    code = fields.Char('Code', size=None, select=1)
    type = fields.Many2One('ekd.account.type.template', 'Section Accounting',
            ondelete="RESTRICT",
            states={
                'invisible': In(Eval('kind'), ['view', 'section']),
                'required': Not(In(Eval('kind'), ['view', 'section'])),
            }, depends=['kind'])
    parent = fields.Many2One('ekd.account.template', 'Parent', select=1,
            ondelete="RESTRICT")
    childs = fields.One2Many('ekd.account.template', 'parent', 'Children')
    type_balance = fields.Selection([
        ('active', 'Active'),
        ('passive', 'Passive'),
        ('both', 'Active - Passive'),
        ], 'Type Balance',
        states={
            'required': Not(In(Eval('kind'), ['view', 'section'])),
            'invisible': In(Eval('kind'), ['view', 'section'])
        }, sort=False)

    kind = fields.Selection([
            ('section', 'Section'),
            ('view', 'View'),
            ('balance', 'Balance'),
            ]+_KIND_OFF_BALANCE, 'Kind of Account', required=True, sort=False)
    kind_analytic = fields.Selection(
            _ANALYTIC_PARTY+
            _ANALYTIC_PRODUCT+
            _ANALYTIC_DEPRECATION+
            _ANALYTIC_MONEY+
            _ANALYTIC_OTHER+
            [('other', 'Other')], 'Kind of Analytic',
            states={
                'required': Not(In(Eval('kind'), ['view', 'section'])),
                'invisible': In(Eval('kind'), ['view', 'section'])
            }, sort=False)


    def __init__(self):
        super(AccountTemplate, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_kind(self):
        return 'balance'

    def default_kind_analytic(self):
        return 'other'

    def default_type_balance(self):
        return 'active'

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for template in self.browse(ids):
            if template.code:
                res[template.id] = template.code + ' - ' + template.name
            else:
                res[template.id] = template.name
        return res

    def search_rec_name(self, name, args):
        args2 = []
        i = 0
        while i < len(args):
            ids = self.search([
                ('code', args[i][1], args[i][2]),
                ], limit=1)
            if ids:
                args2.append(('code', args[i][1], args[i][2]))
            else:
                args2.append((self._rec_name, args[i][1], args[i][2]))
            i += 1
        return args2

    def _get_account_value(self, template, account=None):
        '''
        Set the values for account creation.

        :param template: the BrowseRecord of the template
        :param account: the BrowseRecord of the account to update
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        if not account or account.name != template.name:
            res['name'] = template.name
        if not account or account.code != template.code:
            res['code'] = template.code
        if not account or account.kind != template.kind:
            res['kind'] = template.kind
        if not account or account.kind_analytic != template.kind_analytic:
            res['kind_analytic'] = template.kind_analytic
        if not account or account.template.id != template.id:
            res['template'] = template.id
        return res

    def create_account(self, template, company,
            template2account=None, template2type=None, parent=False):
        '''
        Create recursively accounts based on template.

        :param template: the template id or the BrowseRecord of template
                used for account creation
        :param company: the id of the company for which accounts
                are created
        :param template2account: a dictionary with template id as key
                and account id as value, used to convert template id
                into account. The dictionary is filled with new accounts
        :param template2type: a dictionary with type template id as key
                and type id as value, used to convert type template id
                into type.
        :param parent: the account id of the parent of the accounts
                that must be created
        :return: id of the account created
        '''
        logger = logging.getLogger('CREATE ACCOUNT')
        account_obj = self.pool.get('ekd.account')
        lang_obj = self.pool.get('ir.lang')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2account:
            vals = self._get_account_value(template)
            vals['company'] = company
            vals['parent'] = parent
            vals['active'] = True
            vals['type'] = template2type.get(template.type.id, False)

            new_id = account_obj.create(vals)

            prev_lang = template._context.get('language') or 'ru_RU'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        account_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2account[template.id] = new_id
        else:
            new_id = template2account[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_account(child, company,
                template2account=template2account, template2type=template2type,
                parent=new_id))
        return new_id

AccountTemplate()

class Account(ModelSQL, ModelView):
    'Account'
    _name = 'ekd.account'
    _description = __doc__
    _rec_name = "code"
    _order_name = "code"

    name = fields.Char('Name', size=None, required=True,
                select=1)
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True,
                ondelete="RESTRICT")
    currency = fields.Function(fields.Many2One('currency.currency', 'Currency'), 'get_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    second_currency = fields.Many2One('currency.currency', 'Secondary currency',
                    help='Force all moves for this account \n' \
                    'to have this secondary currency.', ondelete="RESTRICT")
    type = fields.Many2One('ekd.account.type', 'Section Accounting', ondelete="RESTRICT",
                states={
                'invisible': In(Eval('kind'), ['view', 'section']),
                #'required': Not(In(Eval('kind'), ['view', 'section'])),
                }, depends=['kind'])
    parent = fields.Many2One('ekd.account', 'Parent', select=1,
                left="left", right="right", 
                domain=[('kind','in', ['view', 'section']), ('company','=',Eval('company'))],
                ondelete="RESTRICT")
    left = fields.Integer('Left', select=1)
    right = fields.Integer('Right', select=1)
    childs = fields.One2Many('ekd.account', 'parent', 'Children')

    control_analytic = fields.Selection([
                ('debit','Debit'),
                ('credit','Credit'),
                ('both','Debit and Credit'),
                ('not_control',"Don't Control"),
                ('not_debit',"Don't Control Debit"),
                ('not_credit',"Don't Control Credit"),
                ],'Control Balance Analytic',
                states={
                'invisible': Not(In(Eval('kind_analytic'),
                        _PARTY+_PRODUCT+_DEPRECATION+_MONEY+_OTHER)),
                })
    move_balance = fields.Selection([
                ('close_period','Closing at the end of financial period'),
                ('close_year','Closing fiscal year-end'),
                ('dont_close',"Don't close"),
                ('dont_move',"Don't move balance"),
                ],'Type Move Balance')
    #
    balance_dt = fields.Function(fields.Numeric('Debit Balance', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']), 'get_balance')
    balance_ct = fields.Function(fields.Numeric('Credit Balance', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']), 'get_balance')
    credit = fields.Function(fields.Numeric('Credit', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']),'get_balance')
    debit = fields.Function(fields.Numeric('Debit', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']),'get_balance')
    balance_dt_end = fields.Function(fields.Numeric('Debit Balance End', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']),'get_balance')
    balance_ct_end = fields.Function(fields.Numeric('Credit Balance End', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']),'get_balance')
    balance_start = fields.Function(fields.Numeric('Balance', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']),'get_balance')
    balance_end = fields.Function(fields.Numeric('Balance End', #digits=(16, Eval('currency_digits', 2)),
                depends=['currency_digits']), 'get_balance')
    note = fields.Text('Note')
    id_1c = fields.Char("ID import from 1C", size=None, select=1)
    kind = fields.Selection([
                ('section', 'Section'),
                ('view', 'View'),
                ('balance', 'Balance'),
                ]+_KIND_OFF_BALANCE, 'Kind of Account', required=True, sort=False, select=1)
    type_balance = fields.Selection([
                ('active', 'Active'),
                ('passive', 'Passive'),
                ('both', 'Active and Passive'),
                ], 'Type Balance', 
                states={
                    'required': Not(In(Eval('kind'), ['view', 'section'])),
                    'invisible': In(Eval('kind'), ['view', 'section'])
                }, sort=False)
    type_balance_period = fields.Selection([
                ('period', 'Period'),
                ('fiscalyear', 'Fiscalyear'),
                ('datetime_off', 'Outside of periods'),
                ], 'Type Balance Period', 
                states={
                    'invisible': In(Eval('kind'), ['view', 'section'])
                }, sort=False)

    kind_analytic = fields.Selection(
                _ANALYTIC_PARTY+
                _ANALYTIC_PRODUCT+
                _ANALYTIC_DEPRECATION+
                _ANALYTIC_MONEY+
                _ANALYTIC_OTHER+
                [('other', 'Other'),], 
                'Kind of Analytic Accounting', states={
                    'required': Not(In(Eval('kind'), ['view', 'section'])),
                    'invisible': In(Eval('kind'), ['view', 'section'])
                }, sort=False, select=2)
    side_analytic = fields.Selection([
                ('both','Debit and Credit'),
                ('debit','Debit'),
                ('credit','Credit'),
                ('separate','Separate Debit and Credit'),
                ], 'Side Analytic Accounting',
                states={'invisible': Not(In(Eval('kind_analytic'),
                        _PARTY+_PRODUCT+_DEPRECATION+_MONEY+_OTHER)),},)
    template = fields.Many2One('ekd.account.template', 'Template')
    icon = fields.Selection(ICONS, 'Icon', translate=False)

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_accounts'),
        ]
        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
            'delete_account_containing_move_lines': 'You can not delete ' \
                    'accounts containing move lines!',
        })
        self._sql_error_messages.update({
            'parent_fkey': 'You can not delete accounts ' \
                    'that have children!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))

    def default_left(self):
        return 0

    def default_separate_analytic(self):
        return 'both'

    def default_right(self):
        return 0

    def default_active(self):
        return True

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_currency(self):
        company_obj = self.pool.get('company.company')
        return company_obj.browse(Transaction().context.get('company')).currency.id or False

    def default_kind(self):
        return 'view'

    def default_control_analytic(self):
        return 'not_control'

    def default_separate_analytic(self):
        return 'both'

    def default_type_balance(self):
        return 'active'

    def default_kind_analytic(self):
        return 'other'

    def default_icon(self):
        return 'tryton-open'

    def get_icon(self, ids, name):
        res = {}
        res.setdefault(ids, 'tryton-open')
#        for period in self.browse(ids):
#            res[period.id] = _ICONS.get(period.state, '')
        return res

    def get_currency(self, ids, name):
        currency_obj = self.pool.get('currency.currency')
        res = {}
        for account in self.browse(ids):
            res[account.id] = account.company.currency.id
        return res

    def get_currency_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for account in self.browse(ids):
            res[account.id] = account.company.currency.digits
        return res

    def get_childs(self, id):
        res = []
        for child in self.browse(id).childs:
            if child.childs:
                for id in self.get_childs(child.id):
                    res.append(id)
                if child.kind not in ('view', 'consolidation'):
                    res.append(child.id)
            elif child.kind not in ('view', 'consolidation'):
                res.append(child.id)

        return res


    def get_balance(self, ids, names):
        res = {}
        context =Transaction().context
        if not context.get('period_start') or not context.get('period_end'):
            return {}
        balance_obj = self.pool.get('ekd.balances.account')
        period_obj = self.pool.get('ekd.period')
        period_ids = []
        for account_id in ids:
            for name in names:
               res.setdefault(name, {})
               res[name].setdefault(account_id, Decimal('0.0'))

        if context.get('period_start', False) == context.get('period_end', True):
            period_ids.append(context.get('period_start'))
        else:
            period_ids = period_obj.search([
                            ('start_date','>=', period_obj.browse(context.get('period_start')).start_date),
                            ('end_date','<=', period_obj.browse(context.get('period_end')).end_date)
                            ], order=[('start_date','ASC')])
        # Определение счетов с субсчетами
        account_real = []
        account_with_childs = {}
        for account in self.browse(ids):
            # 1. Тип счета (view) с подчиненными счетами 
            if account.childs:
                account_with_childs[account.id] = self.get_childs(account.id)
            # 2. Тип счетам с реальными остатками
            else:
                account_real.append(account.id)

        if account_real:
            balance_ids = balance_obj.search([
                            ('account','in',account_real),
                            ('period', 'in', period_ids)
                            ])

            for balance in balance_obj.browse(balance_ids):
                for name in names:
                    if name == 'balance_start' and balance.period.id == context.get('period_start'):
                            res[name][balance.account.id] += balance.balance
                    elif name == 'balance_end' and balance.period.id == context.get('period_end'):
                            res[name][balance.account.id] += balance.balance_end
                    elif name == 'balance_dt' and balance.period.id == context.get('period_start'):
                            res[name][balance.account.id] += balance.balance_dt
                    elif name == 'balance_ct' and balance.period.id == context.get('period_start'):
                            res[name][balance.account.id] += balance.balance_ct
                    elif name == 'balance_dt_end' and balance.period.id == context.get('period_end'):
                        res[name][balance.account.id] += balance.balance_dt_end
                    elif name == 'balance_ct_end' and balance.period.id == context.get('period_end'):
                        res[name][balance.account.id] += balance.balance_ct_end
                    elif name == 'debit':
                        res[name][balance.account.id] += balance.debit
                    elif name == 'credit':
                        res[name][balance.account.id] += balance.credit

        if account_with_childs:
            for account_id in account_with_childs.keys():
                balance_ids = balance_obj.search([
                            ('account','in',account_with_childs[account_id]),
                            ('period', 'in', period_ids)
                            ])
                for balance in balance_obj.browse(balance_ids):
                    for name in names:
                        if name == 'balance_start' and balance.period.id == context.get('period_start'):
                            res[name][account_id] += balance.balance
                        elif name == 'balance_end' and balance.period.id == context.get('period_end'):
                            res[name][account_id] += balance.balance_end
                        elif name == 'balance_dt' and balance.period.id == context.get('period_start'):
                            res[name][account_id] += balance.balance_dt
                        elif name == 'balance_ct' and balance.period.id == context.get('period_start'):
                            res[name][account_id] += balance.balance_ct
                        elif name == 'balance_dt_end' and balance.period.id == context.get('period_end'):
                            res[name][account_id] += balance.balance_dt_end
                        elif name == 'balance_ct_end' and balance.period.id == context.get('period_end'):
                            res[name][account_id] += balance.balance_ct_end
                        elif name == 'debit':
                            res[name][account_id] += balance.debit
                        elif name == 'credit':
                            res[name][account_id] += balance.credit

        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for account in self.browse(ids):
            if account.code:
#                res[account.id] = account.code
                res[account.id] = "%s - %s"%(account.code,account.name)
            else:
                res[account.id] = account.name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([
                ('code',) + clause[1:],
                ], limit=1)
        if ids:
            return [('code',) + clause[1:]]
        return [(self._rec_name,) + clause[1:]]

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default['left'] = 0
        default['right'] = 0
        default['parent'] = 0
        default['corr_debit'] = False
        default['corr_credit'] = False
        default['child_consol_ids'] = False
        res = super(Account, self).copy(ids, default=default)
        self._rebuild_tree('parent', False, 0)
        return res

    def write(self, ids, vals):
        if not vals.get('active', True):
            move_line_obj = self.pool.get('ekd.account.move.line')
            account = self.search([
                ('parent', 'child_of', ids),
                ])
            if move_line_obj.search([
                ('account', 'in', account),
                ]):
                vals = vals.copy()
                del vals['active']
        return super(Account, self).write(ids, vals)

    def delete(self, ids):
        move_line_obj = self.pool.get('ekd.account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        account = self.search([
            ('parent', 'child_of', ids),
            ])
        if move_line_obj.search([
            ('dt_account', 'in', account),
            ]):
            self.raise_user_error('delete_account_containing_ru_move_lines')
        if move_line_obj.search([
            ('ct_account', 'in', account),
            ]):
            self.raise_user_error('delete_account_containing_ru_move_lines')

        return super(Account, self).delete(account)

    def update_account(self, account,
            template2account=None, template2type=None):
        '''
        Update recursively accounts based on template.

        :param account: an account id or the BrowseRecord of the account
        :param template2account: a dictionary with template id as key
                and account id as value, used to convert template id
                into account. The dictionary is filled with new accounts
        :param template2type: a dictionary with type template id as key
                and type id as value, used to convert type template id
                into type.
        '''
        template_obj = self.pool.get('ekd.account.template')
        lang_obj = self.pool.get('ir.lang')

        if template2account is None:
            template2account = {}

        if template2type is None:
            template2type = {}

        if isinstance(account, (int, long)):
            account = self.browse(account)

        if account.template:
            vals = template_obj._get_account_value(account.template, account=account)
            if account.type.id != template2type.get(account.template.type.id,
                    False):
                vals['type'] = template2type.get(account.template.type.id,
                        False)
            if vals:
                self.write(account.id, vals)

            prev_lang = account._context.get('language') or 'en_US'
            ctx = context.copy()
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                ctx['language'] = lang
                account.setLang(lang)
                data = template_obj._get_account_value(
                           account.template, account=account)
                if data:
                    self.write(account.id, data)
            account.setLang(prev_lang)
            template2account[account.template.id] = account.id

        for child in account.childs:
            self.update_account(child,
                    template2account=template2account,
                    template2type=template2type)

Account()

class AccountLevelAnalytic(ModelSQL, ModelView):
    'Level Analytic Account'
    _name = 'ekd.account.level_analytic'
    _description = __doc__

    account = fields.Many2One('ekd.account', 'Account')
    name = fields.Char('Name Analytic', size=120)
    side = fields.Selection([('dt','Debit'),('ct','Credit')], 'Side Account')
    level = fields.Selection(_LEVEL_ANALYTIC, 'Level analityc', required=True)
    type_analytic = fields.Selection('type_analytic_get', 'Type analityc')
    ref_analytic = fields.Reference('Type analityc', selection='type_analytic_get', required=True)
    domain = fields.Char('Domain', size=None, help="Domain for model")
    move_balance = fields.Boolean('Move Balance in other period')
    collapse_balance = fields.Boolean('Collapse Remains')

    def type_analytic_get(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.level_analytic'),
                    ('pole', '=', 'type_analytic'),
                    ], order=[('sequence','ASC')])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def default_side(self):
        if Transaction().context.get('side', 'dt') =='ct':
            return 'ct'
        else:
            return 'dt'

    def default_move_balance(self):
        return True

    def get_domain_type(self):
        res = []
        raise Exception('ddd')
        return res


AccountLevelAnalytic()

class AccountControlEntriesDebit(ModelSQL):
    'Control Entries with Debit Account'
    _name = 'ekd.account.control.debit'
#    _table = 'ekd_account_control_entries_dt'
    _description = __doc__
    account = fields.Many2One('ekd.account', 'Parent Account',
            ondelete='CASCADE', select=1)
    credit = fields.Many2One('ekd.account', 'Credit Account', ondelete='RESTRICT',
            select=1, required=True)

AccountControlEntriesDebit()

class AccountControlEntriesCredit(ModelSQL):
    'Control Entries with Credit Account'
    _name = 'ekd.account.control.credit'
#    _table = 'ekd_account_control_entries_ct'
    _description = __doc__
    account = fields.Many2One('ekd.account', 'Parent Account',
            ondelete='CASCADE', select=1)
    debit = fields.Many2One('ekd.account', 'Debit Account', ondelete='RESTRICT',
            select=1, required=True)

AccountControlEntriesCredit()


class AccountConsolidation(ModelSQL):
    'Consolidation Account'
    _name = 'ekd.account.consolidation'
#    _table = 'ekd_account_consolidation_rel'
    _description = __doc__

    account = fields.Many2One('ekd.account', 'Parent Account',
            ondelete='CASCADE', select=1)
    child = fields.Many2One('ekd.account', 'Child Account', ondelete='RESTRICT',
            select=1, required=True)

AccountConsolidation()

class OpenChartAccountInit(ModelView):
    'Open Chart Account Init'
    _name = 'ekd.account.open_chart_account.init'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company')
    fiscalyear = fields.Many2One('ekd.fiscalyear', 'Fiscal Year',
            help='Leave empty for all open fiscal year')
    period_start = fields.Many2One('ekd.period', 'Period Balance Begin',
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])
    period_end = fields.Many2One('ekd.period', 'Period Balance End',
                        domain=[
                            ('company','=',Eval('company'))
                        ], depends=['company'])

    def default_period_start(self):
        return Transaction().context.get('current_period') or False

    def default_period_end(self):
        return Transaction().context.get('current_period') or False

    def default_company(self):
        return Transaction().context.get('company') or False

OpenChartAccountInit()


class OpenChartAccount(Wizard):
    'Open Chart Of Account'
    _name = 'ekd.account.open_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.open_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_chart',
                'state': 'end',
            },
        },
    }

    def _action_open_chart(self, data):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('ekd_account', 'act_ekd_account_tree2')
        res = act_window_obj.read(act_window_id)
        res['pyson_context'] = PYSONEncoder().encode({
            'company': data['form']['company'],
            'fiscalyear': data['form']['fiscalyear'],
            'period_start': data['form']['period_start'],
            'period_end': data['form']['period_end'],
            })
        return res

OpenChartAccount()

class CreateChartAccountInit(ModelView):
    'Create Chart Account Init'
    _name = 'ekd.account.create_chart_account.init'
    _description = __doc__

CreateChartAccountInit()


class CreateChartAccountAccount(ModelView):
    'Create Chart Account Account'
    _name = 'ekd.account.create_chart_account.account'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company', required=True)
    account_template = fields.Many2One('ekd.account.template',
            'Account Template', required=True, domain=[('parent', '=', False)])

CreateChartAccountAccount()


class CreateChartAccountPropertites(ModelView):
    'Create Chart Account Properties'
    _name = 'ekd.account.create_chart_account.properties'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company')

    account_receivable = fields.Many2One('ekd.account',
            'Default Receivable Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_payable = fields.Many2One('ekd.account',
            'Default Payable Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_cash = fields.Many2One('ekd.account',
            'Default Cash Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_bank = fields.Many2One('ekd.account',
            'Default Bank Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_tax = fields.Many2One('ekd.account',
            'Default Taxs Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_fixed = fields.Many2One('ekd.account',
            'Default Fixed Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    account_goods = fields.Many2One('ekd.account',
            'Default Goods Account',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

CreateChartAccountPropertites()


class CreateChartAccount(Wizard):
    'Create chart account from template'
    _name = 'ekd.account.create_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.create_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('account', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'account': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.create_chart_account.account',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create_account', 'Create', 'tryton-ok', True),
                ],
            },
        },
        'create_account': {
            'actions': ['_action_create_account'],
            'result': {
                'type': 'form',
                'object': 'ekd.account.create_chart_account.properties',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('create_properties', 'Create', 'tryton-ok', True),
                ],
            },
        },
        'create_properties': {
                'result': {
                'type': 'action',
                'action': '_action_create_properties',
                'state': 'end',
            },
        },
    }

    def _action_create_account(self, datas):
        account_type_template_obj = \
                self.pool.get('ekd.account.type.template')
        account_template_obj = self.pool.get('ekd.account.template')

        #context['language'] = 'ru_RU'

        account_template = account_template_obj.browse(
                datas['form']['account_template'])

        # Create account types
        template2type = {}
        account_type_template_obj.create_type(
                account_template.type, datas['form']['company'], 
                template2type=template2type)

        # Create accounts
        template2account = {}
        account_template_obj.create_account(
                account_template, datas['form']['company'],
                template2account=template2account,
                template2type=template2type)

        return {'company': datas['form']['company']}

    def _action_create_properties(self, datas):
        property_obj = self.pool.get('ir.property')
        model_field_obj = self.pool.get('ir.model.field')
        '''
        account_receivable_field_id = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_receivable_'),
            ], limit=1)[0]
        property_ids = property_obj.search([
            ('field', '=', account_receivable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ])
        with Transaction().set_user(0):
            property_obj.delete(property_ids)
            property_obj.create({
                'name': 'account_receivable_',
                'field': account_receivable_field_id,
                'value': 'ekd.account,' + \
                        str(datas['form']['account_receivable']),
                'company': datas['form']['company'],
                })

        account_payable_field_id = model_field_obj.search([
            ('model.model', '=', 'party.party'),
            ('name', '=', 'account_payable_'),
            ], limit=1)[0]
        property_ids = property_obj.search([
            ('field', '=', account_payable_field_id),
            ('res', '=', False),
            ('company', '=', datas['form']['company']),
            ])
        with Transaction().set_user(0):
            property_obj.delete(property_ids)
            property_obj.create({
                'name': 'account_payable_',
                'field': account_payable_field_id,
                'value': 'ekd.account,' + \
                        str(datas['form']['account_payable']),
                'company': datas['form']['company'],
                })
        '''
        return {}

CreateChartAccount()


class UpdateChartAccountInit(ModelView):
    'Update Chart Account from Template Init'
    _name = 'ekd.account.update_chart_account.init'
    _description = __doc__
    account = fields.Many2One('ekd.account', 'Root Account',
            required=True, domain=[('parent', '=', False)])

UpdateChartAccountInit()


class UpdateChartAccountStart(ModelView):
    'Update Chart Account from Template Start'
    _name = 'ekd.account.update_chart_account.start'
    _description = __doc__

UpdateChartAccountStart()


class UpdateChartAccount(Wizard):
    'Update Chart Account from Template'
    _name = 'ekd.account.update_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.update_chart_account.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_action_update_account'],
            'result': {
                'type': 'form',
                'object': 'ekd.account.update_chart_account.start',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
    }

    def _action_update_account(self, datas):
        account_type_obj = self.pool.get('ekd.account.type')
        account_type_template_obj = \
                self.pool.get('ekd.account.type.template')
        account_obj = self.pool.get('ekd.account')
        account_template_obj = self.pool.get('ekd.account.template')

        account = account_obj.browse(datas['form']['account'],
                )

        # Update account types
        template2type = {}
        account_type_obj.update_type(account.type,
                template2type=template2type)
        # Create missing account types
        if account.type.template:
            account_type_template_obj.create_type(
                    account.type.template, account.company.id,
                    template2type=template2type)

        # Update accounts
        template2account = {}
        account_obj.update_account(account,
                template2account=template2account, template2type=template2type)
        # Create missing accounts
        if account.template:
            account_template_obj.create_account(account.template,
                    account.company.id,
                    template2account=template2account,
                    template2type=template2type)

        return {}

UpdateChartAccount()

