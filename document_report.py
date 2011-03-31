# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
##############################################################################
# В данном файле описываются объекты 
# 3. Тип счетов
# 3. Остатки по счетам
##############################################################################
"Print form documents"
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard
from trytond.report import Report
from trytond.tools import safe_eval
import time
from decimal import Decimal, ROUND_HALF_EVEN
import datetime
import logging

