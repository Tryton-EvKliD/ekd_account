# -*- coding: utf-8 -*-
##############################################################################
#
##############################################################################
'Book RU'
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import Eval
from decimal import Decimal
import datetime
import md5

_MOVE_STATES = {
    'readonly': "state == 'posted'",
    }
_MOVE_DEPENDS = ['state']

_LINE_STATES = {
        'readonly': "state == 'posted'",
        }
_LINE_DEPENDS = ['state']


class BookCash(ModelSQL, ModelView):
    'Book Cash Flow'
    _name = "ekd.book.cash"
    _description = __doc__
    _inherits = {'ekd.balances.finance': 'balances'}

    balances = fields.Many2One('ekd.balances.finance', 'Balances Cash', required=True, ondelete='CASCADE')
    income = fields.Function('get_amount_sum', string='Income', type='numeric', digits=(16, Eval('currency_digits', 2)))
    expense = fields.Function('get_amount_sum', string='expense', type='numeric', digits=(16, Eval('currency_digits', 2)))
    documents_cash = fields.One2Many('ekd.document.head.cash', 'balance', 'Document',
                            context={'date_account': Eval('date_balance'), 'cash_account': Eval('account')})
    currency_digits = fields.Function('get_currency_digits', type='integer', string='Currency Digits')

    def default_currency_digits(self):
        return 2

    def default_state(self):
        return 'draft'

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
                    if document.type_line == name and document.state == 'posted':
                        amount_sum += abs(document.amount)
                res[name][page.id] = amount_sum

#        raise Exception('name-', res, 'get_amount_move', ids)
        return res

    def on_change_account(self, values):
        if not values.get('company') or not values.get('date_balance') or not values.get('account'):
            return {}
        balance_ids = self.search([
                            ('company','=' , values.get('company')),
                            ('date_balance','<' , values.get('date_balance')),
                            ('account','=' , values.get('account'))], limit=1, order=[('date_balance', 'DESC')])
        if balance_ids:
            return { 'balance': self.browse(balance_ids[0]).balance_end }
        else:
            return {}

    def create(self, vals):
        res = super(BookCash, self).create(vals)
        old_id = self.browse(res)
        cursor.execute("UPDATE company_employee SET id=%s WHERE id=%s", (old_id.party.id, old_id.id ))
        res = self.browse(old_id.party.id)
        return res.id

BookCash()

class BookBank(ModelSQL, ModelView):
    'Book Bank Flow'
    _name = "ekd.book.bank"
    _description=__doc__

    company = fields.Many2One('company.company', 'Company', required=True,
                ondelete="RESTRICT")
    type_line = fields.Selection([('income','Income'),('expense','expense')], 'Type Operation', required=True)
    name = fields.Char('Name', size=None)
    description = fields.Text('Note')
    date_operation = fields.Date('Date Operation')
    bank_document = fields.Many2One('ekd.document.bank', 'Document Cash')
    bank_account = fields.Many2One('ekd.account', 'Cash Account', required=True,
                domain=[('kind', '!=', 'view')],
                select=1)
    document = fields.Many2One('ekd.document', 'Base Document')
    corr_account = fields.Many2One('ekd.account', 'Credit Account', required=True,
                domain=[('kind', '!=', 'view')],
                select=1)
    from_to_party = fields.Many2One('party.party', 'From Party')

    corr2_account = fields.Many2One('ekd.account', 'Credit Account', required=True,
                domain=[('kind', '!=', 'view')],
                select=1)
    analytic = fields.Many2One('ekd.account.analytic', 'Debit analytic account')
    income = fields.Numeric('Income', digits=(16, Eval('currency_digits', 2)))
    expense = fields.Numeric('expense', digits=(16, Eval('currency_digits', 2)))
    amount_currency = fields.Numeric('Amount in currency', digits=(16, Eval('second_currency_digits', 2)))
    currency = fields.Many2One('currency.currency','Currency')
    currency_digits = fields.Function('get_currency_digits', type='integer',
            string='Currency Digits')
    second_currency_digits = fields.Function('get_currency_digits',
            type='integer', string='Second Currency Digits', on_change_with=['currency'])
    state = fields.Selection([('draft','Draft'), ('posted','Posted'), ('error','Error'), ('deleted','Deleted') ], 'State', required=True)
    book = fields.One2Many('ekd.document.head.cash', 'move', 'Line Finance',
                states=_MOVE_STATES, depends=_MOVE_DEPENDS,
                context="{'company': company, 'period': period, 'date_transaction': date_transaction}")
    line = fields.One2Many('ekd.account.move.line', 'move', 'Account Entry Lines',
                states=_MOVE_STATES, depends=_MOVE_DEPENDS,
                context="{'company': company, 'period': period, 'date_transaction': date_transaction}")
    deleting = fields.Boolean('Flag deleting', readonly=True)

    def default_state(self):
        return 'draft'

    def default_date_operation(self):
        period_obj = self.pool.get('ekd.period')
        date_obj = self.pool.get('ir.date')
        period = self.default_period()
        if period:
            period = period_obj.browse(period)
            return period.start_date
        return date_obj.today()

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

BookBank()

class BookOpen(Wizard):
    'Book Open'
    _name = 'ekd.book.cash.open'
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
        book_cash_obj = self.pool.get('ekd.book.cash')
        context = Transaction().context
        act_window_id = model_data_obj.get_id('ekd_document', 'act_documents_cash_form')
        page_cash = book_cash_obj.browse(data['id'])
        res = act_window_obj.read(act_window_id)
        res['pyson_domain'] = [('balance', '=', data['id']),]
        res['pyson_domain'] = PYSONEncoder().encode(res['pyson_domain'])
        res['pyson_context'] = PYSONEncoder().encode({
                'balance': data['id'],
                'date_account': page_cash.date_balance,
                'cash_account': page_cash.account,
            })
        return res

BookOpen()


class BookCostFixed(ModelSQL, ModelView):
    'Book Fixed Costs'
    _name = "ekd.book.cost.fixed"
    _description=__doc__

BookCostFixed()

class BookCostGeneral(ModelSQL, ModelView):
    'Book General'
    _name = "ekd.book.cost.general"
    _description=__doc__

BookCostGeneral()

class BookCostProduction(ModelSQL, ModelView):
    'Book Production Cost'
    _name = "ekd.book.cost.production"
    _description=__doc__

BookCostProduction()
