# -*- coding: utf-8 -*-
#NOTE: Платежи документов
"Document Payment"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.tools import safe_eval
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import In, If, Get, Eval, Not, Equal, Bool, Or, And
from trytond.modules.ekd_documents.ekd_state_document import _STATES_FULL
from account import _PARTY, _PRODUCT, _MONEY
import time
import datetime
import random

_RECEIVED_STATES = {
    'readonly': Not(Equal(Eval('state'),'draft')),
        }

_RECEIVED_DEPENDS = ['state']

class DocumentPayment(ModelSQL, ModelView):
    "Documents Payment"
    _name='ekd.document.payment'
    _table='ekd_document'
    _description=__doc__

    company = fields.Many2One('company.company', 'Company', readonly=True)
    model = fields.Many2One('ir.model', 'Model', domain=[('model','like','ekd.document%')], readonly=True)
    model_str = fields.Char('Model Name', size=128)
    direction = fields.Selection([('input','Input'),('output','Output')],'Direction document')
    name = fields.Char('Description', readonly=True)
    template = fields.Many2One('ekd.document.template', 'Document Name', help="Template documents", order_field="%(table)s.template %(order)s", readonly=True)
    note = fields.Text('Note document', readonly=True)
    number_our = fields.Char('Number Outgoing', size=32, readonly=True)
    number_in = fields.Char('Number of incoming', size=32, readonly=True)
    date_document = fields.Date('Date Create', readonly=True)
    date_account = fields.Date('Date Account', readonly=True)
    from_party = fields.Many2One('party.party', 'Manager', readonly=True)
    to_party = fields.Many2One('party.party', 'Beneficiary', readonly=True)
    amount = fields.Numeric('Amount Document', digits=(16,2), readonly=True)
    amount_payment = fields.Function(fields.Numeric('Amount Payment', digits=(16,2)), 'get_payment_fields')
    amount_paid = fields.Function(fields.Numeric('Amount Paid', digits=(16,2)),'get_paid_fields')
    amount_balance = fields.Function(fields.Numeric('Amount Balance', digits=(16,2)),'get_fields')
    parent = fields.Function(fields.One2Many('ekd.document', None, 'Payment document'), 'get_parent')
    child = fields.Many2One('ekd.document', 'Parent document', readonly=True)
    lines = fields.One2Many('ekd.document.line.request', 'requestcash', 'Lines Request')
    lines_payment = fields.One2Many('ekd.document.line.payment', 'doc_base', 'Lines Payment')
