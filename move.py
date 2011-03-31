# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2009-today Dmitry klimanov
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#NOTE: Операционный журнал
##############################################################################
'MoveRU'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import Greater, Equal, Eval, Get, And, Or, Not, In, Bool, PYSONEncoder
from account import _PARTY, _PRODUCT, _DEPRECATION, _OTHER, _MONEY
from decimal import Decimal
import datetime
try:
    import hashlib
except ImportError:
    hashlib = None
    import md5

_MOVE_STATES = {
    'readonly': Equal(Eval('state'), 'posted'),
    }
_MOVE_DEPENDS = ['state', 'date_operation']

_LINE_STATES = {
        'readonly': Equal(Eval('state'), 'posted'),
        }
_LINE_DEPENDS = ['state']

_DT_PARTY_STATES = {
        'invisible': Not(In(Eval('dt_kind_analytic', ''), _PARTY+_PRODUCT)),
        }

_CT_PARTY_STATES = {
        'invisible': Not(In(Eval('ct_kind_analytic', ''), _PARTY+_PRODUCT)),
        }

_DT_PRODUCT_STATES = {
        'invisible': Not(In(Eval('dt_kind_analytic', ''), _PRODUCT)),
        }

_CT_PRODUCT_STATES = {
        'invisible': Not(In(Eval('ct_kind_analytic', ''), _PRODUCT)),
        }

_ACC_PRODUCT_STATES = {
        'required': Bool(Eval('product')),
        'invisible': And(Not(In(Eval('dt_kind_analytic', ''), _PRODUCT)),
            Not(In(Eval('ct_kind_analytic', ''), _PRODUCT))),
        }

class MoveRUMarker(ModelSQL, ModelView):
    'Marker for entries'
    _name = "ekd.account.move.marker"
    _description=__doc__

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True,
                ondelete="RESTRICT")
    name = fields.Char('Name', size=None)
    note = fields.Text('Note')
    active = fields.Boolean('Active')

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_active(self):
        return True

MoveRUMarker()

class MoveRU(ModelSQL, ModelView):
    'Business operations russian standart'
    _name = "ekd.account.move"
    _description=__doc__
    _pool_default_line = {}

    company = fields.Many2One('company.company', 'Company', required=True, readonly=True,
                ondelete="RESTRICT")

    name = fields.Char('Name', size=None)
    note = fields.Text('Note')
    marker = fields.Many2One('ekd.account.move.marker', 'Additional marker')
    period = fields.Function(fields.Many2One('ekd.period', 'Account Period'),\
                    'get_period_move', searcher='search_move_field')
    period_open = fields.Function(fields.Boolean('Period open'), 'get_period_move')
    post_move = fields.Integer('Move Sequence', help='Also known as Folio Number')
    post_date = fields.Date('Post Date', readonly=True)
    date_operation = fields.Date('Date Operation')
    from_party = fields.Many2One('party.party', 'From Party')
    to_party = fields.Many2One('party.party', 'To Party')
    #template_move = fields.Many2One('ekd.account.move.template', 'Template move')
    document = fields.Many2One('ekd.document', 'Document')
    document_ref = fields.Reference('Base for entry', 
                        selection='documents_get', select=1,
                        on_change=['document_ref'])
    document2 = fields.Many2One('ekd.document', 'Document for Party')
    document2_ref = fields.Reference('Base for party', selection='documents2_get', select=1)
    amount = fields.Function(fields.Numeric('Total Entry'), 'get_amount_move')
    amount_currency = fields.Function(fields.Numeric('Total Entry'), 'get_amount_move')
    state = fields.Selection([
                            ('draft','Draft'),
                            ('posted','Posted'),
                            ('canceled','Canceled'),
                            ('deleted','Deleted')
                            ], 'State', required=True, readonly=True)
    lines = fields.One2Many('ekd.account.move.line', 'move', 'Account Entry Lines',
                states=_MOVE_STATES, depends=_MOVE_DEPENDS,
                context={'company': Eval('company'),
                        'date_operation': Eval('date_operation'),
                        'ct_party': Eval('from_party'),
                        'dt_party': Eval('to_party'),
                        'amount': Eval('amount'),
                        })
    id_1c = fields.Char("ID import from 1C", size=None, select=1)
    deleted = fields.Boolean('Flag deleting', readonly=True)
    dt_account = fields.Function(fields.Char('Account Debit'), 'get_account', searcher="search_account")
    ct_account = fields.Function(fields.Char('Account Credit'), 'get_account', searcher="search_account")

    def __init__(self):
        super(MoveRU, self).__init__()
#        self._constraints += [
#            ('check_company', 'company_in_move'),
#            ('check_date', 'date_outside_period'),
#            ]
        self._rpc.update({
            'button_post': True,
            'button_cancel': True,
            'button_restore': True,
            })

        self._order.insert(0, ('date_operation', 'ASC'))
        self._order.insert(1, ('post_move', 'ASC'))

        self._error_messages.update({
            'del_posted_move': 'You can not delete posted moves!',
            'post_empty_move': 'You can not post an empty move!',
            'post_unbalanced_move': 'You can not post an unbalanced move!',
            'modify_posted_move': 'You can not modify a posted move ' \
            'in this journal!',
            'company_in_move': 'You can not create lines on accounts\n' \
            'of different companies in the same move!',
            'date_outside_period': 'You can not create move ' \
            'with a date outside the period!',
            'period_not_find': "This period don't find",
            'period_is_close': 'This Period is closed',
            'delete_posted_line': "Warning! Find line entry with state 'posted'.",
            'delete_posted_move': "This entry state is 'posted'!\n Are you sure?",
            })

#
#	DEFAULT VALUES
#

    def default_get(self, fields, with_rec_name=True):
        context = Transaction().context
        res = super(MoveRU, self).default_get(fields, with_rec_name=True)
        if 'company' in fields:
            res['company'] = context.get('company') or False
        if 'state' in fields:
            res['state'] = context.get('state') or 'draft'
        if 'document_ref' in fields:
            res['document_ref'] = context.get('document_ref') or False
        if 'document2_ref' in fields:
            res['document2_ref'] = context.get('document2_ref') or False
        if 'from_party' in fields:
            res['from_party'] = context.get('from_party') or False
        if 'to_party' in fields:
            res['to_party'] = context.get('to_party') or False
        if 'name' in fields:
            res['name'] = context.get('name') or False
        if 'note' in fields:
            res['note'] = context.get('note') or False
        if 'date_operation' in fields:
            if context.get('date_operation'):
                res['date_operation'] = context.get('date_operation')
            elif context.get('current_date'):
                res['date_operation'] = context.get('current_date')
            else:
                res['date_operation'] = datetime.datetime.now()
        return res

#
#	GET VALUES
#
    def get_account(self, ids, names):
        return {'dt_account':{}.fromkeys(ids, ''),'ct_account':{}.fromkeys(ids, '')}

    def view_header_get(self, value, view_type='form'):
        context = Transaction().context
        if view_type == 'tree':
            return u' %s - с %s по %s'%(value, context.get('start_period'), context.get('end_period'))
        else:
            return u' %s - с %s по %s'%(value, context.get('start_period'), context.get('end_period'))

    def get_amount_move(self, ids, names):
