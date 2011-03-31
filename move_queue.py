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
'Move Queue'
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Greater, Equal, Eval, Get, And, Or, Not, In, Bool, PYSONEncoder
from account import _PARTY, _PRODUCT, _DEPRECATION, _OTHER, _MONEY
from decimal import Decimal
import datetime

class LineQueue(ModelSQL, ModelView):
    "Queue Lines"
    _name="ekd.account.move.line.queue"
    _description=__doc__

    line = fields.Many2One('ekd.account.move.line', 'Entries', ondelete="CASCADE")
    state_line = fields.Selection([
                ('draft','Draft'),
                ('posted','Posted'),
                ('canceled','Canceled'),
                ('deleted','Deleted')
                ], 'Line State', required=True, readonly=True)

    state_queue = fields.Selection([
                ('posted','Posted'),
                ('error','Error'),
                ('deleted','Deleted')
                ], 'Queue State', required=True, readonly=True)

    post_date = fields.Date('Post Time')
    message = fields.Text('Note')

    def __init__(self):
        super(LineQueue, self).__init__()

    def verify_queue():
        return True

    def work_queue():
        pass

LineQueue()
