# -*- coding: utf-8 -*-..
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Period'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.pyson import Equal, Eval
import datetime

_STATES = {
    'readonly': Equal(Eval('state'), 'close'),
}


class Period(ModelSQL, ModelView):
    'Period'
    _name = 'ekd.period'
    _description = __doc__

    company = fields.Many2One('company.company', 'Period of Company',
            required=True, states=_STATES, select=1)
    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    start_date = fields.Date('Starting Date', required=True, states=_STATES,
            select=1)
    end_date = fields.Date('Ending Date', required=True, states=_STATES,
            select=1)
    fiscalyear = fields.Many2One('ekd.fiscalyear', 'Fiscal Year',
            required=True, states=_STATES, select=1)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)
    type = fields.Selection([
        ('standard', 'Standard'),
        ('adjustment', 'Adjustment'),
        ('opening', 'Opening'),
        ('closed', 'Closed'),
        ], 'Type', required=True, states=_STATES, select=1)

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
                domain=[('code', '=', 'ekd.account.sequence.book.cash'),
                    ['OR',
                    ('company', '=', Eval('company')),
                    ('company', '=', False)]],
                    context={'code': 'ekd.account.sequence.book.cash', 'company': Eval('company')},
                depends=['company'])

    def __init__(self):
        super(Period, self).__init__()
        self._constraints += [
            ('check_dates', 'periods_overlaps'),
            ('check_fiscalyear_dates', 'fiscalyear_dates'),
            ]
        self._order.insert(0, ('company', 'ASC'))
        self._order.insert(1, ('start_date', 'ASC'))
        self._order.insert(2, ('end_date', 'ASC'))

        self._error_messages.update({
            'no_period_date': 'No period defined for this date!',
            'modify_del_period_moves': 'You can not modify/delete ' \
                    'a period with moves!',
            'create_period_closed_fiscalyear': 'You can not create ' \
                    'a period on a closed fiscal year!',
            'open_period_closed_fiscalyear': 'You can not open ' \
                    'a period from a closed fiscal year!',
            'close_period_non_posted_move': 'You can not close ' \
                    'a period with non posted moves!',
            'periods_overlaps': 'You can not have two overlapping periods!',
            'fiscalyear_dates': 'The period dates must be in ' \
                    'the fiscal year dates',
            })

    def default_state(self):
        return 'open'

    def default_type(self):
        return 'standard'

    def check_dates(self, ids):
        cr = Transaction().cursor
        for period in self.browse(ids):
            if period.type != 'standard':
                continue
            cr.execute('SELECT id ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE ((start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date <= %s AND end_date >= %s) ' \
                            'OR (start_date >= %s AND end_date <= %s)) ' \
                        'AND fiscalyear = %s ' \
                        'AND type = \'standard\' ' \
                        'AND id != %s',
                    (period.start_date, period.start_date,
                        period.end_date, period.end_date,
                        period.start_date, period.end_date,
                        period.fiscalyear.id, period.id))
            if cr.fetchone():
                return False
        return True

    def check_fiscalyear_dates(self, ids):
        for period in self.browse(ids):
            if period.start_date < period.fiscalyear.start_date \
                    or period.end_date > period.fiscalyear.end_date:
                return False
        return True

    def find(self, company_id, date=None, exception=True,
            test_state=True):
        '''
        Return the period for the company_id
            at the date or the current date.
        If exception is set the function will raise an exception
            if any period is found.

        :param cursor: the database cursor
        :param user: the user id
        :param company_id: the company id
        :param date: the date searched
        :param exception: a boolean to raise or not an exception
        :param test_state: a boolean if true will search on non-closed periods
        :param context: the context
        :return: the period id found or False
        '''
        date_obj = self.pool.get('ir.date')

        if not date:
            date = date_obj.today()
        clause = [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ('fiscalyear.company', '=', company_id),
            ('type', '=', 'standard'),
            ]
        if test_state:
            clause.append(('state', '!=', 'close'))
        ids = self.search(clause, order=[('start_date', 'DESC')],
                limit=1)
        if not ids:
            if exception:
                self.raise_user_error('no_period_date')
            else:
                return False
        return ids[0]

    def _check(self, ids):
        move_obj = self.pool.get('ekd.account.move')
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_ids = move_obj.search([
            ('period', 'in', ids),
            ], limit=1)
        if move_ids:
            self.raise_user_error('modify_del_period_moves')
        return

    def search(self, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        args = args[:]
        def process_args(args):
            i = 0
            while i < len(args):
                if isinstance(args[i], list):
                    process_args(args[i])
                if isinstance(args[i], tuple) \
                        and args[i][0] in ('start_date', 'end_date') \
                        and isinstance(args[i][2], (list, tuple)):
                    if not args[i][2][0]:
                        args[i] = ('id', '!=', '0')
                    else:
                        period = self.browse(args[i][2][0],
                                )
                        args[i] = (args[i][0], args[i][1], period[args[i][2][1]])
                i += 1
        process_args(args)
        return super(Period, self).search(args, offset=offset,
                limit=limit, order=order, count=count,
                query_string=query_string)

    def create(self, vals):
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        vals = vals.copy()
        if vals.get('fiscalyear'):
            fiscalyear = fiscalyear_obj.browse(vals['fiscalyear'])
            if fiscalyear.state == 'close':
                self.raise_user_error('create_period_closed_fiscalyear')
        return super(Period, self).create(vals)

    def write(self, ids, vals):
        move_obj = self.pool.get('ekd.account.move')
        for key in vals.keys():
            if key in ('start_date', 'end_date', 'fiscalyear'):
                self._check(ids)
                break
        if vals.get('state') == 'open':
            for period in self.browse(ids):
                if period.fiscalyear.state == 'close':
                    self.raise_user_error('open_period_closed_fiscalyear')
        return super(Period, self).write(ids, vals)

    def delete(self, ids):
        self._check(ids)
        return super(Period, self).delete(ids)

    def close(self, ids):
        move_obj = self.pool.get('ekd.account.move')

        if isinstance(ids, (int, long)):
            ids = [ids]

        #First close the period to be sure
        #it will not have new journal.period created between.
        self.write(ids, {
            'state': 'close',
            })
        return

    def transfer(self, vals=None):
        '''
        Перенос остатков за определённые периоды
        1. за 1 период 
        2. или множеств
        periods - словарь идентификаторов периодов
        '''
        if vals.get('period_start') is None\
                and vals.get('company') is None and vals.get('periods'):
            raise Exception('Period start or Company - unknown!')

        period_begin = self.browse(vals.get('period_start'))

        if vals.get('period_end') is None:
            date_next = period_begin.end_date + datetime.timedelta(days=1)
            period_id = self.search([
                            ('company','=', period_begin.company.id),
                            ('start_date','<=', date_next),
                            ('end_date','>=', date_next),
                            ('type','=','standard'),
                            ], order=[('start_date','ASC'),('end_date','ASC')])
            period_end = self.browse(period_id[0])
            vals['periods'] = [ period_begin.id, period_end.id]

        else:
            period_end = self.browse(vals.get('period_end'))
            vals['periods'] = self.search([
                            ('company','=', vals.get('company')),
                            ('start_date','>=', period_begin.start_date.strftime('%Y-%m-%d')),
                            ('end_date','<=', period_end.end_date.strftime('%Y-%m-%d')),
                            ('type','=','standard')
                            ], order=[('start_date','ASC'),('end_date','ASC')])

        for period in self.browse(vals['periods']):
            if period.state == "close":
                raise Exception('This is period is close', period.name )

        bal_account_obj = self.pool.get('ekd.balances.account')
#        bal_analytic_obj = self.pool.get('ekd.balances.analytic')
#        bal_party_obj = self.pool.get('ekd.balances.party')
#        bal_product_obj = self.pool.get('ekd.balances.product')

        if bal_account_obj.transfer_balances(vals):
            pass
#        if bal_analytic_obj.transfer(vals):
#            pass
#        if bal_party_obj.transfer(vals):
#            pass
#        if bal_product_obj.transfer(vals):
#            pass

Period()

class ClosePeriodInit(ModelView):
    'Close Period Init'
    _name = 'ekd.period.close_period.init'
    _description = __doc__

    transfer = fields.Boolean('Transfer Balance of Accounts')
    skip_closed = fields.Boolean('Skip closed balances')
    transfer_analytic = fields.Boolean('Transfer Balance of Analytic Accounts')
    skip_closed_analytic = fields.Boolean('Skip closed analityc balances')

    def default_transfer(self):
        return True

    def default_transfer_analytic(self):
        return True

    def default_skip_closed(self):
        return True

    def default_skip_closed_analytic(self):
        return True

ClosePeriodInit()


class ClosePeriod(Wizard):
    'Close Period'
    _name = 'ekd.period.close_period'
    states = {
        'init': {
                'result': {
                        'type': 'form',
                        'object': 'ekd.period.close_period.init',
                        'state': [
                                ('end', 'Cancel', 'tryton-cancel'),
                                ('open', 'Close Period', 'tryton-ok', True),
                                ],
                        },
                },
        'open': {
                'result': {
                        'type': 'action',
                        'action': '_close',
                        'state': 'end',
                            },
                },
            }


    def _close(self, data):
        period_obj = self.pool.get('ekd.period')
        if data['form']['transfer']:
            if len(data['ids']) == 1:
                period_obj.transfer({
                        'company': period_obj.browse(data['ids'][0]).company.id,
                        'periods': data['ids'],
                        'period_start':data['ids'][0],
                        'transfer':data['form']['transfer'],
                        'transfer_analytic':data['form']['transfer_analytic'],
                        'skip_closed':data['form']['skip_closed'],
                        'skip_closed_analytic':data['form']['skip_closed_analytic'],
                        })

            elif len(data['ids']) == 2:
                period_obj.transfer({
                        'company': period_obj.browse(data['ids'][0]).company.id,
                        'periods': data['ids'],
                        'period_start':data['ids'][0],
                        'period_end': data['ids'][1],
                        'transfer': data['form']['transfer'],
                        'transfer_analytic':data['form']['transfer_analytic'],
                        'skip_closed':data['form']['skip_closed'],
                        'skip_closed_analytic':data['form']['skip_closed_analytic'],
                        })
            else:
                period_obj.transfer({
                        'company': period_obj.browse(data['ids'][0]).company.id,
                        'periods': data['ids'],
                        'transfer':data['form']['transfer'],
                        'transfer_analytic':data['form']['transfer_analytic'],
                        'skip_closed':data['form']['skip_closed'],
                        'skip_closed_analytic':data['form']['skip_closed_analytic'],
                        })

        period_obj.close(data['ids'])
        return {}

ClosePeriod()

class TransferBalanceInit(ModelView):
    'Transfer balance account Init'
    _name = 'ekd.period.transfer.init'
    _description = __doc__
    company = fields.Many2One('company.company', 'Company') 
    period_start = fields.Many2One('ekd.period',  'Period Balance Begin')
    period_end = fields.Many2One('ekd.period',  'Period Balance End')
    transfer = fields.Boolean('Transfer Balance of Accounts')
    skip_closed = fields.Boolean('Skip closed balances')
    transfer_analytic = fields.Boolean('Transfer Balance of Analytic Accounts')
    skip_closed_analytic = fields.Boolean('Skip closed analytic balances')

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_period_start(self):
        context = Transaction().context
        if context.get('period_start'):
            return context.get('period_start')
        elif context.get('period_current'):
            return context.get('period_current')
        else:
            return False

    def default_period_end(self):
        return Transaction().context.get('period_start') or False

    def default_transfer(self):
        return True

    def default_transfer_analytic(self):
        return True

    def default_skip_closed(self):
        return True

    def default_skip_closed_analytic(self):
        return True

TransferBalanceInit()

class TransferBalanceAccount(Wizard):
    'Transfer Balance Account'
    _name = 'ekd.period.transfer'
    states = {
        'init': {
                'result': {
                        'type': 'form',
                        'object': 'ekd.period.transfer.init',
                        'state': [
                                ('end', 'Cancel', 'tryton-cancel'),
                                ('open', 'Transfer', 'tryton-ok', True),
                                ],
                        },
                },
        'open': {
                'result': {
                        'type': 'action',
                        'action': '_action_transfer',
                        'state': 'end',
                            },
                },
            }

    def _action_transfer(self, data):
        period_obj = self.pool.get('ekd.period')
#        if data['ids']:
#            period_obj.transfer({
#                    'company': data['form']['company'],
#                    'periods': data['ids'],
#                    'period_start': data['form']['period_start'],
#                    'period_end': data['form']['period_end'],
#                        })
#        else:
        period_obj.transfer({
                    'company': data['form']['company'],
                    'period_start': data['form']['period_start'],
                    'period_end': data['form']['period_end'],
                    'transfer':data['form']['transfer'],
                    'skip_closed':data['form']['skip_closed'],
                    'transfer_analytic':data['form']['transfer_analytic'],
                    'skip_closed_analytic':data['form']['skip_closed_analytic'],
                        })
        return {}

TransferBalanceAccount()

class ReOpenPeriod(Wizard):
    'Re-Open Period'
    _name = 'ekd.period.reopen_period'
    states = {
        'init': {
            'actions': ['_reopen'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _reopen(self, data):
        period_obj = self.pool.get('ekd.period')
        period_obj.write(data['ids'], {
            'state': 'open',
            })
        return {}

ReOpenPeriod()
