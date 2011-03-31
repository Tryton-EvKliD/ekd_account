# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Tax"
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from decimal import Decimal
from trytond.pyson import Eval, Not, Equal
from trytond.cache import Cache

class Group(ModelSQL, ModelView):
    'Tax Group'
    _name = 'ekd.account.tax.group'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company')
    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None, required=True)
    taxes = fields.One2Many('ekd.account.tax', 'group', 'Taxes')

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
        ]

Group()

class Tax(ModelSQL, ModelView):
    '''
    Account Tax

    Type:
        percentage: tax = base_amount * percentage / 100
        fixed: tax = amount
        scale: tax = scale('1': percentage, Less(XXX), Greater(XXX), ...)
    '''
    _name = 'ekd.account.tax'
    _description = 'Account Tax'

    company = fields.Many2One('company.company', 'Company', required=True)
    shortname = fields.Char('Short Name', required=True)
    name = fields.Char('Description', required=True,
            help="The name that will be used in reports")
    group = fields.Many2One('ekd.account.tax.group', 'Group')
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence',
            help='Use to order the taxes')
    parent = fields.Many2One('ekd.account.tax', 'Parent', select=1,
            domain=[('company', '=', Eval('company'))], depends=['company'])
    childs = fields.One2Many('ekd.account.tax', 'parent', 'Children',
            domain=[('company', '=', Eval('company'))], depends=['company'])

    current_rate = fields.Function(fields.Numeric('Current Rate', digits=(16, Eval('rate_digits', 2)),
            states={
                'invisible': Equal(Eval('type_rate'), 'scale'),
            }, depends=['type']), 'get_current_rate')
    rate = fields.One2Many('ekd.account.tax.rate', 'tax', 'Rate Tax')
    rate_digits = fields.Function(fields.Integer('Rate Digits'), 'get_rate_digits')

    type_base = fields.Selection([
        ('vat', 'VAT'),
        ('sales_tax', 'Sales Tax'),
        ('turnover', 'Turnover'),
        ('balance', 'Balance'),
        ], 'Type Base', 
        help='Type- "VAT" and "Sales Tax" used in document for computed"\n'\
        'Type - "Turnover" and "Balance" used in accounting for computed'
        , required=True)

    type_rate = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('scale', 'Scale'),
        ], 'Type Rate', required=True)
    kind = fields.Selection([
        ('tax', 'Tax'),
        ('excise','Excise'),
        ('social', 'Social'),
        ('other', 'Other'),
        ], 'Type', required=True)

    formula = fields.Text('Formula', 
            help="Enter formula for computer")

    account_tax = fields.Many2One('ekd.account', 'Account Tax',
            domain=[('company', '=', Eval('company')),
                    ('kind', '!=', 'view')],
            depends=['company'])
    move_payment_tax = fields.Many2One('ekd.account.move.template', 'Template for payment Tax',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])
    move_tax_calculation = fields.Many2One('ekd.account.move.template', 'Template for tax calculation',
            domain=[('company', '=', Eval('company'))],
            depends=['company'])

    def __init__(self):
        super(Tax, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        super(Tax, self).init(module_name)

    def default_active(self):
        return True

    def default_type(self):
        return 'percentage'

    def default_company(self):
        return Transaction().context.get('company') or False

    def get_rate_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for tax in self.browse(ids):
            if tax.type_rate == 'percentage':
                res[tax.id] = 8
        return res

    def get_current_rate(self, ids, name):
        res = {}.fromkeys(ids, Decimal('0.0'))
        for tax in self.browse(ids):
            if tax.type_rate == 'percentage':
                res[tax.id] = Decimal('0.0')
        return res

    def _process_tax(self, tax, price_unit):
        if tax.type_rate == 'percentage':
            amount = price_unit * tax.percentage / Decimal('100')
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }
        if tax.type_rate == 'fixed':
            amount = tax.amount
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }

    def _unit_compute(self, taxes, price_unit):
        res = []
        for tax in taxes:
            if tax.type_rate != 'none':
                res.append(self._process_tax(tax, price_unit,
                    ))
            if len(tax.childs):
                res.extend(self._unit_compute(tax.childs,
                    price_unit))
        return res

    def delete(self, ids):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).delete(ids)

    def create(self, vals):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).create(vals)

    def write(self, ids, vals):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).write(ids, vals)

    @Cache('account_tax.sort_taxes')
    def sort_taxes(self, ids):
        '''
        Return a list of taxe ids sorted

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of tax ids
        :param context: the context
        :return: a list of tax ids sorted
        '''
        return self.search([
            ('id', 'in', ids),
            ], order=[('sequence', 'ASC'), ('id', 'ASC')])

#    sort_taxes = Cache('account_tax.sort_taxes')(sort_taxes)

    def compute(self, ids, price_unit, quantity):
        '''
        Compute taxes for price_unit and quantity.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        ids = self.sort_taxes(ids)
        taxes = self.browse(ids)
        res = self._unit_compute(taxes, price_unit)
        quantity = Decimal(str(quantity)) or Decimal('0.0')
        for row in res:
            row['base'] *= quantity
            row['amount'] *= quantity
        return res

Tax()

class TaxRate(ModelSQL, ModelView):
    'Tax Rate'
    _name = 'ekd.account.tax.rate'
    _description = __doc__

    tax = fields.Many2One('ekd.account.tax', 'Tax',
           required=True, select=1, ondelete='CASCADE')

    rate = fields.Numeric('Rate', digits=(16, Eval('rate_digits', 2)),
           help='In company\'s currency', depends=['type', 'rate_digits'])
    rate_digits = fields.Function(fields.Integer('Rate Digits'), 'get_rate_digits')

    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ], 'Type', required=True)
    less = fields.Numeric('Amount Less', digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'percentage')),
            }, help='In company\'s currency', depends=['type', 'currency_digits'])
    greater = fields.Numeric('Amount Greater', digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'percentage')),
            }, help='In company\'s currency', depends=['type', 'currency_digits'])

    active = fields.Boolean('Active')
    start_date = fields.Date('Start date')
    end_date = fields.Date('End date')

    def default_rate_digits(self):
        return 8

    def default_type(self):
        return 'percentage'

    def get_rate_digits(self, ids, name):
        res = {}.fromkeys(ids, 2)
        for tax in self.browse(ids):
            if tax.type == 'percentage':
                res[tax.id] = 8
        return res


TaxRate()
