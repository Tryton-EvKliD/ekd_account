# -*- coding: utf-8 -*-
"Timesheet"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.tools import safe_eval
from decimal import Decimal, ROUND_HALF_EVEN
from trytond.pyson import In, Eval, Not, In, Equal, If, Get, Bool
import time
import datetime
import random
import copy

# Шаблон табеля учета времени
class TimeSheetTemplate(ModelSQL, ModelView):
    "Card Template"
    _name='ekd.timesheet.template'

    period = fields.Many2One('ekd.period', 'Period')

TimeSheetTemplate()

#График работы
class TimesheetSchedule(ModelSQL, ModelView):
    "TimeSheet Schedule"
    _name='ekd.timesheet.schedule'

    period = fields.Many2One('ekd.period', 'Period', domain=[('company','=', Eval('company'))])

TimesheetSchedule()

