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
from trytond.pyson import Eval
from move import _CT_PRODUCT_STATES, _MOVE_STATES, _MOVE_DEPENDS

class MoveRU(ModelSQL, ModelView):
    'Business operations russian standart'
    _name = "ekd.account.move"
    _description=__doc__

    template_move = fields.Many2One('ekd.account.move.template', 'Template move')

MoveRU()

class LineRU(ModelSQL, ModelView):
    "Lines of business operations russian standart"
    _name="ekd.account.move.line"
    _description=__doc__

    template_line = fields.Many2One('ekd.account.move.line.template', 'Template Move line', ondelete="RESTRICT")
    journal = fields.Many2One('ekd.account.journal', 'Journal',
            states=_MOVE_STATES, depends=_MOVE_DEPENDS)

    product_balance_assets = fields.Many2One('ekd.balances.assets', 'Assets',
                domain=[('account','=',Eval('ct_account'))],
                states=_CT_PRODUCT_STATES)
#    product_balance_intangible = fields.Many2One('ekd.balances.intangible', 'Balance Intangible Assets',
#                states=_CT_PRODUCT_STATES)
#    product_balance_material = fields.Many2One('ekd.balances.material', 'Balance Material',
#                states=_CT_PRODUCT_STATES)
    product_balance_goods = fields.Many2One('ekd.balances.goods.balance', 'Balance Goods',
                domain=[('period_product.goods.account','=',Eval('ct_account'))],
                states=_CT_PRODUCT_STATES)
LineRU()
