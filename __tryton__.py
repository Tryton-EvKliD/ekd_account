# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Accounting',
    'name_de_DE': 'Buchhaltung',
    'name_es_CO': 'Contabilidad',
    'name_es_ES': 'Contabilidad',
    'name_fr_FR': 'Comptabilité',
    'name_ru_RU': 'Финансовый учет',
    'version': '1.8.0',
    'author': 'Dmitry Klimanov',
    'email': 'k-dmitry2@narod.ru',
    'website': 'http://www.delfi2000.ru/',
    'description': '''Financial and Accounting Module with:
    - General accounting
    - Fiscal year management
    - Journal entries

And with reports:
    - Balance sheet
    - Income statement
    - General journal
''',
    'description_ru_RU': '''модуль Бухгалтерского учета по Российскому стандарту:
    форма учета Журнал-Главная, Журнально ордерная
    Внимание после установки Вам надо выбрать как будут работать триггеры
    разноски остатков!!!
        1. Реализован динамический расчет остатков за периоды или за интервал времени
        2. На сервере Tryton - (модуль ekd_account_triggers)
        3. В базе данных PostgerSQL - (каталог triggers) - пока не перенес :-(
    Формы в модули
    - Операционный журнал (Заголовки проводок)
    - Операционный журнал (Строки проводок)
    - Операционный журнал - корзина (Заголовки проводок)
    - Операционный журнал - корзина (Строки проводок)
    - Оборотные ведомости по счетам
    - Оборотные ведомости по аналитическим счетам
    - Оборотные ведомости по финансовым счетам (касса, банк)
    - Журналы ордера (Разработка)

    Формы документов для печати:

    Формы отчетов для печати:
    - Операционный журнал  - ( неподключен )
    - Оборотные ведомости по счетам - ( неподключен )
    - Оборотные ведомости по аналитическим счетам - ( неподключен )
    - Оборотные ведомости по счетам ТМЦ - ( неподключен )
    - Оборотные ведомости по счетам контрагентов (Поставщики, Заказчики, Подотчетные лица) - ( неподключен )
    - Баланс - ( неподключен )
    - Главная книга - ( неподключен )

''',
    'depends': [
        'ir',
        'res',
        'calendar',
        'currency',
        'ekd_system',
        'ekd_party',
        'ekd_company',
        'ekd_product',
        'ekd_documents',
    ],
    'xml': [
        'xml/ekd_system.xml',
        'xml/ekd_account.xml',
        'xml/ekd_fiscalyear.xml',
        'xml/ekd_period.xml',
        'xml/ekd_analytic.xml',
        'xml/ekd_move.xml',
        'xml/ekd_move_template.xml',
        'xml/ekd_move_line.xml',
        'xml/ekd_journal.xml',
        'xml/ekd_balance.xml',
        'xml/ekd_bal_finance.xml',
        'xml/ekd_bal_party_tree.xml',
        'xml/ekd_bal_analytic_ext.xml',
        'xml/ekd_bal_goods.xml',
        'xml/ekd_bal_goods_balance.xml',
        'xml/ekd_doc_template_view.xml',
        'xml/ekd_doc_cash_view.xml',
        'xml/ekd_doc_request_view.xml',
        'xml/ekd_doc_payment_view.xml',
        'xml/ekd_wiz_move.xml',
        'xml/ekd_book_cash.xml',
        'xml/ekd_account_report.xml',
        'xml/ekd_balance_report.xml',
        'xml/ekd_company.xml',
        'xml/ekd_party.xml',
        'xml/product.xml',
        'xml/ekd_tax.xml',
    ],
    'translation': [
        'ru_RU.csv',
    ],
}