#                states=_RECEIVED_STATES, depends=_RECEIVED_DEPENDS)
    state = fields.Selection(_STATES_FULL, 'State', readonly=True)
    post_date = fields.Date('Date Post', readonly=True)

    def __init__(self): 
        super(DocumentPayment, self).__init__()
        self._rpc.update({
                    'payment': True,
                    'receive': True,
                    'return': True,
                            })

        self._order.insert(0, ('company','ASC')) 
        self._order.insert(1, ('date_document', 'ASC')) 
        self._order.insert(2, ('template', 'ASC')) 
        self._order.insert(3, ('date_account', 'ASC')) 
        self._order.insert(4, ('number_our', 'ASC')) 

    def get_rec_name(self, ids, name):
        res={}
        for document in self.browse(ids):
            if document.template.shortcut:
                TemplateName = document.template.shortcut
            else:
                TemplateName = document.template.name

            if document.number_our:
                DocumentNumber = document.number_our
            elif document.number_in:
                DocumentNumber = document.number_in
            else:
                DocumentNumber = 'no number'

            if document.date_account:
                DocumentDate = str(document.date_account.strftime('%d.%m.%Y'))
            elif document.date_document:
                DocumentDate = str(document.date_document.strftime('%d.%m.%Y'))
            else:
                DocumentDate = 'no date'
            res[document.id] = "%s %s %s %s %s"%(TemplateName, u"№", DocumentNumber, "от", DocumentDate)
        return res

    def get_fields(self, ids, names):
        if not ids:
            return {}
        res = {}

        for document in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(document.id, {})
                if name == 'amount_balance':
                    res[name][document.id] = document.amount-document.amount_payment-document.amount_paid
        return res

    def get_parent(self, ids, names):
        if not ids:
            return {}
        res = {}
        for document in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(document.id, [])
                if name == 'parent':
                    parent_ids = []
                    for line in document.lines_payment:
                        if line.doc_payment.id not in parent_ids:
                            parent_ids.append(line.doc_payment.id)
                    res[name][document.id] = parent_ids
        return res

    def on_change_amount_pay(self, values):
        if not values.get('lines'):
            return {}
        res={}
        if values.get('amount') == values.get('amount_pay'):
            for line in values.get('lines'):
                line['amount_payment'] = line['amount_request']
        else:
            amount = values.get('amount_pay')
            for line in values.get('lines'):
                if amount > 0:
                    if amount > line['amount_request']:
                        line['amount_payment'] = line['amount_request']
                    else:
                        line['amount_payment'] = amount
                else:
                    break
                amount -= line['amount_payment']

        return res

    def button_draft(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_draft(ids)

    def button_cancel(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_cancel(ids)

    def button_restore(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_restore(ids)

    def button_issued(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_issued(ids)

    def button_on_payment(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_payment(ids)

    def button_pay(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_pay(ids)

    def button_confirmed(self, ids):
        for document in self.browse(ids):
            if document.template.model:
                self.pool.get(document.template.model).button_confirmed(ids)

    def get_payment_fields(self, ids, name):
        res = {}.fromkeys( ids, Decimal('0.0'))
        cr = Transaction().cursor
        cr.execute("SELECT doc_base, SUM(amount_payment) "\
                        "FROM ekd_document_line_payment "\
                        "WHERE doc_base in ("+','.join(map(str,ids))+") and state in ('wait0', 'wait1', 'payment') "\
                        "GROUP BY doc_base")
        for id, sum in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[id] = sum
        return res

    def get_paid_fields(self, ids, name):
        res = {}.fromkeys( ids, Decimal('0.0'))
        cr = Transaction().cursor
        cr.execute("SELECT doc_base, SUM(amount_payment) "\
                        "FROM ekd_document_line_payment "\
                        "WHERE doc_base in ("+','.join(map(str,ids))+") and state='done' "\
                        "GROUP BY doc_base")
        for id, sum in cr.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[id] = sum
        return res

#    def fields_view_get(self, view_id=None, view_type=None, toolbar=None):
#        if view_type == 'form' and context.get('model', False):
#	    current_obj = self.browse(context.get('document_id')[0]=context )[0]
#	    model_obj = self.pool.get(current_obj.model.name)
#	    return model_obj.
#            raise Exception(str(context))
#	else:
#        return super(DocumentPayment, self).fields_view_get(view_id, view_type)

DocumentPayment()

class DocumentPaymentLine(ModelSQL, ModelView):
    "Documents Payment Line"
    _name='ekd.document.line.payment'
    _description=__doc__

    doc_payment = fields.Many2One('ekd.document', 'Document Payment', ondelete="CASCADE")
    doc_base = fields.Many2One('ekd.document.head.request', 'Document Base')
    amount_payment = fields.Numeric('Amount Payment', digits=(16,2))
    line_request = fields.Many2One('ekd.document.line.request', 'Line Request of money')
    line_ref = fields.Reference(selection='get_line_ref',  string='Ref.')
    type_transaction = fields.Selection([
                    ('income_cash','Income in Cash'),
                    ('expense_cash','Expense in Cash'),
                    ('return_cash','Return in Cash'),
                    ('income_bank','Income in Bank'),
                    ('expense_bank','Expense in Bank'),
                    ('return_bank','Return in Bank')
                    ], 'Type Transaction')
    state = fields.Selection([
                    ('deleted','Deleted'),
                    ('done','Done'),
                    ('payment','Payment'),
                    ('wait_bank','Waiting Confirm Bank')
            ], 'State')

    def get_line_ref(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                            ('model', '=', 'ekd.document.line.payment'),
                            ('pole', '=', 'line_ref'),
                            ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

DocumentPaymentLine()

class DocumentPaymentInit(ModelView):
    'Document Cash Init'
    _name = 'ekd.document.wizard.payment.init'
    _description = __doc__

    amount_payment = fields.Numeric('Amount Payment', digits=(16,2))

    def default_amount_payment(self):
        context = Transaction().context
        if context.get('active_ids', False):
            amount_balance = Decimal('0.0')
            for requestcash in self.pool.get('ekd.document.head.request').browse(context.get('active_ids')):
                amount_balance += requestcash.amount_balance
            return amount_balance
        elif context.get('active_id', False):
            requestcash = self.pool.get('ekd.document.head.request').browse(context.get('active_id'))
            return requestcash.amount_balance
        elif context.get('id', False):
            requestcash = self.pool.get('ekd.document.head.request').browse(context.get('id'))
            return requestcash.amount_balance
        elif context.get('amount_payment', False):
            return context.get('amount_payment')
        else:
            return Decimal('0.0')

DocumentPaymentInit()

class DocumentPaymentCash(ModelView):
    'Document Cash Init'
    _name = 'ekd.document.wizard.payment.cash'
    _description = __doc__

    # Specification Payment
    company = fields.Many2One('company.company', 'Company', readonly=True)
    template_cash = fields.Many2One('ekd.document.template', string='Document Name',
                        domain=[
                                ('type_account','=','cash_documents'),
                                ('code_call','=',Eval('type_transaction'))
                        ], on_change=['template_cash'])
    number_our = fields.Char('Number Outgoing', size=32, readonly=True)
    number_in = fields.Char('Number of incoming', size=32)
    date_document = fields.Date('Date Create')
    date_account = fields.Date('Date Account')
    description = fields.Text('Notes')
    application = fields.Char('Application')
    type_transaction = fields.Char('Type Operation')
    cash_account = fields.Many2One('ekd.account', 'Cash Account',
                                domain=[('kind_analytic', '=', 'money_cash')])
    corr_account = fields.Many2One('ekd.account', 'Corr Account',
                            domain=['OR', [
                                 ('kind_analytic', 'in', _PARTY+_MONEY),
                                 ('company','=', Eval('company'))],
                                 [('type.code', '=', 'salary'),
                                  ('company','=', Eval('company'))]])
    document_base_ref = fields.Reference('Document Base', selection='documents_get', readonly=True)
    from_to_party = fields.Many2One('party.party', string='From or To Party', readonly=True)
    # Amount
    amount_request = fields.Numeric('Amount Document', digits=(16,2), readonly=True)
    amount_received = fields.Numeric('Amount Received', digits=(16,2), readonly=True)
    amount_balance = fields.Numeric('Amount Balance', digits=(16,2), readonly=True)
    amount_payment = fields.Numeric('Amount Payment', digits=(16,2), readonly=True, 
                                on_change_with=['lines'], on_change=['amount_request', 'amount_payment', 'lines'])
    lines = fields.Function(fields.One2Many("ekd.document.line.request", None, 'Lines Request'), 'get_fields', setter="set_fields")

    def __init__(self):
        super(DocumentPaymentCash, self).__init__()
#        self._rpc.update({
#		'calculate': True,
#		'create': True,
#                })

    def default_get(self, fields,  with_rec_name=True):
        values = super(DocumentPaymentCash, self).default_get(fields, with_rec_name=with_rec_name)
        if 'type_transaction' in fields:
            values['type_transaction']='expense_cash'
        values['amount_request']=Decimal('0.0')
#        if not values.get('amount_received', True):
        values['amount_received']=Decimal('0.0')
#        if not values.get('amount_balance', True):
        values['amount_balance']=Decimal('0.0')
#        if not values.get('amount_payment', True):
        values['amount_payment']=Decimal('0.0')
        values['description'] = u"По документам:\n"

        context = Transaction().context
        if context.get('active_ids', False):
            if len(context.get('active_ids')) > 1:
                values['description'] = u"По документам:\n"
            else:
                values['description'] = u"По документу:\n"
            for requestcash_ids in self.pool.get('ekd.document.head.request').browse(context.get('active_ids')):
                values['company']=requestcash_ids.company.id
                values['date_account']=requestcash_ids.date_account
                values['document_base_ref']= u'ekd.document.head.request,%s'%(str(requestcash_ids.id))
                values['from_to_party']=requestcash_ids.recipient.id
                values['amount_request']+=requestcash_ids.amount_request
                values['amount_received']+=requestcash_ids.amount_received
                values['amount_balance']+=requestcash_ids.amount_balance
                values['amount_payment']+=requestcash_ids.amount_balance
                values['description'] += u"%s\n"%(requestcash_ids.rec_name)

        elif context.get('id', False):
            requestcash_ids = self.pool.get('ekd.document.head.request').browse(context.get('active_id'))

            values['company']=requestcash_ids.company.id
            values['date_account']=requestcash_ids.date_account
            values['document_base_ref']= u'ekd.document.head.request,%s'%(str(requestcash_ids.id))
            values['from_to_party']=requestcash_ids.recipient.id
            values['amount_request']=requestcash_ids.amount_request
            values['amount_received']=requestcash_ids.amount_received
            values['amount_balance']=requestcash_ids.amount_balance
            values['amount_payment']=requestcash_ids.amount_balance

        elif context.get('amount_request', False):
            values['amount_request']=context.get('amount_request')
            values['amount_received']=context.get('amount_received')

        else:
            values['amount_request']=Decimal('0.0')
            values['amount_received']=Decimal('0.0')

        return values

    def default_amount_payment(self):
        context = Transaction().context
        if context.get('amount_payment', False):
            return context.get('amount_payment')
        elif context.get('active_ids', False):
            amount_balance = Decimal('0.0')
            for requestcash_ids in self.pool.get('ekd.document.head.request').browse(context.get('active_ids')):
                amount_balance += requestcash_ids.amount_balance
            return requestcash_ids.amount_balance
        elif context.get('id', False):
            requestcash_ids = self.pool.get('ekd.document.head.request').browse(context.get('active_id'))
            return requestcash_ids.amount_balance
        elif context.get('amount_payment', False):
            return context.get('amount_payment')
        else:
            return Decimal('0.0')

    def default_lines(self):
        context = Transaction().context
        if context.get('active_ids', False):
            lines_ids = self.pool.get('ekd.document.line.request').search([
                                    ('requestcash','in', context.get('active_ids'))
                                ])
            res = self.pool.get('ekd.document.line.request').read(lines_ids, [
                                'requestcash',
                                'name',
                                'note',
                                'analytic',
                                'product',
                                'uom',
                                'quantity',
                                'unit_digits',
                                'unit_price',
                                'amount_request',
                                'amount_received',
                                'amount_balance',
                                'amount_payment',
                                'state',
                                ])
            return  res
        elif context.get('active_id', False):
            lines_ids = self.pool.get('ekd.document.line.request').search([
                                ('requestcash','='.get('active_id'))
                                ])
            res = self.pool.get('ekd.document.line.request').read(lines_ids, [
                                'name',
                                'note',
                                'analytic',
                                'product',
                                'uom',
                                'quantity',
                                'unit_digits',
                                'unit_price',
                                'amount_request',
                                'amount_received',
                                'amount_balance',
                                'amount_payment',
                                'state',
                                ])
            return  res
        elif context.get('id', False):
            lines_ids = self.pool.get('ekd.document.line.request').search([
                                ('requestcash','='.get('id'))
                                ])
            res = self.pool.get('ekd.document.line.request').read(lines_ids, [
                                'name',
                                'note',
                                'analytic',
                                'product',
                                'uom',
                                'quantity',
                                'unit_digits',
                                'unit_price',
                                'amount_request',
                                'amount_received',
                                'amount_balance',
                                'amount_payment',
                                'state',
                                ])
            return  res
        else:
            raise Exception('Payment default_lines',str(context))
        return {}

    def documents_get(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
            ('model', '=', 'ekd.document.head.cash'),
            ('pole', '=', 'document_base_ref'),
            ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def on_change_with_amount_payment(self, values):
        amount = Decimal('0.0')
        for line in values['lines']:
            if line['amount_payment']:
                amount += Decimal(str(line['amount_payment']))
        return amount

    def on_change_amount_payment(self, values):
        amount = values['amount_payment']
        if values['amount_request'] == values['amount_payment']:
            for line in values['lines']:
                line['amount_payment'] = line['amount_balance'] 
        else:
            for line in values['lines']:
                if amount >= line['amount_balance']:
                    line['amount_payment'] = line['amount_balance']
                else:
                    line['amount_payment'] = amount
                    break
                amount -= line['amount_balance']
        return {'amount_request':values['amount_request'],
                'amount_payment':values['amount_payment'], 
                'lines': values['lines']}

    def on_change_with_type_transaction(self, values):
        template_obj = self.pool.get('ekd.document.template')
        template_id = template_obj.browse(values['template_cash'])
        return template_id.code_call

    def on_change_template_cash(self, values):
        template_obj = self.pool.get('ekd.document.template')
        template_id = template_obj.browse(values['template_cash'])
        return { 'type_transaction': template_id.code_call, }

DocumentPaymentCash()

class DocumentPaymentWizard(Wizard):
    'Payment in bank'
    _name = 'ekd.document.wizard.payment'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'ekd.document.wizard.payment.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('bank', 'Payment via bank', 'tryton-ok', True),
                    ('cash', 'Payment via cash', 'tryton-ok', True),
                        ],
                    },
                },

        'bank': {
            'actions': ['_load'],
            'result': {
                'type': 'form',
                'object': 'ekd.document.wizard.payment.bank',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('commit_bank', 'Payment', 'tryton-ok', True),
                        ],
                    },
                },

        'cash': {
            'actions': ['_load'],
            'result': {
                'type': 'form',
                'object': 'ekd.document.wizard.payment.cash',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('commit_cash', 'Payment', 'tryton-ok', True),
                        ],
                    },
                },

        'commit_bank': {
            'result': {
                'type': 'action',
                'action': '_bank',
                'state': 'end'
                        },
                },


        'commit_cash': {
            'result': {
                'type': 'action',
                'action': '_cash',
                'state': 'end'
                        },
                }
            }

    def _load(self, data):
        amount_request = Decimal('0.0')
        amount_received = Decimal('0.0')
        amount_balance = Decimal('0.0')
        amount_payment = Decimal('0.0')
        note_str = u"Документы:\n"
        context = Transaction().context
        Cycle_First = True
        document_obj = self.pool.get('ekd.document.head.request')
        for document_id in document_obj.browse(data['ids']):
            if Cycle_First:
                recipient_old = document_id.recipient
                Cycle_First = False

            if document_id.recipient != recipient_old :
                self.raise_user_error(cursor, error="Warning many recipient",
                                     error_description="Only one recipient in request cash!")
            note_str += u"%s\n"%(document_id.rec_name)
            amount_request += document_id.amount_request
            amount_received += document_id.amount_received
            amount_balance += document_id.amount_balance

            recipient_old = document_id.recipient

        if data['form']['amount_payment'] > 0:
            context['amount_payment'] = data['form']['amount_payment']
            return {'amount_request': amount_request,
                'amount_received': amount_received,
                'amount_balance': amount_balance,
                'amount_payment': data['form']['amount_payment'],
                    }
        else:
            return {'amount_request': amount_request,
                'amount_received': amount_received,
                'amount_balance': amount_balance,
                'amount_payment': amount_balance,
                    }

    def _bank(self, data):
        raise Exception('I am Sorry this develop!!!')

    def _cash(self, data):
        doc_cash_obj = self.pool.get('ekd.document.head.cash')
        payment_line_obj = self.pool.get('ekd.document.line.payment')
        if data['form']['description']:
            if isinstance(data['form']['description'], unicode):
                note_str = data['form']['description'] +u'\n'+ u'Строки заявки:'
            else:
                note_str = unicode(data['form']['description'], 'utf8')+\
                            u'\n'+ u'Строки заявки:'
        else:
            note_str = u'Строки заявки:'

        if data['form']['lines']:
            if data['form']['type_transaction'] == 'expense_cash':
                for state, line in data['form']['lines']:
                    if state == 'add':
                        continue
                    note_str += u'%s - сумма по заявке: %s, выдано: %s\n'%(line['name'], line['amount_request'], line['amount_payment'])
            else:
                for state, line in data['form']['lines']:
                    note_str += u'%s - сумма по заявке: %s, возврат суммы: %s\n'%(line['name'], line['amount_request'], line['amount_payment'])

        doc_cash_id = doc_cash_obj.create({
                            'template_cash': data['form']['template_cash'],
                            'date_account': data['form']['date_account'],
                            'type_transaction': data['form']['type_transaction'],
                            'document_base_ref': 'ekd.document.head.request,%s'%(data['id']),
                            'amount': data['form']['amount_payment'],
                            'cash_account':data['form']['cash_account'] or False,
                            'corr_account':data['form']['corr_account'] or False,
                            'from_to_party':data['form']['from_to_party'],
                            'note': note_str,
                            'child': data['id'],
                            'state_doc': 'draft'
                            })

        for state, line in data['form']['lines']:
            if state == 'add':
                continue

            elif state == 'create' and line['amount_payment'] != 0:
                payment_line_obj.create({
                            'doc_payment': doc_cash_id,
                            'doc_base': line['requestcash'],
                            'amount_payment': line['amount_payment'],
                            'line_request': line['id'],
                            'type_transaction': data['form']['type_transaction'],
                            'state': 'payment'
                            })

        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search([
                    ('fs_id', '=', 'act_documents_cash_form'),
                    ('module', '=', 'ekd_documents'),
                    ('inherit', '=', False),
                    ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        res = act_window_obj.read(model_data.db_id)
        res['res_id'] = doc_cash_id
        res['views'].reverse()
        return res

DocumentPaymentWizard()
