#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""Copyright (C) 2009 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kmj is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

# See the user manual for a description of how to define rulesets.
# Names must only contain ascii chars. Because kdecore.i18n()
# only accepts 8bit characters, no unicode.

from inspect import isclass
from scoring import Ruleset, Rule
from util import m18n


class ClassicalChinesePattern(Ruleset):
    """classical chinese rules expressed by patterns, not complete"""

    def __init__(self):
        Ruleset.__init__(self, 'Classical Chinese with Patterns')

    def _load(self, dbhandle):
        """define the rules"""
        self.intRules.append(Rule('minMJPoints', 0))
        self.intRules.append(Rule('limit', 500))
        self.mjRules.append(Rule('mah jongg', 'PMahJongg()', points=20))
        self.mjRules.append(Rule('last tile completes simple pair', 'PLastTileCompletes(Simple(Pair))', points=2))
        self.mjRules.append(Rule('last tile completes pair of terminals or honours',
            'PLastTileCompletes(NoSimple(Pair))', points=4))
        self.mjRules.append(Rule('last tile is only possible tile', 'PLastTileOnlyPossible()',  points=4))
        self.mjRules.append(Rule('won with last tile taken from wall', 'PLastTileCompletes(Concealed)', points=2))

        self.handRules.append(Rule('own flower and own season',
                r'I.* f(.).* y\1 .*m\1', doubles=1))
        self.handRules.append(Rule('all flowers', r'I.*(\bf[eswn]\s){4,4}',
                                                doubles=1))
        self.handRules.append(Rule('all seasons', r'I.*(\by[eswn]\s){4,4}',
                                                doubles=1))
        self.handRules.append(Rule('three concealed pongs',  'PConcealed(PungKong)*3  +  Rest', doubles=1))
        self.handRules.append(Rule('little three dragons', 'PDragons(PungKong)*2 +  Dragons(Pair) +   Rest', doubles=1))
        self.handRules.append(Rule('big three dragons', 'PDragons(PungKong)*3  +  Rest', doubles=2))
        self.handRules.append(Rule('little four joys', 'PWinds(PungKong)*3 + Winds(Pair) +   Rest', doubles=1))
        self.handRules.append(Rule('big four joys', 'PWinds(PungKong)*4  +  Rest', doubles=2))

        self.mjRules.append(Rule('zero point hand', r'I.*/([dwsbc].00)*M', doubles=1))
        self.mjRules.append(Rule('no chow', 'PNoChow(MahJongg)', doubles=1))
        self.mjRules.append(Rule('only concealed melds', 'PConcealed(MahJongg)', doubles=1))
        self.mjRules.append(Rule('false color game',
                                        'PHonours() + Character + NoBamboo(NoStone)*3 ||'
                                        'PHonours() + Stone + NoBamboo(NoCharacter)*3 ||'
                                        'PHonours() + Bamboo + NoStone(NoCharacter)*3', doubles=1 ))
        self.mjRules.append(Rule('true color game', 'POneColor(NoHonours(MahJongg))', doubles=3))
        self.mjRules.append(Rule('only terminals and honours', 'PNoSimple(MahJongg)', doubles=1))
        self.mjRules.append(Rule('only honours',  'PHonours(MahJongg)', doubles=2))
        self.manualRules.append(Rule('last tile taken from dead wall', 'PMahJongg()',  doubles=1))
        self.manualRules.append(Rule('last tile is last tile of wall', 'PMahJongg()', doubles=1))
        self.manualRules.append(Rule('last tile is last tile of wall discarded', 'PMahJongg()', doubles=1))
        self.manualRules.append(Rule('robbing the kong', 'PMahJongg()', doubles=1))
        self.manualRules.append(Rule('mah jongg with call at beginning', 'PMahJongg()', doubles=1))

        # limit hands:
        self.manualRules.append(Rule('blessing of heaven', r'.*Me', limits=1))
        self.manualRules.append(Rule('blessing of earth', r'.*M[swn]', limits=1))
        self.mjRules.append(Rule('concealed true color game',
                'PConcealed(ClaimedKongAsConcealed(OneColor(NoHonours(MahJongg))))', limits=1))
        self.manualRules.append(Rule('hidden treasure',
                'PConcealed(ClaimedKongAsConcealed(PungKong())*4+Pair())', limits=1))
        self.mjRules.append(Rule('all honours', 'PHonours(MahJongg)', limits=1))
        self.mjRules.append(Rule('all terminals', 'PTerminals(MahJongg)', limits=1))
        self.mjRules.append(Rule('winding snake',
                'POneColor(PungKong(1)+Chow(2)+Chow(5)+PungKong(9)+Pair(8)) ||'
                'POneColor(PungKong(1)+Chow(3)+Chow(6)+PungKong(9)+Pair(2)) ||'
                'POneColor(PungKong(1)+Chow(2)+Chow(6)+PungKong(9)+Pair(5))', limits=1))
        self.mjRules.append(Rule('four kans', 'PKong()*4 + Rest', limits=1))
        self.mjRules.append(Rule('three great scholars', 'PDragons(PungKong)*3 + Rest', limits=1))
        self.mjRules.append(Rule('four blessings hovering over the door', 'PWinds(PungKong)*4 + Rest', limits=1))
        self.mjRules.append(Rule('All greens', 'PAllGreen(MahJongg)', limits=1))
        self.mjRules.append(Rule('nine gates',
                'POneColor(Concealed(Pung(1)+Chow(2)+Chow(5)+Single(8)+Pung(9))+Exposed(Single))', limits=1))
        self.mjRules.append(Rule('thirteen orphans', "PBamboo(Single(1)+Single(9))+Character(Single(1)+Single(9))"
            "+Stone(Single(1)+Single(9))+Single('b')+Single('g')+Single('r')"
            "+Single('e')+Single('s')+Single('w')+Single('n')+Single(NoSimple)", limits=1))

        self.handRules.append(Rule('flower 1', r'I.*\bfe ', points=4))
        self.handRules.append(Rule('flower 2', r'I.*\bfs ', points=4))
        self.handRules.append(Rule('flower 3', r'I.*\bfw ', points=4))
        self.handRules.append(Rule('flower 4', r'I.*\bfn ', points=4))
        self.handRules.append(Rule('season 1', r'I.*\bye ', points=4))
        self.handRules.append(Rule('season 2', r'I.*\bys ', points=4))
        self.handRules.append(Rule('season 3', r'I.*\byw ', points=4))
        self.handRules.append(Rule('season 4', r'I.*\byn ', points=4))

        # doubling melds:
        self.meldRules.append(Rule('pung/kong of dragons', 'PDragons(PungKong)', doubles=1))
        self.meldRules.append(Rule('pung/kong of own wind', 'POwnWind(PungKong)', doubles=1))
        self.meldRules.append(Rule('pung/kong of round wind', 'PRoundWind(PungKong)', doubles=1))

        # exposed melds:
        self.meldRules.append(Rule('exposed kong', 'PSimple(Exposed(Kong))', points=8))
        self.meldRules.append(Rule('exposed kong of terminals', 'PTerminals(Exposed(Kong))', points=16))
        self.meldRules.append(Rule('exposed kong of honours', 'PHonours(Exposed(Kong))', points=16))

        self.meldRules.append(Rule('exposed pung', 'PSimple(Exposed(Pung))', points=2))
        self.meldRules.append(Rule('exposed pung of terminals', 'PTerminals(Exposed(Pung))', points=4))
        self.meldRules.append(Rule('exposed pung of honours', 'PHonours(Exposed(Pung))', points=4))

        # concealed melds:
        self.meldRules.append(Rule('concealed kong', 'PSimple(Concealed(Kong))', points=16))
        self.meldRules.append(Rule('concealed kong of terminals', 'PTerminals(Concealed(Kong))', points=32))
        self.meldRules.append(Rule('concealed kong of honours', 'PHonours(Concealed(Kong))', points=32))

        self.meldRules.append(Rule('concealed pung', 'PSimple(Concealed(Pung))', points=4))
        self.meldRules.append(Rule('concealed pung of terminals', 'PTerminals(Concealed(Pung))', points=8))
        self.meldRules.append(Rule('concealed pung of honours', 'PHonours(Concealed(Pung))', points=8))

        self.meldRules.append(Rule('pair of own wind', 'POwnWind(Pair)', points=2))
        self.meldRules.append(Rule('pair of round wind', 'PRoundWind(Pair)', points=2))
        self.meldRules.append(Rule('pair of dragons', 'PDragons(Pair)', points=2))

