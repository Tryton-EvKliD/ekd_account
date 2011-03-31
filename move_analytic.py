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
'Move Analytic'
from trytond.model import ModelView, ModelSQL, fields

class MoveAnalytic(ModelSQL, ModelView):
    'Move Analytic Account'
    _name = "ekd.account.move.line.analytic"
    _description=__doc__

    move_line = fields.Many2One('ekd.account.move.line', 'Entries', ondelete="CASCADE")
    move_line_west = fields.Many2One('ekd.account.move.line.west', 'Entries', ondelete="CASCADE")
    level = fields.Char('Level analytic', size=2)
    analytic = fields.Char('Analytic Model', size=None)
    # Ref to ekd.balances.analytic.*.amount
    ref_analytic = fields.Integer('Ref Analytic Account')
    ref_period = fields.Integer('Ref Turnover Analytic Amount')

    def __init__(self):
        super(MoveAnalytic, self).__init__()
        self._order.insert(0, ('level', 'ASC'))
        self._sql_constraints += [
                ('move_line_level_uniq', 'UNIQUE(move_line,level)',\
                 'move_line,level - must be unique per entries line!'),
                 ]

MoveAnalytic()

class MoveAnalyticDebit(ModelSQL, ModelView):
    'Move Analytic Account on Debit'
    _name = "ekd.account.move.line.analytic_dt"
    _description=__doc__

    move_line = fields.Many2One('ekd.account.move.line', 'Entries', ondelete="CASCADE")
    move_line_west = fields.Many2One('ekd.account.move.line.west', 'Entries', ondelete="CASCADE")
    level = fields.Char('Level analytic', size=2)
    analytic = fields.Char('Analytic Model', size=None)
    # Ref to ekd.balances.analytic.*.amount
    ref_analytic = fields.Integer('Ref Analytic Account')
    ref_period = fields.Integer('Ref Turnover Analytic Amount')

    def __init__(self):
        super(MoveAnalyticDebit, self).__init__()
        self._order.insert(0, ('level', 'ASC'))
        self._sql_constraints += [
                ('move_line_level_uniq', 'UNIQUE(move_line,level)',\
                 'move_line,level - must be unique per entries line!'),
                 ]

MoveAnalyticDebit()

class MoveAnalyticCredit(ModelSQL, ModelView):
    'Move Analytic Account on Credit'
    _name = "ekd.account.move.line.analytic_ct"
    _description=__doc__

    move_line = fields.Many2One('ekd.account.move.line', 'Entries', ondelete="CASCADE")
    move_line_west = fields.Many2One('ekd.account.move.line.west', 'Entries', ondelete="CASCADE")
    level = fields.Char('Level analytic', size=2)
    analytic = fields.Char('Analytic Model', size=None)
    # Ref to ekd.balances.analytic.*.period
    ref_analytic = fields.Integer('Ref Analytic Account')
    ref_period = fields.Integer('Ref Turnover Analytic Amount')

    def __init__(self):
        super(MoveAnalyticCredit, self).__init__()
        self._order.insert(0, ('level', 'ASC'))
        self._sql_constraints += [
                ('move_line_level_uniq', 'UNIQUE(move_line,level)',\
                 'move_line,level - must be unique per entries line!'),
                 ]

MoveAnalyticCredit()