#        res={}.fromkeys(ids, Decimal('0.0'))
        res={}
        amount = Decimal('0.0')
        amount_currency = Decimal('0.0')
        for move in self.browse(ids):
            for line in move.lines:
                if move.state == line.state:
                    amount += line.amount
                    amount_currency += line.amount_currency
            for name in names:
                res.setdefault(name, {})
                if name == 'amount':
                    res[name][move.id] = amount
                elif name == 'amount_currency':
                    res[name][move.id] = amount_currency
            amount = Decimal('0.0')
            amount_currency = Decimal('0.0')
        return res

    def check_context(self, ids, names):
        pass

    def search_rec_name(self, name, clause):
        ids = self.search(['OR',
            ('reference',) + clause[1:],
            (self._rec_name,) + clause[1:],
            ])
        return [('id', 'in', ids)]

    def search_move_field(self, name, clause):
        if name == 'period':
            pole, dif, period_id = clause
            period_obj = self.pool.get('ekd.period')
            period = period_obj.browse(period_id)
            #raise Exception(str(period_id), str(period.start_date), str(period.end_date))
            ids = self.search([
                    ('company','=', period.fiscalyear.company.id),
                    ('date_operation','>=', period.start_date),
                    ('date_operation','<=', period.end_date),])
            return [('id', 'in', ids)]

    def search_account(self, name, clause):
        line_obj = self.pool.get('ekd.account.move.line')
        account_obj = self.pool.get('ekd.account')
        pole, dif, code = clause
        account_ids = account_obj.search([
                        ('company','=',Transaction().context.get('company')),
                        ('code', dif, code)])
        if name == 'dt_account':
            lines = line_obj.search([('dt_account','in', account_ids)])
            #raise Exception(str([('id','in', [ x['move'] for x in line_obj.read(lines, ['move']]))]))
            return [('id','in', [ x['move'] for x in line_obj.read(lines, ['move'])])]
        elif name == 'ct_account':
            lines = line_obj.search([('ct_account','in', account_ids)])
            return [('id','in', [ x['move'] for x in line_obj.read(lines, ['move'])])]

    def get_period_move(self, ids, names):
        period_obj = self.pool.get('ekd.period')
        res={}
        for move in self.browse(ids):
            period_id = period_obj.search([
                            ('company','=',move.company.id),
                            ('start_date','<=',move.date_operation),
                            ('end_date','>=',move.date_operation)
                            ],limit=1)

            if period_id:
                if isinstance(period_id, list):
                    period_id = period_id[0]
                for name in names:
                    res.setdefault(name, {})
                    if name == 'period':
                        res[name][move.id] = period_id
                    elif name == 'period_open':
                        if period_obj.browse(period_id).state == 'open':
                            res[name][move.id] = True
                        else:
                            res[name][move.id] = False
            else:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(move.id, False)


        return res

    def documents_get(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.move'),
                    ('pole', '=', 'document_ref'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
#        res.append([' ', ' '])
        return res

    def documents2_get(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.move'),
                    ('pole', '=', 'document2_ref'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
#        res.append([' ', ' '])
        return res

    def on_change_document_ref(self, vals):
        model, _model_id = vals.get('document_ref').split(',',1)
        model_obj = self.pool.get(model)
        if _model_id != '0':
            model_id = model_obj.browse(int(_model_id))
            return {
                'date_operation': model_id.date_account,
                'document': model_id.id,
                'from_party': model_id.from_party.id,
                'to_party': model_id.to_party.id,
                'amount':  model_id.amount,
                'note':  model_id.note,
                }
        else:
            return {}

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        context = Transaction().context
        default['state'] = 'draft'
        default['date_operation'] = context.get('current_date', datetime.datetime.now().strftime('%Y-%m-%d'))
        res = super(MoveRU, self).copy(ids, default=default)
        return res

    def create(self, vals):
        #if vals.get('document_ref') and len(vals.get('document_ref')) < 7:
        #    vals['document_ref']=False
        #elif vals.get('document_ref'):
        #    model, vals['document']=vals['document_ref'].split(',')

        #if vals.get('document2_ref') and len(vals.get('document2_ref')) < 7:
        #    vals['document2_ref']=False
        #elif vals.get('document2_ref'):
        #    model, vals['document2']=vals['document2_ref'].split(',')
        #raise Exception(str(vals))
        #raise Exception(str(vals))
        new_id = super(MoveRU, self).create(vals)
        return new_id


    def write(self, id, vals):
        if vals.get('document_ref') and len(vals.get('document_ref')) < 7:
            vals['document_ref']=False
        elif vals.get('document_ref'):
            model, vals['document']=vals['document_ref'].split(',')
        if vals.get('document2_ref') and len(vals.get('document2_ref')) < 7:
            vals['document2_ref']=False
        elif vals.get('document2_ref'):
            model, vals['document2']=vals['document2_ref'].split(',')
        #raise Exception(str(vals))
        if 'lines' in vals.keys():
            for line_move in vals.get('lines'):
                if line_move[0] == 'write':
                    if line_move[2].get('ct_analytic_accounts'):
                        anl_ct_obj = self.pool.get('ekd.account.move.line.analytic_ct')
                        for analytic_line in line_move[2].get('ct_analytic_accounts'):
                            if analytic_line[0] == 'delete':
                                anl_ct_obj.delete(analytic_line[1])
                                line_move[2].get('ct_analytic_accounts').remove(analytic_line)
                                #raise Exception(str(vals))
                                break
                            
                    elif line_move[2].get('dt_analytic_accounts'):
                        anl_dt_obj = self.pool.get('ekd.account.move.line.analytic_dt')
                        for analytic_line in line_move[2].get('dt_analytic_accounts'):
                            if analytic_line[0] == 'delete':
                                anl_dt_obj.delete(analytic_line[1])
                                line_move[2].get('dt_analytic_accounts').remove(analytic_line)
                                break
                    
        #raise Exception(str(vals))
        res = super(MoveRU, self).write(id, vals)
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        move_line_obj = self.pool.get('ekd.account.move.line')
        for move in self.browse(ids):
            if move.state == 'posted' and move.period == 'close':
                self.raise_user_error('period_is_close')
            if move.lines:
                move_line_ids = [x.id for x in move.lines]
                move_line_obj.delete(move_line_ids)
            if move.state == 'deleted' and move.deleted:
                return super(MoveRU, self).delete(ids)
            else:
                return move.write(ids, {'state':'deleted', 'deleted':True})

    def button_post(self, ids):
        return self.post(ids)

    def button_cancel(self, ids):
        return self.post_cancel(ids)

    def button_restore(self, ids):
        return self.restore(ids)

    def post(self, ids):
        lines_obj = self.pool.get('ekd.account.move.line')
        sequence_obj = self.pool.get('ir.sequence')

        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.browse(ids):
            if not move.lines:
                self.raise_user_error('post_empty_move')
            line_ids = []
            for line in move.lines:
                if line.state in ('draft', 'canceled'):
                    if line.date_operation != move.date_operation:
                        lines_obj.write(line.id, {'date_operation': move.date_operation})
                    line_ids.append(line.id)
            line.post(line_ids)
            if move.post_move:
                self.write(move.id, {
                    'state': 'posted',
                    'post_date': datetime.datetime.now().strftime('%Y-%m-%d'),
                    })
            else:
                reference = sequence_obj.get_id(move.period.post_move_sequence.id)
                self.write(move.id, {
                    'post_move': reference,
                    'state': 'posted',
                    'post_date': datetime.datetime.now().strftime('%Y-%m-%d'),
                    })
        return

    def post_cancel(self, ids):
        lines_obj = self.pool.get('ekd.account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.browse(ids):
            if move.period.state == 'open':
                line_ids=[]
                for line in move.lines:
                    if line.state == 'posted':
                        line_ids.append(line.id)
                lines_obj.post_cancel(line_ids)
                self.write(move.id, {
                    'state': 'canceled',
                    })
            else:
                self.raise_user_error('period_is_close')
        return

    def restore(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        moves = self.browse(ids)
        for move in moves:
            for line in move.lines:
                if line.state == 'deleted':
                    line.restore(line.id)
            self.write(move.id, {
                'state': 'draft',
                })

        return

MoveRU()

class LineRU(ModelSQL, ModelView):
    "Lines of business operations russian standart"
    _name="ekd.account.move.line"
    _description=__doc__
    _default_context = {}

    company = fields.Many2One('company.company', 'Company', required=True,
                ondelete="RESTRICT", readonly=True)
    name = fields.Function(fields.Char('Name', size=None, states=_MOVE_STATES, 
                        depends=_MOVE_DEPENDS), 'get_move_field', 
                        setter='set_move_field', searcher='search_move_field')
    name_line = fields.Char('Name', size=None, states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    post_line = fields.Integer('Line Sequence', readonly=True)
    post_date = fields.Date('Post Date', readonly=True)
    move = fields.Many2One('ekd.account.move', 'Head Entries', ondelete="CASCADE", states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    date_operation = fields.Date('Operation Date', states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    dt_account = fields.Many2One('ekd.account', 'Debit Account',
            states={ 'required': Equal(Eval('ct_kind'),'balance'),
                     'readonly': Equal(Eval('state'), 'posted'),}, depends=_MOVE_DEPENDS,
            domain=[('kind', 'not in', ['view', 'section']),
                    ('company','=', Eval('company'))
                    ],
            on_change=['dt_account', 'dt_analytic_accounts'], select=1)
    dt_analytic_accounts = fields.One2Many('ekd.account.move.line.analytic_dt','move_line','Analytic for Account Debit')
    dt_analytic_01 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='First Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 1, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_02 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Second Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 2, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_03 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Third Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 3, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_04 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Fourth Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 4, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_05 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Fifth Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 5, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_06 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Sixth Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 6, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')
    dt_analytic_07 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Seventh Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 7, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_dt', setter='set_analytic_dt')

    ct_account = fields.Many2One('ekd.account', 'Credit Account',
            states={ 'required': Equal(Eval('dt_kind'),'balance'), 
                    'readonly': Equal(Eval('state'), 'posted'),},
            domain=[('kind', 'not in', ['view', 'section']),
                    ('company','=', Eval('company'))
                    ],
            on_change=['ct_account', 'ct_analytic_accounts'], select=1)
    ct_analytic_accounts = fields.One2Many('ekd.account.move.line.analytic_ct','move_line','Analytic for Account Credit')
    ct_analytic_01 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='First Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 1, True)), 
                                'readonly': Equal(Eval('state'), 'posted'),},
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_02 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Second Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 2, True)), 
                                'readonly': Equal(Eval('state'), 'posted'),},
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_03 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Third Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 3, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_04 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Fourth Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 4, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_05 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='Fifth Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 5, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_06 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='Sixth Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 6, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_ct', setter='set_analytic_ct')
    ct_analytic_07 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='Seventh Level',
                        states={ 'invisible': Not(Greater(Eval('ct_analytic_level', 0), 7, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic_ct', setter='set_analytic_ct')

    product_income = fields.Many2One('product.product', 'Product Income',
            states=_DT_PRODUCT_STATES)

    product = fields.Function(fields.Many2One('product.product', 'Product',), 'get_product_dic')

    product_uom = fields.Many2One('product.uom', 'Unit', states=_ACC_PRODUCT_STATES,
            domain=[('category', '=', (Eval('product'), 'product.default_uom.category'))],
            context={'category': (Eval('product'), 'product.default_uom.category'),},
            on_change_with=['product'])
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
            states=_ACC_PRODUCT_STATES)
    unit_digits = fields.Function(fields.Integer('Unit Digits', on_change_with=['product_uom']), 'get_unit_digits')
    unit_price = fields.Numeric('Price Unit', digits=(16, Eval('currency_digits', 2)),
            states=_ACC_PRODUCT_STATES)
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            on_change_with=['quantity', 'unit_price'],
            states={'readonly': Equal(Eval('state'), 'posted'),},
            depends=['currency_digits', 'quantity', 'unit_price'])
    amount_currency = fields.Numeric('Amount in Currency', 
            states={'readonly': Equal(Eval('state'), 'posted'),},
            digits=(16, Eval('second_currency_digits', 2)),
            depends=['second_currency_digits'])
    currency = fields.Many2One('currency.currency','Currency', states={
            'invisible': Not(Bool(Eval('amount_currency', 0.0))),
            'readonly': Equal(Eval('state'), 'posted'),
            })
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    second_currency_digits = fields.Function(fields.Integer('Second Currency Digits', on_change_with=['currency']),'get_currency_digits')
    id_1c = fields.Char("ID import from 1C", size=None, select=1)
    state = fields.Selection([
                ('draft','Draft'),
                ('posted','Posted'),
                ('canceled','Canceled'),
                ('deleted','Deleted')
                ], 'State', required=True, readonly=True)
    dt_balance = fields.Integer('Ref balances debit')
    ct_balance = fields.Integer('Ref balances credit')
    dt_balance2 = fields.Integer('Ref balances debit of type')
    ct_balance2 = fields.Integer('Ref balances credit of type')
    deleted = fields.Boolean('Flag deleting')
    dt_kind = fields.Function(fields.Char('Kind Account Debit'),'get_kind_account')
    ct_kind = fields.Function(fields.Char('Kind Account Credit'),'get_kind_account')
    dt_kind_analytic = fields.Function(fields.Char('Kind Account Debit'),'get_kind_account')
    ct_kind_analytic = fields.Function(fields.Char('Kind Account Credit'),'get_kind_account')
    dt_acc_analytic = fields.Function(fields.Many2One('ekd.account.analytic', 
                'Analytic Account Debit'),'get_kind_account')
    dt_analytic = fields.Many2One('ekd.account.analytic', 'Debit analytic account',
                states={ 'invisible': Or(Not(Equal(Eval('dt_kind_analytic'),'analytic')), 
                                        Not(Bool(Eval('dt_acc_analytic')))), },
                domain=[('type', '!=', 'view'),('parent','child_of', Eval('dt_acc_analytic'), 'parent')])

    ct_acc_analytic = fields.Function(fields.Many2One('ekd.account.analytic', 
                'Analytic Account Credit'),'get_kind_account')
    ct_analytic = fields.Many2One('ekd.account.analytic', 'Credit analytic account',
                states={ 'invisible': Or(Not(Equal(Eval('ct_kind_analytic'),'analytic')), 
                                         Not(Bool(Eval('ct_acc_analytic')))), },
                domain=[('type', '!=', 'view'),('parent','child_of', Eval('ct_acc_analytic'), 'parent')])

    dt_analytic_level = fields.Function(fields.Integer('Analytic Account Debit'),'get_kind_account')
    ct_analytic_level = fields.Function(fields.Integer('Analytic Account Credit'),'get_kind_account')
    period = fields.Function(fields.Many2One('ekd.period', 'Period'),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')
    date = fields.Function(fields.Date('Effective Date'),
            'get_move_field', setter='set_move_field',
            searcher='search_move_field')

    def __init__(self):
        super(LineRU, self).__init__()

        self._rpc.update({
            'button_post': True,
            'button_cancel': True,
            'button_restore': True,
            'get_analytic_new': True,
            })
        self._order.insert(0, ('date_operation', 'ASC'))
        self._order.insert(1, ('dt_account', 'ASC'))
        self._order.insert(2, ('ct_account', 'ASC'))

        self._error_messages.update({
            'del_posted_move': 'You can not delete posted moves!',
            'post_empty_move': 'You can not post an empty move!',
            'company_in_move': 'You can not create lines on accounts\n' \
            'of different companies in the same move!',
            'date_outside_period': 'You can not create move ' \
            'with a date outside the period!',
            })

    def default_get(self, fields, with_rec_name=True):
        context = Transaction().context
        self._default_context = Transaction().context
        res = super(LineRU, self).default_get(fields, with_rec_name=True)
        if 'company' in fields:
            res['company'] = context.get('company') or False
        if 'state' in fields:
            res['state'] = context.get('state') or 'draft'
        if 'name' in fields:
            res['name'] = context.get('name') or False
        if 'amount' in fields:
            res['amount'] = context.get('amount') or False
        if 'date_operation' in fields:
            res['date_operation'] = context.get('date_operation') or False
        if 'currency_digits' in fields:
            res['currency_digits'] = context.get('currency_digits') or 2
        if 'second_currency_digits' in fields:
            res['second_currency_digits'] = context.get('second_currency_digits') or 2

        return res

    def triggers_all(self, ids, vals):
        raise Exception(str(ids), str(vals))
    
    def get_analytic_dt(self, ids, names):
        res = []
        if not ids:
            return {}
        res = {}
        for line in self.browse(ids):
            if line.dt_analytic_level > 0:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
                    for analytic_line in line.dt_analytic_accounts:
                        if analytic_line.level == name[-2:]:
                            res[name][line.id] = analytic_line.analytic
            else:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
        #raise Exception(str(res))
        return res

    def set_analytic_dt(self, ids, name, vals):
        line_id = self.browse(ids[0])
        for analytic_line in line_id.dt_analytic_accounts:
            if analytic_line.level == name[-2:]:
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': analytic_line.level, 
                                    'analytic': vals,
                                    })
        return True

    def get_analytic_ct(self, ids, names):
        if not ids:
            return {}
        res = {}
        for line in self.browse(ids):
            if line.ct_analytic_level > 0:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
                    for analytic_line in line.ct_analytic_accounts:
                        if analytic_line.level == name[-2:]:
                            res[name][line.id] = analytic_line.analytic
            else:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
        return res

    # TODO: При сохранении через основной объект идет повтор сохранения
    def set_analytic_ct(self, ids, name, vals):
        line_id = self.browse(ids[0])
        for analytic_line in line_id.ct_analytic_accounts:
            if analytic_line.level == name[-2:]:
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': analytic_line.level, 
                                    'analytic': vals,
                                    })

    def get_analytic_new(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.level_analytic'),
                    ('pole', '=', 'type_analytic'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            #if diction.domain:
            #    res.append((diction.key, diction.value,diction.domain))
            #else:
                res.append((diction.key, diction.value))
        return res

    def get_product_dic(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                if line.dt_kind_analytic in _PRODUCT and line.product_income:
                    res[name][line.id] = line.product_income.id
                elif line.ct_kind_analytic == 'product_goods' and line.product_balance_goods:
                    res[name][line.id] = line.product_balance_goods.product.id
                #elif line.ct_kind_analytic == 'product_material' and line.product_balance_material:
                #    res[name][line.id] = line.product_balance_material.product.id
                #elif line.ct_kind_analytic == 'product_fixed' and line.product_balance_fixed:
                #    res[name][line.id] = line.product_balance_fixed.product.id
                #elif line.ct_kind_analytic == 'product_intagible' and line.product_balance_intagible:
                #    res[name][line.id] = line.product_balance_intagible.product.id
                else:
                    res[name][line.id] = None
        #raise Exception(str(res))
        return res

    def get_kind_account(self, ids, names):
        if not ids:
            return {}
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, False)
                if line.dt_account:
                    if name =='dt_kind':
                        res[name][line.id] = line.dt_account.kind
                    elif name =='dt_kind_analytic':
                        res[name][line.id] = line.dt_account.kind_analytic
                    elif name =='dt_acc_analytic':
                        res[name][line.id] = line.dt_account.root_analytic.id
                    elif name =='dt_analytic_level':
                        res[name][line.id] = len(line.dt_account.level_analytic) or 0

                if line.ct_account:
                    if name =='ct_kind':
                        res[name][line.id] = line.ct_account.kind
                    elif name =='ct_kind_analytic':
                        res[name][line.id] = line.ct_account.kind_analytic
                    elif name =='ct_acc_analytic':
                        res[name][line.id] = line.ct_account.root_analytic.id
                    elif name =='ct_analytic_level':
                        if line.ct_account.level_analytic_ct:
                            res[name][line.id] = len(line.ct_account.level_analytic_ct)
                        else:
                            res[name][line.id] = len(line.ct_account.level_analytic) or 0

        return res

    def get_currency_digits(self, ids, names):
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, 2)
                if name == 'currency_digits':
                    res[name][line.id] = line.company.currency.digits
                elif name == 'second_currency_digits':
                    if line.currency:
                        res[name][line.id] = line.currency.digits
        return res

    def on_change_dt_account(self, vals):
        account_obj = self.pool.get('ekd.account')
        context = Transaction().context
        dt_analytic = {
            '01': False,
            '02': False,
            '03': False,
            '04': False,
            '05': False,
            '06': False,
            '07': False,
            'level':0
            }
        account_kind = False
        kind_analytic = False
        root_analytic_id = False
        dt_analytic_accounts = {}
        if vals.get('dt_account'):
            account = account_obj.browse(vals['dt_account'])
            account_kind = account.kind
            kind_analytic = account.kind_analytic
            root_analytic_id = account.root_analytic.id
            if account.level_analytic:
                dt_analytic['level'] = len(account.level_analytic)
                for analytic in account.level_analytic:
                    model, model_id = analytic.ref_analytic.split(',',1)
                    if self._default_context.get('dt_party') and \
                        model in ['party.party', 'party.supplier', 
                         'party.customer']:
                         model_obj = self.pool.get(model)
                         if model_obj.search(['id','=', int(model_id) ]):
                            dt_analytic[analytic.level] = '%s,%s'%\
                                (model, self._default_context.get('dt_party'))
                    if self._default_context.get('dt_employee') and \
                        model == 'company.employee':
                        dt_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('dt_employee'))
                    if self._default_context.get('dt_analytic') and \
                        model == 'ekd.account.analytic':
                        dt_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('dt_analytic'))
                    if self._default_context.get('dt_department') and \
                        model == 'company.department':
                        dt_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('dt_department'))
                    if self._default_context.get('business') and \
                        model == 'business.business':
                        dt_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('business'))
                    else:
                        dt_analytic[analytic.level] = analytic.ref_analytic
                    dt_analytic_accounts.setdefault('add', []).append({
                                    'level': analytic.level, 
                                    'analytic': analytic.ref_analytic})
                if vals.get('dt_analytic_accounts'):
                    dt_analytic_accounts['remove'] = [x['id'] for x in vals.get('dt_analytic_accounts')]
            else:
                if vals.get('dt_analytic_accounts'):
                    dt_analytic_accounts['remove'] = [x['id'] for x in vals.get('dt_analytic_accounts')]
        else:
            if vals.get('dt_analytic_accounts'):
                dt_analytic_accounts['remove'] = [x['id'] for x in vals.get('dt_analytic_accounts')]

        return {'dt_kind': account_kind,
                'dt_kind_analytic': kind_analytic,
                'dt_acc_analytic': root_analytic_id,
                'dt_analytic_level': dt_analytic['level'],
                'dt_analytic_01': dt_analytic['01'],
                'dt_analytic_02': dt_analytic['02'],
                'dt_analytic_03': dt_analytic['03'],
                'dt_analytic_04': dt_analytic['04'],
                'dt_analytic_05': dt_analytic['05'],
                'dt_analytic_06': dt_analytic['06'],
                'dt_analytic_07': dt_analytic['07'],
                'dt_analytic_accounts': dt_analytic_accounts,
                }


    def on_change_ct_account(self, vals):
        account_obj = self.pool.get('ekd.account')
        context = Transaction().context
        ct_analytic={
            '01': False,
            '02': False,
            '03': False,
            '04': False,
            '05': False,
            '06': False,
            '07': False,
            'level':0
            }
        ct_analytic_accounts = {}
        account_kind = False
        kind_analytic = False
        root_analytic_id = False
        if vals.get('ct_account'):
            account = account_obj.browse(vals['ct_account'])
            account_kind = account.kind
            kind_analytic = account.kind_analytic
            root_analytic_id = account.root_analytic.id
            if account.side_analytic == 'credit':
                ct_analytic['level'] = len(account.level_analytic_ct)
                for analytic in account.level_analytic_ct:
                    model, model_id = analytic.ref_analytic.split(',',1)
                    if self._default_context.get('ct_party') and \
                        model in ['party.party', 'party.supplier', 
                         'party.customer']:
                         model_obj = self.pool.get(model)
                         if model_obj.search(['id','=', int(model_id)]):
                            raise Exception(model_obj.search(['id','=', int(model_id)]))
                            ct_analytic[analytic.level] = '%s,%s'%\
                                (model, self._default_context.get('ct_party'))
                    if self._default_context.get('ct_employee') and \
                        model == 'company.employee':
                        ct_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('ct_employee'))
                    if self._default_context.get('ct_analytic') and \
                        model == 'ekd.account.analytic':
                        ct_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('ct_analytic'))
                    if self._default_context.get('ct_department') and \
                        model == 'company.department':
                        ct_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('ct_department'))
                    if self._default_context.get('business') and \
                        model == 'business.business':
                        ct_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('business'))
                    else:
                        ct_analytic[analytic.level] = analytic.ref_analytic
                    ct_analytic_accounts.setdefault('add', []).append({
                                    'level': analytic.level, 
                                    'analytic': analytic.ref_analytic})
                if vals.get('ct_analytic_accounts'):
                    ct_analytic_accounts['remove'] = [x['id'] for x in vals.get('ct_analytic_accounts')]

            elif account.level_analytic:
                ct_analytic['level'] = len(account.level_analytic)
                for analytic in account.level_analytic:
                    model, model_id = analytic.ref_analytic.split(',',1)
                    if self._default_context.get('ct_party') and \
                        model in ['party.party', 'party.supplier', 
                         'party.customer']:
                        ct_analytic[analytic.level] = '%s,%s'%(model, self._default_context.get('ct_party'))
                    else:
                        ct_analytic[analytic.level] = analytic.ref_analytic
                    ct_analytic_accounts.setdefault('add', []).append({
                                    'level': analytic.level, 
                                    'analytic': analytic.ref_analytic})
                if vals.get('ct_analytic_accounts'):
                    ct_analytic_accounts['remove'] = [x['id'] for x in vals.get('ct_analytic_accounts')]
            else:
                if vals.get('ct_analytic_accounts'):
                    ct_analytic_accounts['remove'] = [x['id'] for x in vals.get('ct_analytic_accounts')]
        else:
            if vals.get('ct_analytic_accounts'):
                ct_analytic_accounts['remove'] = [x['id'] for x in vals.get('ct_analytic_accounts')]

        return {'ct_kind': account_kind,
                'ct_kind_analytic': kind_analytic,
                'ct_acc_analytic': root_analytic_id,
                'ct_analytic_level': ct_analytic['level'],
                'ct_analytic_01': ct_analytic['01'],
                'ct_analytic_02': ct_analytic['02'],
                'ct_analytic_03': ct_analytic['03'],
                'ct_analytic_04': ct_analytic['04'],
                'ct_analytic_05': ct_analytic['05'],
                'ct_analytic_06': ct_analytic['06'],
                'ct_analytic_07': ct_analytic['07'],
                'ct_analytic_accounts': ct_analytic_accounts,
                }

    def on_change_with_unit_digits(self, vals):
        uom_obj = self.pool.get('product.uom')
        if vals.get('uom'):
            uom = uom_obj.browse(vals['uom'])
            return uom.digits
        return 2

    def on_change_with_product_uom(self, vals):
        product_obj = self.pool.get('product.product')
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            return product.default_uom.id

    def on_change_with_amount(self, vals):
        if vals.get('quantity') and vals.get('unit_price') :
            return Decimal(str(vals.get('quantity'))) * vals.get('unit_price')


    def on_change_with_second_currency_digits(self, vals):
        currency_obj = self.pool.get('currency.currency')
        if vals.get('currency'):
            currency = currency_obj.browse(vals['currency'])
            return currency.digits
        return 2

    def get_move_field(self, ids, name):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'state', 'name'):
            raise Exception('Invalid name')
        res = {}
        if name == 'date':
            name = 'date_operation'
        for line in self.browse(ids):
            if name in ('date_operation', 'date', 'state'):
                res[line.id] = line.move[name]
            elif name == 'name':
                if line.name_line:
                    res[line.id] = line.name_line
                else:
                    res[line.id] = line.move[name]
            else:
                res[line.id] = line.move[name].id
        return res

    def set_move_field(self, ids, name, value):
        if name == 'move_state':
            name = 'state'
        if name not in ('period', 'journal', 'date', 'name', 'state'):
            raise Exception('Invalid name')
        if not value:
            return
        move_obj = self.pool.get('ekd.account.move')
        lines = self.browse(ids)
        if name == 'name':
            self.write([line.id for line in lines], {
            'name_line': value,
            })

        move_obj.write([line.move.id for line in lines], {
            name: value,
            })

    def search_move_field(self, name, clause):
        if name == 'move_state':
            name = 'state'
            return [('move.' + name,) + clause[1:]]
        if name == 'period':
            pole, dif, period_id = clause
            period_obj = self.pool.get('ekd.period')
            period = period_obj.browse(period_id)
            #raise Exception('line', str(period_id), str(period.start_date), str(period.end_date))
            return [('move.date_operation','>=', period.start_date),
                    ('move.date_operation','<=', period.end_date)]
        return [('move.' + name,) + clause[1:]]

    def get_unit_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            if line.product_uom:
                res[line.id] = line.product_uom.digits
            else:
                res[line.id] = 2
        return res

    def view_header_get(self, value, view_type='form'):
        journal_period_obj = self.pool.get('ekd.account.journal.period')
        if (not Transaction().context.get('journal')
                or not Transaction().context.get('period')):
            if Transaction().context.get('period_move_line'):
                period_move = Transaction().context.get('period_move_line')
                return value + ' with period - begin: ' +\
                                    period_move.get('start_period').strftime('%d.%m.%Y')+\
                                ' end: ' + period_move.get('end_period').strftime('%d.%m.%Y')
            else:
                return value + 'sss'
        journal_period_ids = journal_period_obj.search([
            ('journal', '=', Transaction().context['journal']),
            ('period', '=', Transaction().context['period']),
            ], limit=1)
        if not journal_period_ids:
            return value
        journal_period = journal_period_obj.browse(journal_period_ids[0])
        return value + ': ' + journal_period.rec_name

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
            hexmd5=None):
        journal_obj = self.pool.get('ekd.account.journal')
        result = super(LineRU, self).fields_view_get(view_id=view_id,
                view_type=view_type, toolbar=toolbar, hexmd5=hexmd5)
        if view_type == 'tree' and 'journal' in Transaction().context:
            title = self.view_header_get('', view_type=view_type)
            journal = journal_obj.browse(Transaction().context['journal'])

            if not journal.view:
                return result

            xml = '<?xml version="1.0"?>\n' \
                    '<tree string="%s" editable="top" on_write="on_write" ' \
                    'colors="red:state==\'draft\'">\n' % title
            fields = set()
            for column in journal.view.columns:
                fields.add(column.field.name)
                attrs = []
                if column.field.name == 'amount':
                    attrs.append('sum="Total"')
                if column.readonly:
                    attrs.append('readonly="1"')
                if column.required:
                    attrs.append('required="1"')
                else:
                    attrs.append('required="0"')
                xml += '<field name="%s" %s/>\n' % (column.field.name, ' '.join(attrs))
                for depend in getattr(self, column.field.name).depends:
                    fields.add(depend)
            fields.add('state')
            xml += '</tree>'
            result['arch'] = xml
            result['fields'] = self.fields_get(fields_names=list(fields))
            del result['md5']
            if hashlib:
                result['md5'] = hashlib.md5(str(result)).hexdigest()
            else:
                result['md5'] = md5.new(str(result)).hexdigest()
            if hexmd5 == result['md5']:
                return True
        return result

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for line in self.browse(ids):
            if line.state == 'posted':
                self.raise_user_error('del_posted_move')
            if line.state == 'deleted' and line.deleted:
                return super(LineRU, self).delete(ids)
            else:
                return line.write(ids, {'state':'deleted', 'deleted':True})

    def button_post(self, ids):
        return self.post(ids)

    def button_cancel(self, ids):
        return self.post_cancel(ids)

    def button_restore(self, ids):
        return self.draft(ids)

    def post(self, ids):
        line_west_obj = self.pool.get('ekd.account.move.line.west')
        sequence_obj = self.pool.get('ir.sequence')
        line_analytic_dt_obj = self.pool.get('ekd.account.move.line.analytic_dt')
        line_analytic_ct_obj = self.pool.get('ekd.account.move.line.analytic_ct')
        for line in self.browse(ids):
            if line.dt_account:
                line_dt = line_west_obj.create({
                        'line': line.id,
                        'period': line.period.id,
                        'date_operation': line.move.date_operation,
                        'account': line.dt_account.id,
                        'debit': line.amount,
                        })
            if line.ct_account:
                line_ct = line_west_obj.create({
                        'line': line.id,
                        'period': line.period.id,
                        'date_operation': line.move.date_operation,
                        'account': line.ct_account.id,
                        'credit': line.amount,
                        })
            if line.dt_analytic_level:
                for analytic_account in line.dt_analytic_accounts:
                    line_analytic_dt_obj.write(analytic_account.id,
                                               {'move_line_west': line_dt})
            if line.ct_analytic_level:
                for analytic_account in line.ct_analytic_accounts:
                    line_analytic_ct_obj.write(analytic_account.id,
                                               {'move_line_west': line_ct})
        return self.write(ids, {
                        'post_date': datetime.datetime.now().strftime('%Y-%m-%d'),
                        'state': 'posted',
                        })

    def draft(self, ids):
        return self.write(ids, {
                        'state': 'draft',
                        })

    def post_cancel(self, ids):
        line_west_obj = self.pool.get('ekd.account.move.line.west')
        line_analytic_dt_obj = self.pool.get('ekd.account.move.line.analytic_dt')
        line_analytic_ct_obj = self.pool.get('ekd.account.move.line.analytic_ct')
        # move.period.post_move_sequence.id
        #                        'post_line': reference,
        for line in self.browse(ids):
            if line.dt_analytic_level:
                for analytic_account in line.dt_analytic_accounts:
                    line_analytic_dt_obj.write(analytic_account.id,
                                               {'move_line_west': None})
            if line.ct_analytic_level:
                for analytic_account in line.ct_analytic_accounts:
                    line_analytic_ct_obj.write(analytic_account.id,
                                               {'move_line_west': None})
        line_west_obj.delete(line_west_obj.search([('line', 'in', ids)]))
        return self.write(ids, {
                        'state': 'canceled',
                        })

    def restore(self, ids):
        return self.write(ids, {
                        'state': 'draft',
                        })

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        context = Transaction().context
        default['state'] = 'draft'
        res = super(LineRU, self).copy(ids, default=default)
        return res

    def create(self, vals):

        return super(LineRU, self).create( vals)


    def write(self, ids, vals):
        if isinstance(ids, (int, long)):
            ids = [ids]
        #raise Exception(str(vals))
        res = super(LineRU, self).write(ids, vals)
        return res

    def turnover(self, vals):
        '''
        Сбор данных по оборота счетов
        {
        'type_account': [Список полей для группировки],
        'account': [Список id счетов],
        'StartDate': Дата,
        'EndDate': Дата
        }
        '''
        res = {}
        cr = Transaction().cursor
        cr.execute('SELECT '+','.join(map(str,vals.get('type_account')))+ ', SUM(amount) as amount '+\
                    'FROM ekd_account_move_line'+\
                    'WHERE date_operation<=%s AND date_operation>=%s, %s in ('+\
                    ','.join(map(str,vals.get('account')))+')'+\
                    'GROUP BY '+','.join(map(str,vals.get('type_account')))+\
                    ''%(vals.get('StartDate'), vals.get('EndDate')))
        res = cr.fetchall()
        return res

