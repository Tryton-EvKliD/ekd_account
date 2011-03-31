# -*- coding: utf-8 -*-
#NOTE: Кассовые документы
#TODO: Что делать?
"Document Cash"
from trytond.model import ModelStorage, ModelView, ModelSQL, fields
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.tools import safe_eval
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import In, Eval, Not, In, Equal, If, Get, Bool
from account import _PARTY, _PRODUCT, _MONEY
import time
import datetime
import logging

from pytils import numeral

_STATES = {
    'readonly': Equal(Eval('state_doc'),'posted'),
    }
_DEPENDS = ['state_doc']

class DocumentCash(ModelSQL, ModelView):
    "Documents of cash"
    _name='ekd.document.head.cash'
    _description=__doc__

    cash_account = fields.Many2One('ekd.account', 'Cash Account',
            states=_STATES, depends=_DEPENDS,
            domain=[
                ('kind_analytic', '=', 'money_cash'),
                ('company','=', Eval('company'))])
    corr_account = fields.Many2One('ekd.account', 'Corr. Account',
                states=_STATES, depends=_DEPENDS,
                domain=['OR', [
                    ('kind_analytic', 'in', _PARTY+_MONEY),
                    ('company','=', Eval('company'))],
                    [('type.code', '=', 'salary'), 
                     ('company','=', Eval('company'))]])

    balance = fields.Many2One('ekd.balances.finance', 'Book Cash', 
            states= {'invisible': Bool(Eval('date_balance')),})

    def default_cash_account(self):
        return Transaction().context.get('cash_account')

    def default_corr_account(self):
        return Transaction().context.get('corr_account')

    #def default_lines_payment(self):
    #    return Transaction().context.get('lines_payment') or []

    def on_change_document_base_ref(self, values):
        if not values.get('document_base_ref'):
            return {}
        res = {}
        model, model_ids = values.get('document_base_ref').split(',')
        if model and model_ids != '0':
            model_obj = self.pool.get(str(model))
            model_id = model_obj.browse(int(model_ids))
            res['document_base'] = model_ids
            res['amount']=model_id.amount
            res['child']=model_ids
            if values.get('type_transaction') == 'income_cash':
                res['from_to_party']=model_id.from_party.id
                res['income']=model_id.amount
                res['corr_account']=model_id.from_party.account_receivable
            if values.get('type_transaction') == 'return_cash':
                res['from_to_party']=model_id.from_party.id
                res['income']=model_id.amount
                res['corr_account']=model_id.from_party.account_receivable
            elif values.get('type_transaction') == 'expense_cash':
                res['from_to_party']=model_id.to_party.id
                res['expense']=model_id.amount
                res['corr_account']=model_id.to_party.account_payable
        return res

    def on_change_template_cash(self, values):
        if not values.get('template_cash'):
            return {}
        res={}
        template_obj = self.pool.get('ekd.document.template')
        template_ids = template_obj.browse(int(values.get('template_cash')))
        values['type_transaction'] = template_ids.code_call
        if values.get('document_base_ref'):
            model, model_ids = values.get('document_base_ref').split(',')
            if model and model_ids != '0':
                model_obj = self.pool.get(str(model))
                model_id = model_obj.browse(int(model_ids))
                res['amount']= model_id.amount
                if template_ids.code_call == 'income_cash' and model_id.from_party:
                    res['from_to_party']=model_id.from_party.id
                if template_ids.code_call == 'return_cash' and model_id.from_party:
                    res['from_to_party']=model_id.from_party.id
                elif template_ids.code_call == 'expense_cash' and model_id.to_party:
                    res['from_to_party']=model_id.to_party.id
                elif template_ids.template_account:
                    res['corr_account']=model_id.template.template_account.id
        return res


    def button_post(self, ids):
        return self.post(ids)

    def button_draft(self, ids):
        return self.draft(ids)

    def button_restore(self, ids):
        return self.draft(ids)

    def post(self, ids):
        sequence_obj = self.pool.get('ir.sequence')
        date_obj = self.pool.get('ir.date')
        book_cash_obj = self.pool.get('ekd.balances.finance')
        fiscalyear_obj = self.pool.get('ekd.fiscalyear')
        template_move_obj = self.pool.get('ekd.account.move.template')
        analytic_payment = []

        if isinstance(ids, (int, long)):
            ids = [ids]
        for document in self.browse(ids):
            if not document.balance:
                page_cash_id = book_cash_obj.search([
                            ('company','=',document.company),
                            ('date_balance','=',document.date_account),
                            ('account','=',document.cash_account)], limit=1)
                if not page_cash_id:
                    page_cash_id = book_cash_obj.create({
                            'company':document.company,
                            'date_balance': document.date_account,
                            'account': document.cash_account,
                            'state': 'open',
                            })

                else:
                    if isinstance(page_cash_id, list):
                        page_cash_id = page_cash_id[0]

            else:
                page_cash_id = document.balance

            if not page_cash_id:
                self.raise_user_error(error="Warning",
                            error_description="Don't Page Book Cash for document %s"%(document.name))
            elif not document.from_to_party:
                self.raise_user_error(error="Error",
                            error_description="Not find Party!")

            if document.lines_payment:
#                lines_payment_obj = self.pool.get('documents.payment.line')
                for line in document.lines_payment:
                    analytic_payment.append({'analytic':line.line_request.analytic,'amount':line.amount_payment})
                    line.write(line.id, {
                                            'state': 'done',
                                            })

            if document.template_cash.code_call == 'income_cash':
                add_options ={
                    'dt_account': document.cash_account,
                    'dt_analytic': {},
                    'ct_account': document.corr_account,
                    'ct_analytic': {
                        'party.party': 'party.party,%s'%(document.from_to_party.id),
                        'company.employee': 'company.employee,%s'%(document.from_to_party.id),
                        },
                    'analytic': analytic_payment,
                    'document_base_ref': document.document_base_ref,
                    }

            elif document.template_cash.code_call == 'expense_cash':
                add_options ={
                        'ct_account': document.cash_account,
                        'ct_analytic': {},
                        'dt_account': document.corr_account,
                        'dt_analytic': {
                            'party.party': 'party.party,%s'%(document.from_to_party.id),
                            'company.employee': 'company.employee,%s'%(document.from_to_party.id),
                            },
                        'analytic': analytic_payment,
                        'document_base_ref': document.document_base_ref,
                        }

            elif document.template_cash.code_call == 'return_cash':
                add_options ={
                        'ct_account': document.cash_account,
                        'ct_analytic': {},
                        'dt_account': document.corr_account,
                        'dt_analytic': {
                            'party.party': 'party.party,%s'%(document.from_to_party.id),
                            'company.employee': 'company.employee,%s'%(document.from_to_party.id),
                            },
                        'analytic': analytic_payment,
                        'document_base_ref': document.document_base_ref,
                        }

            if not document.number_our or not document.move:
                if not document.number_our:
                    fiscalyear = fiscalyear_obj.browse(
                            Transaction().context.get('fiscalyear'))
                    if fiscalyear.get_sequence_id(fiscalyear.id, document.template_cash.id):
                        reference = fiscalyear.get_sequence_id(document.template_cash.id)
                    elif document.template.sequence:
                        reference = sequence_obj.get_id(
                            document.template_cash.sequence.id)
                    else:
                        self.raise_user_error(error="Error",
                            error_description='Sequence for Document not find!')
                else:
                    reference = document.number_our

                self.write(document.id, {
                            'number_our': reference,
                            'balance': page_cash_id,
                                'state': 'posted',
                            'post_date': date_obj.today(),
                            'move': template_move_obj.create_move({
                                    'document':document,
                                    'template': document.template_cash.template_move,
                                    'return': 'id',
                                    'add_options': add_options
                                    })
                                })
            else:
                self.write(document.id, {
                            'state': 'posted',
                            'post_date': date_obj.today(),
                            'move': template_move_obj.change_move(
                                    {'document':document,
                                     'template': document.template_cash.template_move,
                                     'move': document.move,
                                     'return': 'id',
                                     'add_options': add_options,
                                    })
                                })

#        return document.move.post(document.move.id)


    def draft(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        document_ids = self.browse(ids)
        for document in document_ids:
            if document.move:
                document.move.post_cancel(document.move.id)
        self.write(ids, {
                'state': 'draft',
                })
        return

    # Схема удаления документа
    def delete(self, ids):
        cr = Transaction().cursor
        for document in self.browse(ids):
            if document.state == 'deleted' and document.deleting:
                cr.execute('DELETE FROM "ekd_document_head_cash" WHERE id=%s', (document.id,))
                cr.execute('DELETE FROM "ekd_document" WHERE id=%s', (document.id,))
                cr.execute('DELETE FROM "ekd_document_line_payment" WHERE doc_payment=%s', (document.id,))
            else:
                if document.state == 'posted' and document.move:
                    document.move.post_cancel(document.move.id)
                    document.move.delete(document.move.id)

                if document.lines_payment:
                    lines_payment_obj = self.pool.get('ekd.document.line.payment')
                    for line in document.lines_payment:
                        lines_payment_obj.write(line.id, {
                                            'state': 'deleted',
                                            })
                self.write(document.id, {'state': 'deleted', 'deleting':True})
        return True

DocumentCash()
