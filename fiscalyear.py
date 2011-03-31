# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Fiscal Year'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.tools import datetime_strftime
from trytond.pyson import Equal, Eval, If, In, Get
import datetime
import time
from dateutil.relativedelta import relativedelta

STATES = {
    'readonly': Equal(Eval('state'), 'close'),
}

STATES_ADD = {
    'readonly': In(Eval('state'), ['close', 'open']),
}

DEPENDS = ['state']

class FiscalYear(ModelSQL, ModelView):
    'Fiscal Year'
    _name = 'ekd.fiscalyear'
    _description = __doc__

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True)
    name = fields.Char('Name', size=None, required=True, depends=DEPENDS)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=STATES,
            depends=DEPENDS)
    end_date = fields.Date('Ending Date', required=True, states=STATES,
            depends=DEPENDS)
    periods = fields.One2Many('ekd.period', 'fiscalyear', 'Periods',
            states=STATES, depends=DEPENDS)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)
    implementation_type = fields.Selection([
        ('shipping', 'Shipping'),
        ('payment', 'Payment'),
        ], 'Implementation type', states=STATES_ADD,
            depends=DEPENDS, required=True)
    cost_method = fields.Selection([
        ("fixed", "Fixed"),
        ("average", "Average"),
        ("fifo", "FIFO"),
        ("lifo", "LIFO"),
        ], 'Cost Method', states=STATES_ADD,
            depends=DEPENDS, required=True)

    system_tax = fields.Many2One('ekd.account.tax.group', 'Main System Tax', required=True)
    sequence_fiscalyear = fields.One2Many('ekd.fiscalyear.sequence', 
                            'fiscalyear', 'Template Sequence', states=STATES_ADD,
                            depends=DEPENDS)

    post_move_sequence = fields.Many2One('ir.sequence', 'Post Move Sequence',
            required=True, domain=[('code', '=', 'ekd.account.move.sequence'),
                ['OR',
                    ('company', '=', Eval("company")),
                    ('company', '=', False)]],
                    context={'code': 'ekd.account.move.sequence', 'company': Eval('company')},
            depends=['company'])
    post_move_line_sequence = fields.Many2One('ir.sequence', 'Post Move Line Sequence',
            domain=[('code', '=', 'ekd.account.move.line.sequence'),
                ['OR',
                    ('company', '=', Eval("company")),
                    ('company', '=', False)]],
                    context={'code': 'ekd.account.move.line.sequence', 'company': Eval('company')},
            depends=['company'])

    cash_book_sequence = fields.Many2One('ir.sequence', 'Cash Book Sequence',
                required=True, domain=[('code', '=', 'ekd.account.sequence.book.cash'),
                    ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False)]],
                    context={'code': 'ekd.account.sequence.book.cash', 'company': Eval('company')},
                depends=['company'])


    def __init__(self):
        super(FiscalYear, self).__init__()
        self._rpc.update({
            'create_period': True,
            'create_period_3': True,
            'set_state_draft': True,
            'close': True,
            'reopen': True,
        })
        self._constraints += [
            ('check_dates', 'fiscalyear_overlaps'),
        ]
        self._order.insert(0, ('start_date', 'ASC'))
        self._error_messages.update({
            'change_post_ru_move_sequence': 'You can not change ' \
                    'the post move sequence',
            'no_fiscalyear_date': 'No fiscal year defined for this date!',
            'fiscalyear_overlaps':
                'You can not have 2 fiscal years that overlaps!',
            'different_cash_book_sequence':
                'You must have different cash book sequence per fiscal year!',
            'different_bank_expense_sequence':
                'You must have different document expense for bank sequence per fiscal year!',
            'account_balance_not_zero':
                'The balance of the account "%s" must be zero!',
            'close_error': 'You can not close a fiscal year until ' \
                    'there is older fiscal year opened!',
            'reopen_error': 'You can not reopen a fiscal year until ' \
                    'there is more recent fiscal year closed!',
            })

    def default_state(self):
        return 'open'
    def default_cost_method(self):
        return 'average'
    
    def default_implementation_type(self):
        return 'payment'
    
    def default_company(self):
        return Transaction().context.get('company') or False

    def check_dates(self, ids):
        cr = Transaction().cursor
        for fiscalyear in self.browse(ids):
            cr.execute('SELECT id ' \
                    'FROM ' + self._table + ' ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND company = %s ' \
                        'AND id != %s',
                    (fiscalyear.start_date, fiscalyear.start_date,
                        fiscalyear.end_date, fiscalyear.end_date,
                        fiscalyear.start_date, fiscalyear.end_date,
                        fiscalyear.company.id, fiscalyear.id))
            if cr.fetchone():
                return False
        return True

    def write(self, ids, vals):
        vals = vals.copy()
        if 'periods' in vals:
            operator = ['delete', 'unlink_all', 'unlink', 'create', 'write',
                    'add', 'set']
            vals['periods'].sort(
                    lambda x, y: cmp(operator.index(x[0]), operator.index(y[0])))
        return super(FiscalYear, self).write(ids, vals)

    def delete(self, ids):
        period_obj = self.pool.get('ekd.period')
        period_ids = []
        for fiscalyear in self.browse(ids):
            period_ids.extend([x.id for x in fiscalyear.periods])
        period_obj.delete(period_ids)
        return super(FiscalYear, self).delete(ids)

    def set_state_open(self, ids):
        '''
         Set State Open
        '''
        return self.set_state(ids, 'open')

    def set_state_draft(self, ids):
        '''
         Set State Draft
        '''
        return self.set_state(ids, 'draft')

    def set_state_close(self, ids):
        '''
         Set State Draft
        '''
        return self.set_state(ids, 'close')

    def set_state(self, ids, state='draft'):
        '''
         Set State
        '''
        return self.write(ids, {'state': state})

    def create_period(self, ids, interval=1):
        '''
        Create periods for the fiscal years with month interval
        '''
        period_obj = self.pool.get('ekd.period')
        for fiscalyear in self.browse(ids):
            period_start_date = fiscalyear.start_date
            while period_start_date < fiscalyear.end_date:
                period_end_date = period_start_date + \
                            relativedelta(months=interval - 1) + \
                            relativedelta(day=31)
                if period_end_date > fiscalyear.end_date:
                    period_end_date = fiscalyear.end_date
                name = datetime_strftime(period_start_date, '%m-%Y')
                if name != datetime_strftime(period_end_date, '%m-%Y'):
                    name += ' - ' + datetime_strftime(period_end_date, '%Y-%m')
                period_obj.create({
                        'company': fiscalyear.company,
                        'name': name,
                        'code': name,
                        'start_date': period_start_date,
                        'end_date': period_end_date,
                        'fiscalyear': fiscalyear.id,
                        'post_move_sequence': fiscalyear.post_move_sequence.id,
                        'post_move_line_sequence': fiscalyear.post_move_line_sequence.id,
                        'cash_book_sequence': fiscalyear.cash_book_sequence.id,
                        'type': 'standard',
                        'state': 'open',
                        })
                period_start_date = period_end_date + relativedelta(days=1)
        return True

    def create_period_3(self, ids):
        '''
        Create periods for the fiscal years with 3 months interval
        '''
        return self.create_period(ids,
                interval=3)

    def find(self, company_id, date=None, exception=True,
            context=None):
        '''
        Return the fiscal year for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any fiscal year is found.
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today()
        ids = self.search([
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('company', '=', company_id),
            ], order=[('start_date', 'DESC')], limit=1)
        if not ids:
            if exception:
                self.raise_user_error('no_fiscalyear_date')
            else:
                return False
        return ids[0]

    def _process_account(self, account, fiscalyear):
        '''
        Process account for a fiscal year closed

        :param cursor: the database cursor
        :param user: the user id
        :param account: a BrowseRecord of the account
        :param fiscalyear: a BrowseRecord of the fiscal year closed
        :param context: the context
        '''
        currency_obj = self.pool.get('currency.currency')

#        if account.kind == 'view':
        return

    def close(self, fiscalyear_id):
        '''
        Close a fiscal year

        :param cursor: the database cursor
        :param user: the user id
        :param fiscalyear_id: the fiscal year id
        :param context: the context
        '''
        period_obj = self.pool.get('ekd.period')
        account_obj = self.pool.get('ekd.account')

        if isinstance(fiscalyear_id, list):
            fiscalyear_id = fiscalyear_id[0]

        fiscalyear = self.browse(fiscalyear_id)

        if self.search([
            ('end_date', '<=', fiscalyear.start_date),
            ('state', '=', 'open'),
            ('company', '=', fiscalyear.company.id),
            ]):
            self.raise_user_error('close_error')

        #First close the fiscalyear to be sure
        #it will not have new period created between.
        self.write(fiscalyear_id, {
            'state': 'close',
            })
        period_ids = period_obj.search([
            ('fiscalyear', '=', fiscalyear_id),
            ])
        period_obj.close(period_ids)

        ctx = context.copy()
        ctx['fiscalyear'] = fiscalyear_id
        if 'date' in context:
            del context['date']

        account_ids = account_obj.search([
            ('company', '=', fiscalyear.company.id),
            ])
        for account in account_obj.browse(account_ids):
            self._process_account(account, fiscalyear)

    def reopen(self, fiscalyear_id):
        '''
        Re-open a fiscal year

        :param cursor: the database cursor
        :param user: the user id
        :param fiscalyear_id: the fiscal year id
        :param context: the context
        '''
        if isinstance(fiscalyear_id, list):
            fiscalyear_id = fiscalyear_id[0]

        fiscalyear = self.browse(fiscalyear_id)

        if self.search([
            ('start_date', '>=', fiscalyear.end_date),
            ('state', '=', 'close'),
            ('company', '=', fiscalyear.company.id),
            ]):
            self.raise_user_error('reopen_error')

        self.write(fiscalyear_id, {
            'state': 'open',
            })

    def get_sequence_id(self, ids, template_id):
        sequence_obj = self.pool.get('ir.sequence')
        fiscalyear = self.browse(ids)
        sequence_tmp = False
        for sequence_line in fiscalyear.sequence_fiscalyear:
            if sequence_line.template.id == template_id:
                return sequence_obj.get_id(sequence_line.sequence.id)
            elif sequence_line.template.sequence.code == sequence_line.sequence.code:
                sequence_tmp = sequence_line.sequence.id
        if sequence_tmp:
            return sequence_obj.get_id(sequence_tmp)
        else:
            return False


FiscalYear()

class FiscalYearSequence(ModelSQL, ModelView):
    'Fiscal Year - Sequence'
    _name = 'ekd.fiscalyear.sequence'
    _description = __doc__

    fiscalyear = fields.Many2One('ekd.fiscalyear', 'Fiscal Year', required=True)
    template = fields.Many2One('ekd.document.template', 'Template', required=True)
    sequence = fields.Many2One('ir.sequence', 'Sequence', required=True)
    sequence_domain = fields.Function(fields.Char('Sequence Domain'), 'sequence_domain_get')

    def sequence_domain_get(self, ids, name):
        res = {}.fromkeys(ids, '')
        return res

FiscalYearSequence()

class CloseFiscalYearInit(ModelView):
    'Close Fiscal Year Init'
    _name = 'ekd.fiscalyear.close_fiscalyear.init'
    _description = __doc__
    close_fiscalyear = fields.Many2One('ekd.fiscalyear',
            'Fiscal Year to close',
            required=True,
            domain=[('state', '!=', Eval('close'))])
    transfer = fields.Boolean('Transfer Balance of Accounts')
    skip_closed = fields.Boolean('Skip closed balances')
    transfer_analytic = fields.Boolean('Transfer Balance of Analytic Accounts')
    skip_closed_analityc = fields.Boolean('Skip closed analityc balances')

    def default_transfer(self): 
        return True

    def default_transfer_analityc(self):
        return True

    def default_skip_closed(self):
        return True

    def default_skip_closed_analytic(self):
        return True

CloseFiscalYearInit()


class CloseFiscalYear(Wizard):
    'Close Fiscal Year'
    _name = 'ekd.fiscalyear.close_fiscalyear'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.fiscalyear.close_fiscalyear.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('close', 'Close', 'tryton-ok', True),
                ],
            },
        },
        'close': {
            'actions': ['_close'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _close(self, data):
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')

        fiscalyear_obj.close(data['form']['close_fiscalyear'])
        return {}

CloseFiscalYear()
