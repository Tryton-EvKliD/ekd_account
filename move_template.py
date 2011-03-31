# -*- coding: utf-8 -*- 
##############################################################################
#
##############################################################################
'MoveRU Templates'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.tools import safe_eval
from move import _DT_PARTY_STATES, _CT_PARTY_STATES
from account import _PARTY, _PRODUCT
from decimal import Decimal
import datetime
import re

EXP_CONVERT=re.compile('\+|\-|\*|\/')
FUNC_TOKEN=re.compile('\(|\,|\)')

_SECTION_ACCOUNTING=(
        ('cash','Cash'),
        ('bank','Bank'),
        ('supplier','Supplier'),
        ('customer','Customer'),
        ('other_party','Other Party'),
        ('employee','Employee'),
        ('expense','Expense'),
        ('goods','Goods'),
        ('fixed_assets','Fixed Assets'),
        ('material','Materials'),
        ('tax','Tax'),
        ('tax_social','Tax Social'),
        )

_FUNC = {
    'ru_RU':{
    u'оборот':'turnover',
    u'остаток':'balance',
    u'сумма':'amount',
    u'налогcумма':'amountTAX',
    u'налогпроцент':'percentTAX',
    u'текущийпериод':'period',
    u'текущийгод':'year',
    u'датаначала':'start_date',
    u'датаконец':'end_date',
    u'документ':'document',
    u'строка':'line',
    u'основныесредства':'fixed_assets',
    u'материалы':'material',
    u'товар':'goods',
    u'дебет':'debit',
    u'кредит':'credit',
    u'начала':'begin',
    u'конец':'end',
    u'счетдебет':'dt_account',
    u'счеткредит':'ct_account',
    }
}

