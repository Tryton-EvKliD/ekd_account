# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты 
# 3. Тип счетов
# 3. Остатки по счетам
##############################################################################
"Reports Accounting"
from __future__ import with_statement
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.tools import safe_eval
import time
from decimal import Decimal, ROUND_HALF_EVEN
import datetime
import logging


class ChartAccountReport(Report):
    _name = "ekd.account.chart.report"

    def _get_objects(self, ids, model, datas):
        account_obj = self.pool.get('ekd.account')
        with Transaction().set_context(language='ru_RU'):
            return account_obj.browse(ids)

    def parse(self, report, objects=[], datas={}, localcontext={}):
        context = Transaction().context
        user = self.pool.get('res.user').browse(Transaction().user)
        localcontext['company'] = self.pool.get('company.company').browse(context.get('company', False))
        localcontext['current_date'] = context.get('current_date', False)
        with Transaction().set_context(language='ru_RU'):
            res = super(ChartAccountReport, self).parse(report, objects, datas, localcontext)
        return res

ChartAccountReport()

