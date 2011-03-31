# -*- coding: utf-8 -*-
"Document"
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import In, Eval, Not, In, Equal, If, Get, Bool

_STATES = {
    'readonly': Equal(Eval('state'),'posted'),
    }
_DEPENDS = ['state']

class DocumentTemplate(ModelSQL, ModelView):
    "Document Template"
    _name='ekd.document.template'

    template_move = fields.Property(fields.Many2One('ekd.account.move.template',
            'Template Entry', domain=[('company','=', Eval('company'))]))
    template_account = fields.Property(fields.Many2One('ekd.account',
        'Template Account ', domain=[('company', '=', Eval('company'))]))
    template_tax_account = fields.Property(fields.Many2One('ekd.account',
        'Template Tax Account ', domain=[('company', '=', Eval('company'))]))

    taxes = fields.Many2Many('ekd.document.template-ekd.account.tax',
                            'template', 'tax', 'Taxes', domain=[('parent', '=', False)])

    def default_template_move(self):
        return Transaction().context.get('template_move') or False

DocumentTemplate()

class DocumentTemplateStage(ModelSQL, ModelView):
    "Document Template Stage"
    _name='ekd.document.template.stage'

    template_move = fields.Property(fields.Many2One('ekd.account.move.template',
            'Template Entry', domain=[('company','=', Eval('company'))]))
    template_account = fields.Property(fields.Many2One('ekd.account',
        'Template Account ', domain=[('company', '=', Eval('company'))]))
    template_tax_account = fields.Property(fields.Many2One('ekd.account',
        'Template Tax Account ', domain=[('company', '=', Eval('company'))]))

DocumentTemplateStage()

class DocumentTemplateTax(ModelSQL):
    'Template - Tax'
    _name = 'ekd.document.template-ekd.account.tax'
    _table = 'ekd_document_template_taxes_rel'
    _description = __doc__

    template = fields.Many2One('ekd.document.template', 'Template',
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('ekd.account.tax', 'Tax', ondelete='RESTRICT',
                                                required=True)
DocumentTemplateTax()

class Document(ModelSQL, ModelView):
    "Document"
    _name='ekd.document'

    move = fields.Many2One('ekd.account.move', 'Account Entry Lines',
                            states=_STATES, depends=_DEPENDS)
    account_document = fields.Property(fields.Many2One('ekd.account',
        'Account Document', domain=[('company', '=', Eval('company'))]))

    def post_accounting(self, model=None, ids=None, template_move=None, add_options={}):
        if model == None or ids == None:
            return
        model_obj = self.pool.get(model)
        template_move_obj = self.pool.get('ekd.account.move.template')
        for line in model_obj.browse(ids):
            template_move_obj.create_move({
                'document': [model, line.id, line],
                'template': line.template.template_move,
                'return': 'id',
                'add_options': add_options})

Document()