LineRU()

class Account(ModelSQL, ModelView):
    _name = 'ekd.account'

    corr_debit = fields.Many2Many('ekd.account.control.debit',
                'account', 'credit', 'Corresponden with Credit Account')
    corr_credit = fields.Many2Many('ekd.account.control.credit',
                'account', 'debit', 'Correspondent with Debit Account')

    child_consol_ids = fields.Many2Many('ekd.account.consolidation',
                'account', 'child', 'Consolidated Children')

    level_analytic = fields.Function(fields.One2Many('ekd.account.level_analytic', 'account', 
                                     'Level Analytic',
                                     help="Level Analytic Both Side or Debit",
                                     states={'readonly': Or(Not(In(Eval('kind_analytic'),
                                        _PARTY+_PRODUCT+_DEPRECATION+_MONEY+_OTHER)),
                                        Equal(Eval('side_analytic'), 'credit')),},
                                    context={'side':'dt'}
                                    ), 'get_level_analytic', setter='set_level_analytic')

    level_analytic_ct = fields.Function(fields.One2Many('ekd.account.level_analytic', 'account',
                                     'Level Analytic Side Credit',
                                     help="Level Analytic Credit Side",
                                     states={'readonly': Or(Not(In(Eval('kind_analytic'),
                                        _PARTY+_PRODUCT+_DEPRECATION+_MONEY+_OTHER)),
                                        Not(In(Eval('side_analytic'), ['side', 'credit']))),},
                                    context={'side':'ct'}, 
                                    depends=['kind_analytic', 'side_analytic']
                                    ), 'get_level_analytic', setter='set_level_analytic')

    def get_level_analytic(self, ids, names):
        res={}
        level_analytic_obj = self.pool.get('ekd.account.level_analytic')
        for line_id in ids:
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line_id, [])
                if name =='level_analytic_ct':
                    res[name][line_id] = level_analytic_obj.search([
                            ('side','=','ct'),
                            ('account','=',line_id),
                            ])
                else:
                    res[name][line_id] = level_analytic_obj.search([
                            ('side','=','dt'),
                            ('account','=',line_id),
                            ])
        return res

    def set_level_analytic(self, ids, name, vals):
        res={}
        level_analytic_obj = self.pool.get('ekd.account.level_analytic')
        #raise Exception(str(vals))
        if name =='level_analytic_ct':
            for value in vals:
                if value[0] == 'add':
                    pass
                elif value[0] == 'write':
                    level_analytic_obj.write(value[1], value[2])
                elif value[0] == 'create':
                    value[1]['account'] = ids[0]
                    value[1]['side'] = 'ct'
                    level_analytic_obj.create(value[1])
                elif value[0] == 'delete':
                    level_analytic_obj.delete(value[1])
        elif name =='level_analytic':
            for value in vals:
                if value[0] == 'add':
                    pass
                elif value[0] == 'write':
                    level_analytic_obj.write(value[1], value[2])
                elif value[0] == 'create':
                    value[1]['account'] = ids[0]
                    value[1]['side'] = 'dt'
                    level_analytic_obj.create(value[1])
                elif value[0] == 'delete':
                    level_analytic_obj.delete(value[1])

        #raise Exception(str(ids), str(name), str(vals))
        return res

