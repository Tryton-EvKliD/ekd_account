# -*- encoding: utf-8 -*-
#NOTE: Заявки на деньги
"Document Request for money"
from trytond.model import ModelView, ModelSQL, ModelStorage, fields
#from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import Eval, Equal
#import time
#import datetime

_LINE_STATES = {
    'readonly': Equal(Eval('state_doc'), 'draft'),
    }

_LINE_DEPENDS = ['state_doc']

# Строки документа (Заявки на деньги)
class DocumentRequestCashLine(ModelSQL, ModelView):
    "Document specifications of Request for money "
    _name='ekd.document.line.request'
    _description=__doc__

    analytic = fields.Many2One('ekd.account.analytic', 'Analytic Account', 
        domain=[('type','=','expense')], on_change=['name', 'note', 'analytic'],
        states=_LINE_STATES, depends=_LINE_DEPENDS, required=True)

    def on_change_analytic(self, vals):
        if vals.get('analytic'):
            analytic_obj = self.pool.get('ekd.account.analytic')
            analytic_id = budget_line_obj.browse(vals.get('analytic'))
            if vals.get('name'):
                return { 'name': "%s - (%s)"%(vals.get('name'), analytic_id.name) }
            else:
                return { 'name': analytic_id.name }
        else:
            return {}

DocumentRequestCashLine()