class ClassicalChineseRegex(Ruleset):
    """classical chinese rules expressed by regular expressions, not complete"""

    def __init__(self):
        Ruleset.__init__(self, 'Classical Chinese with Regular Expressions')

    def _load(self, dbhandle):
        """define the rules"""
        self.intRules.append(Rule('minMJPoints', 0))
        self.intRules.append(Rule('limit', 500))
        self.mjRules.append(Rule('mah jongg',   r'.*M', points=20))
        self.mjRules.append(Rule('last tile completes pair of 2..8', r'.*\bL(.[2-8])\1\1\b', points=2))
        self.mjRules.append(Rule('last tile completes pair of terminals or honours',
                r'.*\bL((.[19])|([dwDW].))\1\1\b', points=4))
        self.mjRules.append(Rule('last tile is only possible tile', 'PLastTileOnlyPossible()',  points=4))
        self.mjRules.append(Rule('won with last tile taken from wall', r'.*M.*\bL[A-Z]', points=2))

        self.handRules.append(Rule('own flower and own season',
                r'I.* f(.).* y\1 .*m\1', doubles=1))
        self.handRules.append(Rule('all flowers', r'I.*(\bf[eswn]\s){4,4}',
                                                doubles=1))
        self.handRules.append(Rule('all seasons', r'I.*(\by[eswn]\s){4,4}',
                                                doubles=1))
        self.handRules.append(Rule('three concealed pongs', r'.*/.*(([DWSBC][34]..).*?){3,}', doubles=1))
        self.handRules.append(Rule('little three dragons', r'I.*/d2..d[34]..d[34]..',
                                                doubles=1))
        self.handRules.append(Rule('big three dragons', r'I.*/d[34]..d[34]..d[34]..',
                                                doubles=2))
        self.handRules.append(Rule('little four joys', r'I.*/.*w2..(w[34]..){3,3}',
                                                 doubles=1))
        self.handRules.append(Rule('big four joys', r'I.*/.*(w[34]..){4,4}',
                                                doubles=2))

        self.mjRules.append(Rule('zero point hand', r'I.*/([dwsbc].00)*M',
                                                doubles=1))
        self.mjRules.append(Rule('no chow', r'I.*/([dwsbc][^0]..)*M',
                                                doubles=1))
        self.mjRules.append(Rule('only concealed melds', r'.*/([DWSBC]...)*M', doubles=1))
        self.mjRules.append(Rule('false color game', r'I.*/([dw]...){1,}(([sbc])...)(\3...)*M',
                                                doubles=1))
        self.mjRules.append(Rule('true color game',   r'I.*/(([sbc])...)(\2...)*M',
                                                doubles=3))
        self.mjRules.append(Rule('only 1/9 and honours', r'I((([dw].)|(.[19])){1,4} )*[fy/].*M',
                                                doubles=1 ))
        self.mjRules.append(Rule('only honours', r'I.*/([dw]...)*M',
                                                doubles=2 ))
        self.manualRules.append(Rule('last tile taken from dead wall', r'.*M', doubles=1))
        self.manualRules.append(Rule('last tile is last tile of wall', r'.*M', doubles=1))
        self.manualRules.append(Rule('last tile is last tile of wall discarded', r'.*M', doubles=1))
        self.manualRules.append(Rule('robbing the kong', r'.*M', doubles=1))
        self.manualRules.append(Rule('mah jongg with call at beginning', r'.*M', doubles=1))

        # limit hands:
        self.manualRules.append(Rule('blessing of heaven', r'.*Me', limits=1))
        self.manualRules.append(Rule('blessing of earth', r'.*M[swn]', limits=1))
        # concealed true color game ist falsch, da es nicht auf korrekte Aufteilung in Gruppen achtet
        self.mjRules.append(Rule('concealed true color game',   r'(([sbc][1-9])*([SBC].){1,3} )*[fy/]', limits=1))
        self.manualRules.append(Rule('hidden treasure', 'PMJHiddenTreasure()', limits=1))
        self.mjRules.append(Rule('all honours', r'.*/([DWdw]...)*M', limits=1))
        self.mjRules.append(Rule('all terminals', r'((.[19]){1,4} )*[fy/]', limits=1))
        self.mjRules.append(Rule('winding snake',
                                           'POneColor(PungKong(1)+Chow(2)+Chow(5)+PungKong(9)+Pair(8)) ||'
                                           'POneColor(PungKong(1)+Chow(3)+Chow(6)+PungKong(9)+Pair(2)) ||'
                                           'POneColor(PungKong(1)+Chow(2)+Chow(6)+PungKong(9)+Pair(5))', limits=1))
        self.mjRules.append(Rule('four kans', r'.*/((....)*(.4..)(....)?){4,4}', limits=1))
        self.mjRules.append(Rule('three great scholars', r'.*/[Dd][34]..[Dd][34]..[Dd][34]', limits=1))
        self.mjRules.append(Rule('four blessings hovering over the door', r'.*/.*([Ww][34]..){4,4}', limits=1))
        self.mjRules.append(Rule('All greens', r'( |[bB][23468]|[dD]g)*[fy/]', limits=1))
        self.mjRules.append(Rule('nine gates', r'(S1S1S1 S2S3S4 S5S6S7 S8 S9S9S9 s.|'
                'B1B1B1 B2B3B4 B5B6B7 B8 B9B9B9 b.|C1C1C1 C2C3C4 C5C6C7 C8 C9C9C9 c.)', limits=1))
        self.mjRules.append(Rule('thirteen orphans', \
            r'I(db ){1,2}(dg ){1,2}(dr ){1,2}(we ){1,2}(wn ){1,2}(ws ){1,2}(ww ){1,2}'
            '(s1 ){1,2}(s9 ){1,2}(b1 ){1,2}(b9 ){1,2}(c1 ){1,2}(c9 ){1,2}[fy/].*M', limits=1))


        self.handRules.append(Rule('flower 1', r'I.*\bfe ', points=4))
        self.handRules.append(Rule('flower 2', r'I.*\bfs ', points=4))
        self.handRules.append(Rule('flower 3', r'I.*\bfw ', points=4))
        self.handRules.append(Rule('flower 4', r'I.*\bfn ', points=4))
        self.handRules.append(Rule('season 1', r'I.*\bye ', points=4))
        self.handRules.append(Rule('season 2', r'I.*\bys ', points=4))
        self.handRules.append(Rule('season 3', r'I.*\byw ', points=4))
        self.handRules.append(Rule('season 4', r'I.*\byn ', points=4))

        # doubling melds:
        self.meldRules.append(Rule('pung/kong of dragons', r'([dD][brg])\1\1', doubles=1))
        self.meldRules.append(Rule('pung/kong of own wind', r'(([wW])([eswn])){3,4}.*[mM]\3', doubles=1))
        self.meldRules.append(Rule('pung/kong of round wind', r'(([wW])([eswn])){3,4}.*[mM].\3', doubles=1))

        # exposed melds:
        self.meldRules.append(Rule('exposed kong', r'([sbc])([2-8])(\1\2\1\2.\2)[mM]', points=8))
        self.meldRules.append(Rule('exposed kong 1/9', r'([sbc])([19])(\1\2\1\2.\2)[mM]', points=16))
        self.meldRules.append(Rule('exposed kong of honours', r'([dw])([brgeswn])(\1\2\1\2.\2)[mM]', points=16))

        self.meldRules.append(Rule('exposed pung', r'([sbc][2-8])(\1\1)[mM]', points=2))
        self.meldRules.append(Rule('exposed pung 1/9', r'([sbc][19])(\1\1)[mM]', points=4))
        self.meldRules.append(Rule('exposed pung of honours', r'(d[brg]|w[eswn])(\1\1)[mM]', points=4))

        # concealed melds:
        self.meldRules.append(Rule('concealed kong', r'([sbc][2-8])([SBC][2-8])(\2)(\1)[mM]', points=16))
        self.meldRules.append(Rule('concealed kong 1/9', r'([sbc][19])([SBC][19])(\2)(\1)[mM]', points=32))
        self.meldRules.append(Rule('concealed kong of honours', r'(d[brg]|w[eswn])(D[brg]|W[eswn])(\2)(\1)[mM]',
                                                    points=32))

        self.meldRules.append(Rule('concealed pung', r'([SBC][2-8])(\1\1)[mM]', points=4))
        self.meldRules.append(Rule('concealed pung 1/9', r'([SBC][19])(\1\1)[mM]', points=8))
        self.meldRules.append(Rule('concealed pung of honours', r'(D[brg]|W[eswn])(\1\1)[mM]', points=8))

        self.meldRules.append(Rule('pair of own wind', r'([wW])([eswn])(\1\2)[mM]\2', points=2))
        self.meldRules.append(Rule('pair of round wind', r'([wW])([eswn])(\1\2)[mM].\2', points=2))
        self.meldRules.append(Rule('pair of dragons', r'([dD][brg])(\1)[mM]', points=2))

def defaultRulesets():
    """returns all rulesets defined in this module"""
    thisModule = __import__(__name__)
    result = []
    for attrName in globals():
        obj = getattr(thisModule, attrName)
        if isclass(obj) and Ruleset in obj.__mro__:
            cName = obj.__name__
            if cName not in ('Ruleset'):
                result.append(obj)
    return result