Account()

class AnalyticAccount(ModelSQL, ModelView):
    _name = 'ekd.account.analytic'

    child_consol_ids =  fields.Many2Many('ekd.account.analytic.consolidate', 'account', 'child', 'Consolidated Children')

AnalyticAccount()

class PostMoveInit(ModelView):
    'Post Move Init'
    _name = 'ekd.account.move.post.init'
    _description = __doc__

    queue = fields.Boolean('Queue')

PostMoveInit()

class PostMove(Wizard):
    'Post Move'
    _name = 'ekd.account.move.post'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.move.post.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('post', 'post', 'tryton-ok', True),
                ],
            },
        },
        'post': {
            'actions': ['_post_lines'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _post_lines(self, data):
        move_obj = self.pool.get('ekd.account.move')
        # Сортировка по дате операции
        move_ids =  move_obj.search([('id', 'in', data['ids'])], 
                            order=[('date_operation', 'ASC')])
        move = move_obj.post(move_ids)
        return {}

PostMove()

class CancelPostMoveInit(ModelView):
    'Cancel Post Move Init'
    _name = 'ekd.account.move.cancel.init'
    _description = __doc__

    queue = fields.Boolean('Queue')

CancelPostMoveInit()


class CancelPostMove(Wizard):
    'Cancel Post Move'
    _name = 'ekd.account.move.cancel'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.move.cancel.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('post_cancel', 'Post Cancel', 'tryton-ok', True),
                ],
            },
        },
        'post_cancel': {
            'actions': ['_post_cancel'],
            'result': {
                'type': 'state',
                'state': 'end',
            },
        },
    }

    def _post_cancel(self, data):
        move_obj = self.pool.get('ekd.account.move')
        move_obj.post_cancel(data['ids'])
        return {}

