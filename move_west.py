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

class LineWest(ModelSQL, ModelView):
    "Lines of business operations west standart"
    _name="ekd.account.move.line.west"
    _description=__doc__
    _inherits = {'ekd.account.move.line': 'line'}

    line = fields.Many2One('ekd.account.move.line', 'Entries', ondelete="CASCADE", states=_MOVE_STATES, depends=_MOVE_DEPENDS)
    period = fields.Many2One('ekd.period', 'Period')
    account = fields.Many2One('ekd.account', 'Debit Account',
            states={'readonly': Equal(Eval('state'), 'posted'),}, depends=_MOVE_DEPENDS,
            domain=[('kind', '!=', 'view'), ('company','=', Eval('company'))],
            on_change=['account', 'analytic_accounts'], select=1)
    dt_analytic_accounts = fields.One2Many('ekd.account.move.line.analytic_dt','move_line_west','Analytic for Account Debit')
    ct_analytic_accounts = fields.One2Many('ekd.account.move.line.analytic_ct','move_line_west','Analytic for Account Credit')
    analytic_01 = fields.Function(fields.Reference(selection='get_analytic_new',
                        string='First Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 1, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_02 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Second Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 2, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_03 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Third Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 3, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_04 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Fourth Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 4, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_05 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Fifth Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 5, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_06 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Sixth Level',
                        states={ 'invisible': Not(Greater(Eval('analytic_level', 0), 6, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')
    analytic_07 = fields.Function(fields.Reference(selection='get_analytic_new',  
                        string='Seventh Level',
                        states={ 'invisible': Not(Greater(Eval('dt_analytic_level', 0), 7, True)),
                                'readonly': Equal(Eval('state'), 'posted'), },
                        ), 'get_analytic', setter='set_analytic')

    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)), readonly=True)
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)), readonly=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'), 'get_currency_digits')
    kind = fields.Function(fields.Char('Kind Account Credit'),'get_kind_account')
    kind_analytic = fields.Function(fields.Char('Kind Account Debit'),'get_kind_account')
    acc_analytic = fields.Function(fields.Many2One('ekd.account.analytic',
                'Analytic Account Debit'),'get_kind_account')
    analytic_level = fields.Function(fields.Integer('Analytic Account Debit'),'get_kind_account')

    def __init__(self):
        super(LineWest, self).__init__()

    def get_analytic(self, ids, names):
        res = []
        if not ids:
            return {}
        res = {}
        for line in self.browse(ids):
            if line.dt_analytic_level > 0:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
                    for analytic_line in line.analytic_accounts:
                        if analytic_line.level == '01' and name == 'analytic_01':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '02'  and name == 'analytic_02':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '03' and name == 'analytic_03':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '04' and name == 'analytic_04':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '05' and name == 'analytic_05':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '06' and name == 'analytic_06':
                            res[name][line.id] = analytic_line.analytic
                        elif analytic_line.level == '07' and name == 'analytic_07':
                            res[name][line.id] = analytic_line.analytic
            else:
                for name in names:
                    res.setdefault(name, {})
                    res[name].setdefault(line.id, False)
        return res

    def set_analytic(self, ids, name, vals):
        res = []
        line_id = self.browse(ids[0])
        #raise Exception (name, str(vals))
        for analytic_line in line_id.dt_analytic_accounts:
            if analytic_line.level =='01' and name == 'dt_analytic_01':
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '01', 
                                    'analytic': vals,
                                    })
            elif analytic_line.level =='02' and name == 'dt_analytic_02':
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '02', 
                                    'analytic': vals,
                                    })
                #raise Exception(str(ids), str(vals))
            elif analytic_line.level =='03' and name == 'dt_analytic_03':
                #raise Exception(str(ids), str(vals))
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '03', 
                                    'analytic': vals,
                                    })
            elif analytic_line.level =='04' and name == 'dt_analytic_04':
                #raise Exception(str(ids), str(vals))
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '04', 
                                    'analytic': vals,
                                    })
            elif analytic_line.level =='05' and name == 'dt_analytic_05':
                #raise Exception(str(ids), str(vals))
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '05', 
                                    'analytic': vals,
                                    })
            elif analytic_line.level =='06' and name == 'dt_analytic_06':
                #raise Exception(str(ids), str(vals))
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '06', 
                                    'analytic': vals,
                                    })
            elif analytic_line.level =='07' and name == 'dt_analytic_07':
                #raise Exception(str(ids), str(vals))
                analytic_line.write( analytic_line.id, {
                                    'move_line':ids[0], 
                                    'level': '07', 
                                    'analytic': vals,
                                    })
        return True

    def get_analytic_new(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.level_analytic'),
                    ('pole', '=', 'type_analytic'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def get_kind_account(self, ids, names):
        if not ids:
            return {}
        res = {}
        for line in self.browse(ids):
            for name in names:
                res.setdefault(name, {})
                res[name].setdefault(line.id, False)
                if line.account:
                    if name =='kind':
                        res[name][line.id] = line.dt_account.kind
                    elif name =='kind_analytic':
                        res[name][line.id] = line.account.kind_analytic
                    elif name =='dt_acc_analytic':
                        res[name][line.id] = line.account.root_analytic.id
                    elif name =='dt_acc_analytic':
                        res[name][line.id] = line.account.root_analytic.id
                    elif name =='dt_analytic_level':
                        res[name][line.id] = len(line.account.level_analytic) or 0
                    elif name =='ct_analytic_level':
                        res[name][line.id] = len(line.account.level_analytic) or 0

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

    def on_change_account(self, vals):
        account_obj = self.pool.get('ekd.account')
        if vals.get('account'):
            account = account_obj.browse(vals['account'])
            analytic01 = False
            analytic02 = False
            analytic03 = False
            analytic04 = False
            analytic05 = False
            analytic06 = False
            analytic07 = False
            analytic_accounts = {}
            if account.level_analytic:
                analytic_level = len(account.level_analytic)
                for analytic in account.level_analytic:
                    if analytic.level == '01':
                        analytic01 = analytic.ref_analytic
                    elif analytic.level == '02':
                        analytic02 = analytic.ref_analytic
                    elif analytic.level == '03':
                        analytic03 = analytic.ref_analytic
                    elif analytic.level == '04':
                        analytic04 = analytic.ref_analytic
                    elif analytic.level == '05':
                        analytic05 = analytic.ref_analytic
                    elif analytic.level == '06':
                        analytic06 = analytic.ref_analytic
                    elif analytic.level == '07':
                        analytic07 = analytic.ref_analytic
                    analytic_accounts.setdefault('add', []).append({
                                    'level': analytic.level, 
                                    'analytic': analytic.ref_analytic})
                if vals.get('analytic_accounts'):
                    for line_analytic in vals.get('analytic_accounts'):
                        dt_analytic_accounts.setdefault('delete', line_analytic)

            else:
                dt_analytic_level = 0
                if vals.get('analytic_accounts'):
                    dt_analytic_accounts['remove'] = [x['id'] for x in vals.get('analytic_accounts')]
            return {'kind': account.kind,
                    'kind_analytic': account.kind_analytic,
                    'dt_acc_analytic': account.root_analytic.id,
                    'dt_analytic_level': dt_analytic_level,
                    'analytic_01': dt_analytic01,
                    'analytic_02': dt_analytic02,
                    'analytic_03': dt_analytic03,
                    'analytic_04': dt_analytic04,
                    'analytic_05': dt_analytic05,
                    'analytic_06': dt_analytic06,
                    'analytic_07': dt_analytic07,
                    'dt_analytic_accounts': dt_analytic_accounts,
                    }
        return {}

    def view_header_get(self, value, view_type='form'):
        journal_period_obj = self.pool.get('ekd.account.journal.period')
        if (not Transaction().context.get('journal')
                or not Transaction().context.get('period')):
            return value
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

LineWest()