_DESC_FUNC = {
    'ru_RU':u" Переменные: \n"\
            u"СчетДебет - Счет дебета строки проводки\n"\
            u"СчетКредит - Счет кредита строки проводки\n"\
            u"ОтКого - Контрагент От кого\n"\
            u"Кому - Контрагент Кому\n"\
            u"Год(Текущий) - Текущий финансовый год\n"\
            u"Период(Текущий) - Текущий период\n"\
            u"Дата(Текущая) - Текущий день\n"\
            u"Дата(Начала) - День начала периода включительно\n"\
            u"Дата(Конец) - День окончания периода включительно\n"
            u"Сумма(Документа) - Сумма по документу\n"\
            u"Сумма(Строки) - Сумма по каждой строке спецификации\n"\
            u" Функции: \n"\
            u"Оборот(Счет, (Дата Начала, Дата Окончания) |\n"\
            u"             (Начальный период, Период окончания), \n"
            u"        Тип [Дебет, Кредит]) - Оборот по счета за период\n"\
            u"Остаток(Счет, Период, Тип [Дебет, Кредит]) - Оcтаток\n"\
            u"         на начала периода по счета за период\n"\
            u"Налога(Тип налог, Тип показателя) - Сумма налогов по документу\n"\
}
class TemplateMoveRU(ModelSQL, ModelView):
    'Business Operations Templates'
    _name = "ekd.account.move.template"
    _description=__doc__

    company = fields.Many2One('company.company', 'Company',
                ondelete="RESTRICT")
    name = fields.Char('Name Template', size=None)
    note = fields.Text('Note')
    description = fields.Text('Note')
    marker = fields.Many2One('ekd.account.move.marker', 'Additional marker')
    document_ref = fields.Selection('get_reference',  string='Credit analytic account')
    document2_ref = fields.Selection('get_reference2',  string='Credit analytic account')
    section_acc = fields.Selection(_SECTION_ACCOUNTING,  string='Section Accounting')
    from_party = fields.Many2One('party.party', 'From Party')
    to_party = fields.Many2One('party.party', 'To Party')
    lines = fields.One2Many('ekd.account.move.line.template', 'move', 'Account Entry Lines')
    type_move = fields.Selection([
            ('expense', 'Expense'),
            ('income', 'Income'),
            ('supplier','Supplier'),
            ('customer','Customer'),
            ('realization','Realization'),
            ('salary','Salary'),
            ('cost','Cost'),
            ('cash','Cash'),
            ('bank','Bank'),
            ('goods','The goods'),
            ('materials','Materials'),
            ('means','The basic means'),
            ('person','Accountable persons'),
            ('other','Other'),
            ], string='Credit analytic account')

    active = fields.Boolean('Active')
    posted = fields.Boolean('Post in accounting')
    deleting = fields.Boolean('Flag deleting', readonly=True)

    def __init__(self):
        super(TemplateMoveRU, self).__init__()
        self._function_template={
            'turnover':self._turnover,
            'balance':self._balance,
            'tax':self._tax
            }

        self._rpc.update({
            'button_test': True,
            })

        self._order.insert(0, ('name', 'ASC'))


    def default_company(self):
        return Transaction().context.get('company') or False

    def default_active(self):
        return True

    def get_reference(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.move'),
                    ('pole', '=', 'document_ref'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def get_reference2(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.move'),
                    ('pole', '=', 'document2_ref'),
                    ])
        for diction in dictions_obj.browse(diction_ids):
            res.append([diction.key, diction.value])
        return res

    def button_test(self, ids, values):
        for line in self.browse(ids):
            if '@' in line.amount:
                return True
        return True

    def get_template_line(self, move_template):
        res={}
        return res

    def get_document_line(self, document):
        res={}
        return res

    def get_head_template(self, document, template):
        res={}
        res['company'] = document.company.id
        res['from_party'] = document.from_party.id
        res['to_party'] = document.to_party.id
        res['template_move'] = template.id
        if template.name:
            res['name'] = template.name
        if template.note and 'note' in template.note:
            res['note'] = document.note
        res['date_operation'] = document.date_account
        res['document_ref'] = '%s,%s'%(document.template.model.model, document.id)
        return res

    def create_move(self, values):
        u'''
        Создание проводки на основе документа и шаблона
        Ожидаемая структура списка values
        {'document':BrowseRecord() - заголовок документа,
         'lines':BrowseRecord() - строки документа,
         'template':BrowseRecord() - шаблон проводки,
         'return':'id' or 'entry' - тип возвращаемого значения,
         'add_options':{
            Шаблоны для дополнения шаблона проводки
            'dt_account': ID account,
            'dt_analytic': {
                    'объект аналитики': Значение,
                            },
            'ct_account': ID account,
            'ct_analytic': {
                    'объект аналитики': Значение,
                            },
            'analytic': [{аналитика: сумма},{...}],
            Ниже готовые проводки 
            'entries': ({
                'dt_account': ID account,
                'dt_analytic': [('create',{
                    'имя аналитики': Значение,
                            }),...],
                'ct_account': ID account,
                'ct_analytic': [('create',{
                    'имя аналитики': Значение,
                            }),...],
                'product':,
                'uom':,
                'quantity':,
                'unit_price'
                'amount': Сумма,
                    },...)
            }
        }
        Ожидаемые случаи обработки
        1. Обработка товарного документа (приход расход)
            1.1. Случай простого прихода по одному документу один вид ТМЦ (ОС, Нематер.актив, Материалы, Товары)
            1.2. Случай сложного прихода по одному документу разные вид ТМЦ (ОС, Нематер.актив, Материалы, Товары)
            1.3. Случай простого расхода по одному документу один вид ТМЦ (ОС, Нематер.актив, Материалы, Товары)
            1.4. Случай сложного расхода по одному документу разные вид ТМЦ (ОС, Нематер.актив, Материалы, Товары)
        2. Обработка кассового документа простая (Приход, Расход)
        3. Обработка кассового документа сложная (Обычно Расход)
            Списание с кассы в подотчет и сразу списание на расходы
        4. Обработка документа простая (Приход, Расход)
        5. Обработка документа сложная (Обычно Расход с использованием аналитики)
        '''
        
        if not values:
            return False
        elif not values.get('template'):
            self.raise_user_error(error='Error',\
                error_description="Please relation template document\n"\
                                  " with template entry ")
        elif not values.get('document'):
            self.raise_user_error(error='Error',\
                error_description="Please get document\n"\
                                  " with model of document")
        #elif not values['document'].model.id:
        #    self.raise_user_error(error='Error',\
        #        error_description="Please relation template document\n"\
        #                          " with model of document")

        account_obj = self.pool.get('ekd.account')
        move_obj = self.pool.get('ekd.account.move')
        

        # Заполнение полей заголовка проводки
        entry = self.get_head_template(values['document'], values['template'])
        entry['document2_ref'] = values['add_options'].get('document_base_ref', False)
        entry['lines'] = []

        # Обработка строк шаблона проводки
        # Приоритет данных
        # 1. Счет из шаблона проводки (прямой)
        # 2. Счет из шаблона проводки (по коду счета)
        # 3. Счет из документа 
        if values.get('lines'):
            for line_doc in values['lines'].lines:
                # Формирование строк проводки по шаблону
                for line in values['template'].lines:
                    entry_line = {}
                    entry_line_analytic = {}
                    if line.dt_account:
                        entry_line['dt_account'] = line.dt_account
                    elif line.dt_account_txt:
                        self.raise_user_error(error='Error', error_descrioption='This properties not released (debit account text)')
                    elif values['add_options'].get('dt_account'):
                        entry_line['dt_account'] = values['add_options'].get('dt_account')
                    else:
                        entry_line['dt_account'] = False

                    if line.ct_account:
                        entry_line['ct_account'] = line.ct_account
                    elif line.ct_account_txt:
                        self.raise_user_error(error='Error',
                            error_descrioption='This properties not released (credit account text)')
                    elif values['add_options'].get('ct_account'):
                        entry_line['ct_account'] = values['add_options'].get('ct_account')
                    else:
                        entry_line['ct_account'] = False
        
                    if entry_line.get('dt_account'):
                        dt_account_brw = account_obj.browse(entry_line['dt_account'])
                    if entry_line.get('ct_account'):
                        ct_account_brw = account_obj.browse(entry_line['ct_account'])

                    if dt_account_brw and ct_account_brw and dt_account_brw.kind != ct_account_brw.kind:
                        if (dt_account_brw.kind == 'balance' and ct_account_brw.kind != 'balance') or\
                             (dt_account_brw.kind != 'balance' and ct_account_brw.kind == 'balance'):
                            self.raise_user_error(error='Error', 
                                error_description="Don't balance and off-balance \n"\
                                        " accounts: %s - %s"%(dt_account_brw.code, ct_account_brw.code))
                        elif dt_account_brw.kind in ['off_balance', 'off_balance_out'] and\
                             ct_account_brw.kind in ['off_balance', 'off_balance_out']:
                            self.raise_user_error(error='Error', 
                                error_description="Don't off-balance and off-balance"\
                                        " account %s - %s"%(dt_account_brw.code, ct_account_brw.code))

                    # Обработка аналитических данных по дебету
                    if dt_account_brw:
                        entry_line['dt_analytic_accounts'] = self.get_analytic_account(
                                                    dt_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'))

                    # Обработка аналитических данных по кредиту
                    if ct_account_brw:
                        entry_line['ct_analytic_accounts'] = self.get_analytic_account(
                                                    ct_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'))

                    if dt_account_brw.kind_analytic in _PRODUCT or \
                        ct_account_brw.kind_analytic in _PRODUCT:
                        entry_line['product'] = values['add_options'].get('product').get('product')
                        entry_line['product_uom'] = values['add_options'].get('product').get('product_uom')
                        entry_line['quantity'] = values['add_options'].get('product').get('quantity')
                        entry_line['unit_price'] = values['add_options'].get('product').get('unit_price')


            entry_line['amount'] = self.compute_formula(line.id, 
                        line.amount,{
                            'AmountDoc': values['document'].amount,
                            'AmountLine': line.amount,
                            })

            entry_tmp['lines'].append(('create', entry_line))

        # Обработка простого документа без спецификации
        else:
            for line in values['template'].lines:
                entry_line = {}
                dt_account_brw = None
                ct_account_brw = None
                entry_line_dt_analytic = []
                entry_line_ct_analytic = []
                if line.dt_account:
                    entry_line['dt_account'] = line.dt_account.id
                elif line.dt_account_txt:
                        self.raise_user_error(error='Error', 
                            error_descrioption='This properties not released (debit account text)')
                elif values['add_options'].get('dt_account'):
                    entry_line['dt_account'] = values['add_options'].get('dt_account').id
                else:
                    entry_line['dt_account'] = False
        
                if line.ct_account:
                    entry_line['ct_account'] = line.ct_account.id
                elif line.ct_account_txt:
                        self.raise_user_error(error='Error', 
                                error_descrioption='This properties not released (credit account text)')
                elif values['add_options'].get('ct_account'):
                    entry_line['ct_account'] = values['add_options'].get('ct_account').id
                else:
                    entry_line['ct_account'] = False

                dt_account_brw = account_obj.browse(entry_line.get('dt_account', []))
                ct_account_brw = account_obj.browse(entry_line.get('ct_account', []))

                if dt_account_brw and ct_account_brw and dt_account_brw.kind != ct_account_brw.kind:
                    if (dt_account_brw.kind == 'balance' and ct_account_brw.kind != 'balance') or\
                         (dt_account_brw.kind != 'balance' and ct_account_brw.kind == 'balance'):
                        self.raise_user_error(error='Error', 
                            error_description="Don't balance and off-balance \n"\
                                    " accounts: %s - %s"%(dt_account_brw.code, ct_account_brw.code))
                    elif dt_account_brw.kind in ['off_balance', 'off_balance_out'] and\
                         ct_account_brw.kind in ['off_balance', 'off_balance_out']:
                        self.raise_user_error(error='Error', 
                            error_description="Don't off-balance and off-balance"\
                                    " account %s - %s"%(dt_account_brw.code, ct_account_brw.code))

                # Обработка аналитических данных по дебету
                if dt_account_brw and dt_account_brw.level_analytic:
                    entry_line['dt_analytic_accounts'] = self.get_analytic_account(
                                                    dt_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'),
                                                    line.dt_analytic or 'debit')

                # Обработка аналитических данных по кредиту
                if ct_account_brw and ct_account_brw.level_analytic:
                    entry_line['ct_analytic_accounts'] = self.get_analytic_account(
                                                    ct_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'),
                                                    line.ct_analytic or 'credit')

                if dt_account_brw.kind_analytic in _PRODUCT or \
                    ct_account_brw.kind_analytic in _PRODUCT:
                    entry_line['product'] = values['add_options'].get('product').get('product')
                    entry_line['product_uom'] = values['add_options'].get('product').get('product_uom')
                    entry_line['quantity'] = values['add_options'].get('product').get('quantity')
                    entry_line['unit_price'] = values['add_options'].get('product').get('unit_price')

                entry_line['company'] = values['document'].company.id
                entry_line['template_line'] = line.id
                entry_line['date_operation'] = entry.get('date_operation')
                entry_line['amount'] = self.compute_formula(line.id, 
                            line.amount,{
                            'AmountDoc': values['document'].amount,
                            'AmountLine': values['document'].amount,
                            'AmountTax': values['document'].amount,
                            })

                entry['lines'].append(('create', entry_line))
                #raise Exception(str(entry))
            
        #raise Exception(str(entry))
        if values.get('return') == 'id':
            new_id =  move_obj.create(entry)
            return new_id
        else:
            return entry

    def get_analytic_account(self, account, dt_analytic, ct_analytic, side_analytic):
        line_analytic = []
        #raise Exception(side_analytic, str(dt_analytic))
        if side_analytic == 'debit':
            for level_analytic in account.level_analytic:
                model, model_id = level_analytic.ref_analytic.split(',',1)
                line_analytic.append(('create', {
                                        'level': level_analytic.level,
                                        'analytic': dt_analytic.get(model)
                                        }))
        else:
            for level_analytic in account.level_analytic:
                model, model_id = level_analytic.ref_analytic.split(',',1)
                line_analytic.append(('create', {
                                        'level': level_analytic.level,
                                        'analytic': ct_analytic.get(model)
                                        }))
        return line_analytic

    def change_move(self, values):
        ''' 
        Изменение проводки на основе документа и шаблона
        Ожидаемая структура списка values
            {'document':Browse(), 
             'template':Browse(),
             'move':Browse(),
             'return':'id',
             'add_options':{
                }
            }
             Случаи изменение строк проводок
             1. По полю template_move
        '''
        if not values:
            return False

        account_obj = self.pool.get('ekd.account')
        move_obj = self.pool.get('ekd.account.move')
        move_line_obj = self.pool.get('ekd.account.move.line')
        flag_analytic = True

        # Заполнение полей заголовка проводки
        entry_old = move_obj.read(values['move'].id)
        if values['move'].template_move.id != values['template'].id:
            self.raise_user_error(error='Error', error_description="Find other template move!\nPlease before remove entry")
        entry = self.get_head_template(values['document'], values['template'])
        entry['document2_ref'] = values['add_options'].get('document_base_ref', False)
        #raise Exception(str(values['document']))

        # Обработка строк шаблона проводки
        # Приоритет данных
        # 1. Счет из шаблона проводки (прямой)
        # 2. Счет из шаблона проводки (по коду счета)
        # 3. Счет из документа 
        if values.get('lines'):
            raise Exception(str(values['document'].lines))
            for line_doc in values['document'].lines:
                # Формирование строк проводки по шаблону
                for line in values['template'].lines:
                    entry_line = {}
                    if values['add_options'].get('dt_account'):
                        entry_line['dt_account'] = values['add_options'].get('dt_account')
                    elif line.dt_account:
                        entry_line['dt_account'] = line.dt_account
                    else:
                        entry_line['dt_account'] = False
        
                    if values['add_options'].get('ct_account'):
                        entry_line['ct_account'] = values['add_options'].get('ct_account')
                    elif line.ct_account:
                        entry_line['ct_account'] = line.ct_account
                    else:
                        entry_line['ct_account'] = False
        
                    if entry_line.get('dt_account'):
                        dt_account_brw = account_obj.browse(entry_line['dt_account'])
                    if entry_line.get('ct_account'):
                        ct_account_brw = account_obj.browse(entry_line['ct_account'])

                    if dt_account_brw.kind =='balance':
                        if ct_account_brw.kind !='balance':
                            self.raise_user_error(error='Error', \
                                error_descriptions="Don't balance and off-balance account")
                    elif dt_account_brw.kind =='off_balance':
                        if ct_account_brw.kind =='balance':
                            self.raise_user_error(error='Error', \
                                error_descriptions="Don't balance and off-balance account")
                    elif dt_account_brw.kind =='off_balance_out':
                        if ct_account_brw.kind =='balance':
                            self.raise_user_error(error='Error', \
                                error_descriptions="Don't balance and off-balance account")
                    else:
                        self.raise_user_error(error='Error', \
                            error_descriptions='Unknown kind dt_account for create entry %s'%(dt_account_brw.kind))

                    # Обработка аналитических данных по дебету
                    if dt_account_brw and dt_account_brw.level_analytic:
                        entry_line['dt_analytic_accounts'] = self.get_analytic_account(
                                        dt_account_brw, 
                                        values['add_options'].get('dt_analytic'),
                                        values['add_options'].get('ct_analytic'),
                                        line.dt_analytic or 'debit')

                    # Обработка аналитических данных по кредиту
                    if ct_account_brw and ct_account_brw.level_analytic:
                        entry_line['ct_analytic_accounts'] = self.get_analytic_account(
                                        ct_account_brw, 
                                        values['add_options'].get('dt_analytic'),
                                        values['add_options'].get('ct_analytic'),
                                        line.ct_analytic or 'credit')

                    if dt_account_brw.kind_analytic in _PRODUCT or \
                        ct_account_brw.kind_analytic in _PRODUCT:
                        entry_line['product'] = values['add_options'].get('product').get('product')
                        entry_line['product_uom'] = values['add_options'].get('product').get('product_uom')
                        entry_line['quantity'] = values['add_options'].get('product').get('quantity')
                        entry_line['unit_price'] = values['add_options'].get('product').get('unit_price')

                    entry_line['amount'] = self.compute_formula(line.id, 
                        line.amount,{
                            'AmountDoc': values['document'].amount,
                            'AmountLine': line.amount,
                            })
        # Обработка простого документа без спецификации
        else:
            for line in values['template'].lines:
                entry_line = {}
                dt_account_brw = None
                ct_account_brw = None
                if line.dt_account:
                    entry_line['dt_account'] = line.dt_account.id
                elif line.dt_account_txt:
                        self.raise_user_error(error='Error', 
                            error_descrioption='This properties not released (debit account text)')
                elif values['add_options'].get('dt_account'):
                    entry_line['dt_account'] = values['add_options'].get('dt_account').id
                else:
                    entry_line['dt_account'] = False
        
                if line.ct_account:
                    entry_line['ct_account'] = line.ct_account.id
                elif line.ct_account_txt:
                        self.raise_user_error(error='Error', 
                                error_descrioption='This properties not released (credit account text)')
                elif values['add_options'].get('ct_account'):
                    entry_line['ct_account'] = values['add_options'].get('ct_account').id
                else:
                    entry_line['ct_account'] = False

                dt_account_brw = account_obj.browse(entry_line.get('dt_account', []))
                ct_account_brw = account_obj.browse(entry_line.get('ct_account', []))

                if dt_account_brw and ct_account_brw and dt_account_brw.kind != ct_account_brw.kind:
                    if (dt_account_brw.kind == 'balance' and ct_account_brw.kind != 'balance') or\
                         (dt_account_brw.kind != 'balance' and ct_account_brw.kind == 'balance'):
                        self.raise_user_error(error='Error', 
                            error_description="Don't balance and off-balance \n"\
                                    " accounts: %s - %s"%(dt_account_brw.code, ct_account_brw.code))
                    elif dt_account_brw.kind in ['off_balance', 'off_balance_out'] and\
                         ct_account_brw.kind in ['off_balance', 'off_balance_out']:
                        self.raise_user_error(error='Error', 
                            error_description="Don't off-balance and off-balance"\
                                    " account %s - %s"%(dt_account_brw.code, ct_account_brw.code))

                # Обработка аналитических данных по дебету
                if dt_account_brw and dt_account_brw.level_analytic:
                    entry_line['dt_analytic_accounts'] = self.get_analytic_account(
                                                    dt_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'),
                                                    line.dt_analytic or 'debit')

                # Обработка аналитических данных по кредиту
                if ct_account_brw and ct_account_brw.level_analytic:
                    entry_line['ct_analytic_accounts'] = self.get_analytic_account(
                                                    ct_account_brw, 
                                                    values['add_options'].get('dt_analytic'),
                                                    values['add_options'].get('ct_analytic'),
                                                    line.ct_analytic or 'credit')

                if dt_account_brw.kind_analytic in _PRODUCT or \
                    ct_account_brw.kind_analytic in _PRODUCT:
                    entry_line['product'] = values['add_options'].get('product').get('product')
                    entry_line['product_uom'] = values['add_options'].get('product').get('product_uom')
                    entry_line['quantity'] = values['add_options'].get('product').get('quantity')
                    entry_line['unit_price'] = values['add_options'].get('product').get('unit_price')

                entry_line['template_line'] = line.id
                entry_line['company'] = values['document'].company.id
                entry_line['move'] = values['move'].id
                entry_line['date_operation'] = entry.get('date_operation')
                flag_not_find = True

                entry_line['amount'] = self.compute_formula(line.id, 
                        line.amount,{
                            'AmountDoc': values['document'].amount,
                            'AmountDocTax': values['document'].amount,
                            'AmountLine': values['document'].amount,
                            'AmountLineTax': values['document'].amount,
                            })
                #raise Exception(str(entry_line))
                for line_old in values['move'].lines:
                    if line_old.template_line.id == line.id and\
                       line_old.state != 'deleted':
                        #raise Exception(str(entry_line))
                        move_line_obj.delete(line_old.id)
                        move_line_obj.create(entry_line)
                        flag_not_find = False
                        break
                if flag_not_find:
                    move_line_obj.create(entry_line)

        entry_old.update(entry)
        del entry_old['lines']
        if values.get('return') == 'id':
            move_obj.write( values['move'].id, entry_old)
            #move_obj.post(values['move'].id)
            return values['move'].id
        else:
            return entry_old

    def _turnover(self, values):
        '''
        Ожидаемые запросы:
            - Оборот по 
                - счету или счетам 
                - за период, периоды или определенный отрезок времени
                - дебетовый, кредитовый, свернутый
        values: diction with struct
        {'accounts':[],
         'period':{
            'StartDate': date,
            'EndDate': date,
            'Periods': [] - IDs ekd.period,
            },
         'type_turnover': ['debit', 'credit']
         }

        Return Decimal(Amount)
        '''
        line_obj = self.pool.get('ekd.account.move.line')
        balance_obj = self.pool.get('ekd.balances.account')
        period_obj = self.pool.get('ekd.period')
        res = {}
        res['debit'] = Decimal('0.0')
        res['credit'] = Decimal('0.0')
        if values.get('period').get('Periods'):
            for line in balance_obj.search_read([
                    ('period','in',values.get('period').get('Periods')),
                    ('account','in',values.get('accounts'))]):
                for type in values.get('type_turnover'):
                    res[type] += line[type]
        #raise Exception(str(values))

        elif values.get('period').get('StartDate'):
            cursor = Transaction().cursor
            cursor.execute('SELECT dt_account, ct_account, SUM(COALESCE(amount)) FROM account_ru_move_line '\
                    'WHERE state=\'posted\' AND date_operation >= %s AND date_operation <= %s AND '\
                    '( dt_account in ('+','.join(map(str, values.get('accounts')))+') OR'\
                    '  ct_account in ('+','.join(map(str, values.get('accounts'))) +'))'\
                    'GROUP BY dt_account, ct_account',
                        (values.get('period').get('StartDate'), 
                         values.get('period').get('EndDate')))
            for dt_account, ct_account, amount in cursor.fetchall():
                if dt_account in values.get('accounts'):
                    res['debit'] += amount
                if ct_account in values.get('accounts'):
                    res['credit'] += amount
                
        else:
            raise Exception('Error in _turnover', 'Not found period')

        if values.get('type_turnover') == 0:
            return res['debit']-res['credit']
        elif values.get('type_turnover') == 1:
            return res['debit']
        elif values.get('type_turnover') == -1:
            return res['credit']
        else:
            raise Exception('Error in _turnover', 'Not found Type turnover')

    def _balance(self, values):
        '''
        Вероятные запросы:
            Остаток на дату, 
            Остаток на начала или конец периода,
            Остаток на начала или конец финансового года. 
            - дебетовый, кредитовый, свернутый
        values: diction with struct
        {'accounts':,
         'period':{
            'Date': date,
            'Period': ID ekd.period,
            'Year': ID ekd.fiscalyear,
            },
         'type_balance': [begin, end]
         'type_turnover': [debit, credit, balance]
         }
        '''
        balance_obj = self.pool.get('ekd.balances.account')
        period_obj = self.pool.get('ekd.period')
        context = Transaction().context
        balance_amount = Decimal('0.0')

        if values.get('period').get('Date'):
            period_date = period_obj.search_read([
                    ('company','=', context.get('company')),
                    ('start_date','<=',values.get('period').get('Date')),
                    ('end_date','>=',values.get('period').get('Date')),
                    ], limit=1, fields_names=['id', 'start_date'])
            if not period_date:
                raise Exception(str(period_date))

            balance_ids = balance_obj.search([
                    ('company','=', context.get('company')),
                    ('period','=',period_date.get('id')),
                    ('account','in',values.get('accounts')),
                    ])
            if values.get('type_turnover') == 'debit':
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance_dt

            elif values.get('type_turnover') == 'credit':
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance_ct

            elif values.get('type_turnover') == 'balance':
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance

            return balance_amount + self._turnover({
                    'accounts': values.get('accounts'),
                    'period':{
                        'StartDate': period_date.get('start_date'),
                        'EndDate': values.get('period').get('Date'),
                        },
                     'type_turnover': 0
                    })

        elif values.get('period').get('Periods'):
            balance_ids = balance_obj.search([
                    ('company','=', context.get('company')),
                    ('period','in',values.get('period').get('Periods')),
                    ('account','in',values.get('accounts')),
                    ])

            if values.get('type_balance') == 'begin':
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance
            else:
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance_end
            return balance_amount

        elif values.get('period').get('Year'):

            if values.get('type_balance') == 'begin':
                period_year = period_obj.search([
                    (' fiscalyear','=', values.get('period').get('Year')),
                    ], limit=1, order=[('start_date', 'ASC')])
                balance_ids = balance_obj.search([
                    ('company','=', context.get('company')),
                    ('period','=', period_year[0]),
                    ('account','in',values.get('accounts')),
                    ])
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance

            else:
                period_years = period_obj.search([
                    (' fiscalyear','=', values.get('period').get('Year')),
                    ], order=[('end_date', 'DESC')])
                for period_year in period_years:
                    balance_ids = balance_obj.search([
                        ('company','=', context.get('company')),
                        ('period','=',period_year),
                        ('account','in',values.get('accounts')),
                        ])
                    if balance_ids:
                        break
                for balance in balance_obj.browse(balance_ids):
                    balance_amount += balance.balance_end

            return balance_amount

        return Decimal('0.0')

    def _tax(self, values):
        '''
        values: diction with struct
        {'cod': ID ekd.tax,
         'date': date
         'type_value': amount, percentage, name, code 
         }
        '''

        return 0.0

    def turnover(self, accounts, periods=[], party=None, type_turnover=0):
        if isinstance(accounts, unicode):
            pass
        elif isinstance(accounts, (int, long)):
            pass
        elif isinstance(accounts, bool):
            return Decimal('0.0')
            
        if len(periods) == 1:
            if isinstance(periods[0], (int, long)):
                period = {'Period': periods[0]}
            
        elif len(periods) >= 2:
            if isinstance(periods[0], datetime.date):
                period = {'StartDate': periods[0], 'EndDate': periods[1]}
            elif isinstance(periods[0], (int, long)):
                period = {'Period': periods}
        if isinstance(accounts, (int, long)):
            accounts = [accounts]

        return self._turnover(
                {'accounts':accounts,
                 'period':period,
                 'party': party,
                 'type_turnover': type_turnover,
                 })

    def period(self, periods=None):
        return periods

    def date(self, dates=None):
        return dates

    def balance(self, accounts, periods=None, party=None, type_balance=0):
        '''
        {
                    'Date': date,
                    'Period': ID ekd.period,
                    'Year': ID ekd.fiscalyear,values['move']
                    }
        '''
        if isinstance(accounts, bool):
            return Decimal('0.0')

        if periods != None:
            if isinstance(periods, datetime.date):
                period = {'Date': periods}
            elif isinstance(periods, (int, long)):
                period = {'Period': periods}

        if isinstance(accounts, (int, long)):
            accounts = [accounts]
            
        return self._balance(
                {'accounts':accounts,
                 'period':period,
                 'party': party,
                 'type_balance': type_balance,
                 })

    def compute_formula(self, id, formula, values={}):
        minus = 1
        if formula[:1] == '-':
            minus = -1
            formula = formula[1:]
        if formula == 'AmountDoc':
            return values['AmountDoc']*minus
        elif formula == 'AmountLine':
            return values['AmountLine']*minus
        elif formula == 'AmountAnalytic':
            return values['AmountAnalytic']*minus
        elif formula == 'AmountTax':
            return values['AmountTax']*minus
        #raise Exception(str(values))
       
        context = Transaction().context
        line_obj = self.pool.get('ekd.account.move.line.template')
        line = line_obj.browse(id)

        return safe_eval(formula, {
                    'turnover': self.turnover,
                    'balance': self.balance,
                    'Period': self.period,
                    'Date': self.date,
                    'FromParty': line.ct_analytic,
                    'ToParty': line.dt_analytic,
                    'AccountDt': line.dt_account.id,
                    'AccountCt': line.ct_account.id,
                    'Debit': 1,
                    'Credit': -1,
                    'AmountDoc': Decimal('0.0'),
                    'AmountDocTax': Decimal('0.0'),
                    'AmountLine': Decimal('0.0'),
                    'AmountLineTax': Decimal('0.0'),
                    'AmountAnalytic': Decimal('0.0'),
                    'AmountFixed': Decimal('0.0'),
                    'AmountIntagible': Decimal('0.0'),
                    'AmountMaterial': Decimal('0.0'),
                    'AmountGoods': Decimal('0.0'),
                    'AmountSupplier': Decimal('0.0'),
                    'AmountCustomer': Decimal('0.0'),
                    'AmountEmployee': Decimal('0.0'),
                    'CurrentPeriod': context.get('current_period'),
                    'FiscalYear': context.get('fiscalyear'),
                    'StartDate': context.get('start_period'),
                    'EndDate': context.get('end_period'),
                    'CurrentDate': context.get('current_date'),
                    }.update(values))

TemplateMoveRU()

class TemplateLineRU(ModelSQL, ModelView):
    "Lines of template business operations"
    _name="ekd.account.move.line.template"
    _description=__doc__

    move = fields.Many2One('ekd.account.move.template', 'Head Entries', ondelete="RESTRICT")
    code_line = fields.Char('Code Line', size=20)
    name = fields.Char('Name', size=None)
    dt_account_txt = fields.Char('Debit Account', size=50, 
                help=u"Маска счета - {контекст} - {организация}")
    dt_account = fields.Many2One('ekd.account', 'Debit Account',
                domain=[('kind', 'not in', ('view','section')), ('company','=', Eval('company'))],
                select=1)

    dt_analytic = fields.Selection([
                ('credit','Use Credit Analytic'),
                ('debit', 'Use Debit Analytic'),
                ], 'Use Side Analytic')
    ct_account_txt = fields.Char('Credit Account', size=50, 
                help=u"Маска счета - {контекст} - {организация}")
    ct_account = fields.Many2One('ekd.account', 'Credit Account',
                domain=[('kind', 'not in', ('view','section')), ('company','=', Eval('company'))],
                select=1)

    ct_analytic = fields.Selection([
                ('credit','Use Credit Analytic'),
                ('debit', 'Use Debit Analytic'),
                ], 'Use Side Analytic')
    amount = fields.Text('Formula', help=_DESC_FUNC.get('ru_RU'))
    dt_kind = fields.Function(fields.Char('Kind Account Debit'),'get_kind_account')
    dt_kind_analytic = fields.Function(fields.Char('Kind Account Debit'),'get_kind_account')
    ct_kind = fields.Function(fields.Char('Kind Account Credit'),'get_kind_account')
    ct_kind_analytic = fields.Function(fields.Char('Kind Account Credit'),'get_kind_account')
    
    deleted = fields.Boolean('Flag deleting')

    def __init__(self):
        super(TemplateLineRU, self).__init__()

        self._rpc.update({
            'button_test': True,
            })

        self._order.insert(0, ('code_line', 'ASC'))

        self._error_messages.update({
            'test_formula_yes': 'Formula Ok!',
            })

    def default_dt_analytic(self):
        return 'debit'

    def default_ct_analytic(self):
        return 'credit'

    def default_amount(self):
        return 'AmountDoc'

    def _compute(self, express, values):
        res = 0.0
        return res
    
    def get_reference(self):
        dictions_obj = self.pool.get('ir.dictions')
        res = []
        diction_ids = dictions_obj.search([
                    ('model', '=', 'ekd.account.move.line'),
                    ('pole', '=', 'analytic_ref'),
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
                if name =='dt_kind':
                    if line.dt_account:
                        res[name][line.id] = line.dt_account.kind
                elif name =='dt_kind_analytic':
                    if line.dt_account:
                        res[name][line.id] = line.dt_account.kind_analytic
                elif name =='ct_kind':
                    if line.ct_account:
                        res[name][line.id] = line.ct_account.kind
                elif name =='ct_kind_analytic':
                    if line.ct_account:
                        res[name][line.id] = line.ct_account.kind_analytic
        return res

    def button_test(self, ids):
        move_obj = self.pool.get('ekd.account.move.template')
        for line in self.browse(ids):
            if line.amount in ['@', '-@']:
                self.raise_user_warning('%s@account_ru_move_line_template'%(line.id), 'test_formula_yes')
            elif move_obj.formula_test(line.id, line.amount.encode('utf8')):
                self.raise_user_warning('%s@account_ru_move_line_template'%(line.id), 'test_formula_yes')

TemplateLineRU()

'''
Вероятные случаи аналитических счетов
Контрагенты
Сотрудники
Налоги
Склады - Места хранения
Виды деятельности
Дополнительные Аналитические счета

'''

class MoveTemplateLineAnalytic(ModelSQL, ModelView):
    'Move Template Analytic Account'
    _name = "ekd.account.move.line.template.analytic"
    _description=__doc__

    move_line = fields.Many2One('ekd.account.move.line.template', 'Line template Entries', ondelete="CASCADE")
    level = fields.Char('Level analytic', size=2)
    analytic = fields.Selection([
                ('dt_party','Party Debit Account'),
                ('ct_party','Party Credit Account'),
                ('dt_analytic','Debit Analytic Account'),
                ('ct_analytic','Credit Analytic Account'),
                ('dt_employee','Employee Debit Account'),
                ('ct_employee','Employee Credit Account'),
                ('dt_tax','Tax Debit Account'),
                ('ct_tax','Tax Credit Account'),
                ], 'Analytic Model')
    analytic_txt = fields.Char('Analytic Model', size=None)
MoveTemplateLineAnalytic()