CancelPostMove()

class OpenAccount(Wizard):
    'Open Account'
    _name = 'ekd.account.move.open_account'
    states = {
            'init': {
                'result': {
                        'type': 'action',
                        'action': '_action_open_account',
                        'state': 'end',
                        },
                    },
            }

    def _action_open_account(self, data):
        if not data['ids']:
            return {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        account_obj = self.pool.get('ekd.account')
        context = Transaction().context
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        period_obj = self.pool.get('ekd.period')
        if context.get('current_period'):
            date_start = period_obj.browse(context.get('current_period')).start_date
            date_end = period_obj.browse(context.get('current_period')).end_date
        else:
            if context.get('start_period'):
                date_start = context.get('current_period')
            else:
                date_start = datetime.datetime.now()

            if context.get('end__period'):
                date_end = context.get('end_period')
            else:
                date_end = datetime.datetime.now()

        act_window_id = model_data_obj.get_id('ekd_account', 'act_move_line_ru_form')
        res = act_window_obj.read(act_window_id)
        account_ids = account_obj.get_childs(data['id'])
        if not account_ids:
            account_ids = [data['id']]
        res['pyson_domain'] = [ 'OR',
                        [('date_operation', '>=', date_start),
                        ('date_operation', '<=', date_end),
                        ('state', '=', 'posted'),
                        ('dt_account', 'in', account_ids)],
                        [('date_operation', '>=', date_start),
                        ('date_operation', '<=', date_end),
                        ('state', '=', 'posted'),
                        ('ct_account', 'in', account_ids)],
                        ]
        res['pyson_domain'] = PYSONEncoder().encode(res['pyson_domain'])
        res['pyson_context'] = PYSONEncoder().encode({
                'fiscalyear': Transaction().context.get('fiscalyear'),
                'period_move_line': {
                        'start_period': date_start,
                        'end_period': date_end,
                        },
            })
        res['name'] +=  u' по счету: '+\
                        account_obj.browse(data['id']).rec_name+\
                        u' за период - с: ' +\
                        date_start.strftime('%d.%m.%Y')+\
                        u' по: ' + date_end.strftime('%d.%m.%Y')
        return res

OpenAccount()

class OperationReport(Report):
    _name = 'ekd.account.move.report'

    def execute(self, ids, datas):
        '''
        ids - Перечисление выделенных строк в журнале
        datas - {'model': u'ekd.account.move', 'id': 10} 
        '''
        res = super(OperationReport, self).execute(ids, datas)
        return res

    def _get_objects(self, ids, model, datas):
        '''
        ids - Перечисление выделенных строк в журнале
        model - имя модели
        datas - {'model': u'ekd.account.move', 'id': 10}
        '''
        move_obj = self.pool.get('ekd.account.move')
        return move_obj.browse(ids)

    def parse(self, report, objects, datas, localcontext={}):
        '''
        report - BrowseRecord(ir.action.report, 191)
        objects - [BrowseRecord(ekd.account.move, 10)]
        datas - {'model': u'ekd.account.move', 'id': 10}
        localcontext - {}
        '''
        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['period'] = self.pool.get('ekd.period').browse(context.get('current_period', False))
        localcontext['start_date'] = context.get('start_period', False)
        localcontext['end_date'] = context.get('end_period', False)
        localcontext['current_date'] = context.get('current_date', False)
        localcontext['total_move'] = sum((x['amount'] for x in objects))

        res = super(OperationReport, self).parse(report, objects, datas,
                localcontext)
        return res

OperationReport()

class GeneralJournal(Report):
    _name = 'ekd.account.move.general_journal'

    def _get_objects(self, ids, model, datas):
        move_obj = self.pool.get('ekd.account.move')

        clause = [
            ('date', '>=', datas['form']['from_date']),
            ('date', '<=', datas['form']['to_date']),
            ]
        if datas['form']['posted']:
            clause.append(('state', '=', 'posted'))
        move_ids = move_obj.search(clause,
                order=[('date', 'ASC'), ('reference', 'ASC'), ('id', 'ASC')])
        return move_obj.browse(move_ids)

    def parse(self, report, objects, datas, localcontext):
        company_obj = self.pool.get('company.company')

        company = company_obj.browse(datas['form']['company'])

        localcontext['company'] = company
        localcontext['digits'] = company.currency.digits
        localcontext['from_date'] = datas['form']['from_date']
        localcontext['to_date'] = datas['form']['to_date']

        return super(GeneralJournal, self).parse(report, objects, datas,
                localcontext)

GeneralJournal()

class OpenJournalAsk(ModelView):
    'Open Journal Ask'
    _name = 'ekd.account.move.open_journal.ask'
    _description = __doc__
    journal = fields.Many2One('ekd.account.journal', 'Journal', required=True)
    period = fields.Many2One('ekd.period', 'Period', required=True,
            domain=[
                ('state', '!=', 'close'),
                ('fiscalyear.company.id', '=',
                    Get(Eval('context', {}), 'company', 0)),
            ])

    def default_period(self):
        period_obj = self.pool.get('ekd.period')
        return period_obj.find(Transaction().context.get('company') or False,
                exception=False)

OpenJournalAsk()


class OpenJournal(Wizard):
    'Open Journal'
    _name = 'ekd.account.move.open_journal'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_next',
            },
        },
        'ask': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.move.open_journal.ask',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_journal',
                'state': 'end',
            },
        },
    }

    def _next(self, data):
        if data.get('model', '') == 'ekd.account.journal.period' \
                and data.get('id'):
            return 'open'
        return 'ask'

    def _get_journal_period(self, data):
        journal_period_obj = self.pool.get('ekd.account.journal.period')
        if data.get('model', '') == 'ekd.account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(data['id'])
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
            }
        return {}

    def _action_open_journal(self, data):
        journal_period_obj = self.pool.get('ekd.account.journal.period')
        journal_obj = self.pool.get('ekd.account.journal')
        period_obj = self.pool.get('ekd.period')
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        if data.get('model', '') == 'ekd.account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(data['id'])
            journal_id = journal_period.journal.id
            period_id = journal_period.period.id
        else:
            journal_id = data['form']['journal']
            period_id = data['form']['period']
        if not journal_period_obj.search([
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ]):
            journal = journal_obj.browse(journal_id)
            period = period_obj.browse(period_id)
            journal_period_obj.create({
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                })

        act_window_id = model_data_obj.get_id('ekd_account', 'act_move_line_ru_form')
        res = act_window_obj.read(act_window_id)
        journal = journal_obj.browse(journal_id)
        # Remove name to use the one from view_header_get
        del res['name']
        res['pyson_domain'] = PYSONEncoder().encode([
            ('ct_account', '=', journal.credit_account.id),
            ('period', '=', period_id),
            ])
        res['pyson_context'] = PYSONEncoder().encode({
            'journal': journal_id,
            'period': period_id,
            })
        return res

OpenJournal()

class PrintGeneralJournalInit(ModelView):
    'Print General Journal Init'
    _name = 'ekd.account.move.print_general_journal.init'
    _description = __doc__
    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Show only posted move')

    def default_from_date(self):
        date_obj = self.pool.get('ir.date')
        return datetime.date(date_obj.today().year, 1, 1)

    def default_to_date(self):
        date_obj = self.pool.get('ir.date')
        return date_obj.today()

    def default_company(self):
        return Transaction().context.get('company') or False

    def default_posted(self):
        return False

PrintGeneralJournalInit()

class PrintGeneralJournal(Wizard):
    'Print General Journal'
    _name = 'ekd.account.move.print_general_journal'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.account.move.print_general_journal.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('print', 'Print', 'tryton-print', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'ekd.account.move.general_journal',
                'state': 'end',
            },
        },
    }

PrintGeneralJournal()
