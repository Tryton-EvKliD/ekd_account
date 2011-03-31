#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder, Or, Not, Bool, Eval
from decimal import Decimal
import datetime

class Category(ModelSQL, ModelView):
    "Product Category"
    _name = "product.category"

    account_income = fields.Many2One('ekd.account', 'Account Income')
    account_expense = fields.Many2One('ekd.account', 'Account Expense')
    account_tax_input = fields.Many2One('ekd.account', 'Account Tax Input')
    account_tax_output = fields.Many2One('ekd.account', 'Account Tax Output')

    taxes = fields.Many2Many('product.category-ekd.account.tax',
                'category', 'tax', 'Taxes', domain=[('parent', '=', False)])

Category()

class CategoryTax(ModelSQL):
    'Category - Tax'
    _name = 'product.category-ekd.account.tax'
    _table = 'ekd_category_taxes_rel'
    _description = __doc__

    category = fields.Many2One('product.category', 'Category',
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('ekd.account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

CategoryTax()

class Template(ModelSQL, ModelView):
    _name = "product.template"

    account_category = fields.Boolean('Use Category\'s accounts',
                help='Use the accounts defined on the category')
    account_income = fields.Many2One('ekd.account', 'Account Income',
        states={
                 'invisible': Or(Not(Bool(Eval('company'))),
                    Bool(Eval('account_category'))),
        }, help='This account will be used instead of the one defined ' \
                    'on the category.', depends=['account_category'])
    account_expense = fields.Many2One('ekd.account', 'Account Expense',
        states={
                 'invisible': Or(Not(Bool(Eval('company'))),
                    Bool(Eval('account_category'))),
        }, help='This account will be used instead of the one defined ' \
                    'on the category.', depends=['account_category'])

    account_taxes_category = fields.Boolean('Use Category\'s accounts',
                help='Use the accounts defined on the category')
    account_tax_input = fields.Many2One('ekd.account', 'Account Tax Input',
        states={
                 'invisible': Or(Not(Bool(Eval('company'))),
                    Bool(Eval('taxes_category'))),
        }, help='This account will be used instead of the one defined ' \
                    'on the category.', depends=['taxes_category'])
    account_tax_output = fields.Many2One('ekd.account', 'Account Tax Output',
        states={
                 'invisible': Or(Not(Bool(Eval('company'))),
                    Bool(Eval('taxes_category'))),
        }, help='This account will be used instead of the one defined ' \
                    'on the category.', depends=['taxes_category'])

    taxes_category = fields.Boolean('Use Category\'s Taxes', help='Use the taxes '\
                'defined on the category')
    taxes = fields.Many2Many('product.template-ekd.account.tax',
                'product', 'tax', 'Taxes', domain=[('parent', '=', False)],
                states={
                     'invisible': Or(Not(Bool(Eval('company'))),
                         Bool(Eval('taxes_category'))),
                }, depends=['taxes_category'])
    
Template()

class TemplateProductTax(ModelSQL):
    'Product Template - Tax'
    _name = 'product.template-ekd.account.tax'
    _table = 'ekd_product_taxes_rel'
    _description = __doc__

    product = fields.Many2One('product.template', 'Product Template',
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('ekd.account.tax', 'Tax', ondelete='RESTRICT',
            required=True)

TemplateProductTax()

class Product(ModelSQL, ModelView):
    _name = "ekd.product"

    quantity = fields.Function(fields.Float('Quantity'), 'get_quantity',
            searcher='search_quantity')
    unit_price = fields.Function(fields.Numeric('Unit Price'), 'get_quantity',
            searcher='search_quantity')
    amount = fields.Function(fields.Numeric('Amount'), 'get_quantity',
            searcher='search_quantity')
#    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
#            'get_quantity', searcher='search_quantity')

    def get_quantity(self, ids, names):
        date_obj = self.pool.get('ir.date')
        period_obj = self.pool.get('ekd.period')
        balance_obj = self.pool.get('ekd.balances.product')
        res = {}
        context = Transaction().context
        #if not context.get('locations'):
        #    return dict((id, 0.0) for id in ids)

        for name in names:
            if name == 'quantity':
                res.setdefault(name, {}.fromkeys(ids, 0.0))
            elif name == 'unit_price':
                res.setdefault(name, {}.fromkeys(ids, Decimal('0.0')))
            elif name == 'amount':
                res.setdefault(name, {}.fromkeys(ids, Decimal('0.0')))
        return res


        if context.get('current_period'):
            current_period = context.get('current_period')

        if context.get('current_date'):
            current_period = period_obj.search([
                        ('start_date','<=', context.get('current_date')),
                        ('end_date','>=', context.get('current_date'))
                        ], limit=1)
        else:
            current_period = period_obj.search([
                        ('start_date','<=', date_obj.today()),
                        ('end_date','>=', date_obj.today()),
                        ], limit=1)
        if not current_period:
           raise Exception('Error', 'Period not find!')
        if isinstance(current_period, list):
            current_period = current_period[0]

        balance_ids = balance_obj.search([
                        ('id', 'in', ids),
                        ('period', '=', current_period)
                        ])

        if balance_ids:
            for balance in balance_obj.browse(balance_ids):
                for name in names:
                    if name == 'quantity':
                        res[name][balance.id] = balance.qbalance_end
                    elif name == 'unit_price':
                        res[name][balance.id] = balance.unit_price
                    elif name == 'amount':
                        res[name][balance.id] = balance.balance.balance_end
#                    elif name == 'forecast_quantity':

        return res

    def _search_quantity_eval_domain(self, line, domain):
        field, operator, operand = domain
        value = line.get(field)
        if value == None:
            return False
        if operator not in ("=", ">=", "<=", ">", "<", "!="):
            return False
        if operator == "=":
            operator= "=="
        return (eval(str(value) + operator + str(operand)))

    def search_quantity(self, name, domain=None):
        date_obj = self.pool.get('ir.date')
        context = Transaction().context
        if not (context and context.get('locations') and domain):
            return []

        if name == 'quantity' and \
                context.get('stock_date_end') and \
                context.get('stock_date_end') > \
                date_obj.today():

            context = context.copy()
            context['stock_date_end'] = date_obj.today()

        if name == 'forecast_quantity':
            context = context.copy()
            context['forecast'] = True
            if not context.get('stock_date_end'):
                context['stock_date_end'] = datetime.date.max

        pbl = self.products_by_location(
           location_ids=context['locations'], with_childs=True,
            skip_zero=False).iteritems()

        processed_lines = []
        for (location, product), quantity in pbl:
            processed_lines.append({'location': location, #XXX useful ?
                                    'product': product,
                                    name: quantity})

        res= [line['product'] for line in processed_lines \
                    if self._search_quantity_eval_domain(line, domain)]
        return [('id', 'in', res)]

    def view_header_get(self, value, view_type='form'):
        context = Transaction().context
        if not context.get('locations'):
            return value
        location_obj = self.pool.get('stock.location')
        locations = location_obj.browse(context.get('locations'))
        return value + " (" + ",".join(l.name for l in locations) + ")"

Product()
