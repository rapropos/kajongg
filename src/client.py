#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
Copyright (C) 2009,2010 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
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

from twisted.spread import pb
from twisted.internet.defer import Deferred, DeferredList, succeed
from util import logWarning, logException, logMessage, debugMessage
from common import InternalParameters, WINDS
import syslog
from scoringengine import Ruleset, PredefinedRuleset, meldsContent, Meld
from game import RemoteGame
from query import Query
from move import Move

class ClientTable(object):
    """the table as seen by the client"""
    def __init__(self, tableid, running, rulesetStr, playerNames):
        self.tableid = tableid
        self.running = running
        self.ruleset = Ruleset.fromList(rulesetStr)
        self.playerNames = list(playerNames)
        self.myRuleset = None # if set, points to an identical local rulest
        allRulesets = Ruleset.availableRulesets() + PredefinedRuleset.rulesets()
        for myRuleset in allRulesets:
            if myRuleset.hash == self.ruleset.hash:
                self.myRuleset = myRuleset
                break

    def __str__(self):
        return 'Table %d rules %s players %s' % (self.tableid, self.ruleset.name,
            ', '.join(self.playerNames))

class Client(pb.Referenceable):
    """interface to the server. This class only implements the logic,
    so we can also use it on the server for robot clients. Compare
    with HumanClient(Client)"""

    def __init__(self, username=None):
        """username is something like ROBOT 1 or None for the game server"""
        self.username = username
        self.game = None
        self.moves = []
        self.perspective = None # always None for a robot client
        self.tableList = None
        self.tables = []
        self.table = None
        self.discardBoard = None
        self.answers = [] # buffer for one or more answers to one server request
            # an answer can be a simple type or a Deferred

    @apply
    def host():
        """the name of the host we are connected with"""
        def fget(self):
            assert self # quieten pylint
            return Query.serverName
        return property(**locals())

    def isRobotClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(self.username)

    def isHumanClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return False

    def isServerClient(self):
        """avoid using isinstance because that imports too much for the server"""
        return bool(not self.username)

    def remote_tablesChanged(self, tableid, tables):
        """update table list"""
        self.tables = [ClientTable(*x) for x in tables]

    def readyForGameStart(self, tableid, seed, playerNames, field=None, shouldSave=True):
        """the game server asks us if we are ready. A robot is always ready..."""
        if self.isHumanClient():
            assert not self.table
            for tryTable in self.tables:
                if tryTable.tableid == tableid:
                    self.table = tryTable
            if not self.table:
                raise Exception('client.readyForGameStart: tableid %d unknown' % tableid)
        self.game = RemoteGame(playerNames.split('//'), self.table.ruleset,
            field=field, shouldSave=shouldSave, seed=seed, client=self)
        self.game.prepareHand()
        self.answers.append(True)
        return True

    def readyForHandStart(self, playerNames, rotate):
        """the game server asks us if we are ready. A robot is always ready..."""
        for idx, playerName in enumerate(playerNames.split('//')):
            self.game.players.byName(playerName).wind = WINDS[idx]
        if rotate:
            self.game.rotateWinds()
        self.game.prepareHand()

    def invalidateOriginalCall(self, player):
        """called if a move violates the Original Call"""
        if player.originalCall:
           if player.mayWin and self.thatWasMe(player):
                if player.discarded:
                    player.mayWin = False
                    self.answers.append(('Violates Original Call'))

    def __answer(self, answer, meld, withDiscard=None, lastMeld=None):
        """return an answer to the game server"""
        if lastMeld is None:
            lastMeld = []
        self.answers.append((answer, meld, withDiscard, lastMeld))

    def ask(self, move, answers):
        """this is where the robot AI should go"""
        game = self.game
        myself = game.myself
        if 'Mah Jongg' in answers:
            answerArgs = self.maySayMahjongg()
            if answerArgs:
                self.__answer('Mah Jongg', *answerArgs)
                return
        if 'Kong' in answers:
            answerArgs =self.maySayKong()
            if answerArgs:
                self.__answer('Kong', answerArgs)
                return
        if 'Pung' in answers:
            answerArgs = self.maySayPung()
            if answerArgs:
                self.__answer('Pung', answerArgs)
                return
        if 'Chow' in answers:
            answerArgs = self.maySayChow()
            if answerArgs:
                self.__answer('Chow', answerArgs)

        answer = answers[0] # for now always return default answer
        if answer == 'Discard':
            # do not remove tile from hand here, the server will tell all players
            # including us that it has been discarded. Only then we will remove it.
            hand = move.player.computeHandContent()
            # TODO: also check what has been discarded an exposed
            for meldLen in range(1, 3):
                # hand.hiddenMelds are built from a set, order undefined. But
                # we want to be able to replay a game exactly, so sort them
                melds = sorted(list(x for x in hand.hiddenMelds if len(x) == meldLen),
                    key=lambda x: x.joined)
                if melds:
                    meld = melds[-1]
                    tileName = sorted(meld.pairs)[-1]
                    self.answers.append(('Discard', tileName))
                    return
            raise Exception('Player %s has nothing to discard:concTiles=%s concMelds=%s hand=%s' % (
                            move.player.name, move.player.concealedTiles, move.player.concealedMelds, hand))
        else:
            # the other responses do not have a parameter
            self.answers.append((answer))

    def thatWasMe(self, player):
        """returns True if player == myself"""
        if not self.game:
            return False
        return player == self.game.myself

    def remote_move(self, playerName, command, *args, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        self.answers = []
        self.exec_move(playerName, command, *args, **kwargs)
        for idx, answer in enumerate(self.answers):
            if not isinstance(answer, Deferred):
                self.answers[idx] = succeed(answer)
        return DeferredList(self.answers)

    def exec_move(self, playerName, command, *args, **kwargs):
        player = None
        if self.game:
            self.game.checkSelectorTiles()
            if not self.game.client:
                # we aborted the game, ignore what the server tells us
                return
            myself = self.game.myself
            for myPlayer in self.game.players:
                if myPlayer.name == playerName:
                    player = myPlayer
            if not player:
                logException('Move references unknown player %s' % playerName)
        if InternalParameters.showTraffic:
            if self.isHumanClient():
                debugMessage('%s %s %s' % (player, command, kwargs))
        move = Move(player, command, kwargs)
        self.moves.append(move)
        if command == 'readyForGameStart':
            # move.source are the players in seating order
            # we cannot just use table.playerNames - the seating order is now different (random)
            self.readyForGameStart(move.tableid, move.seed, move.source, shouldSave=move.shouldSave)
        elif command == 'readyForHandStart':
            self.readyForHandStart(move.source, move.rotate)
        elif command == 'initHand':
            self.game.divideAt = move.divideAt
            self.game.showField()
        elif command == 'setTiles':
            self.game.setTiles(player, move.source)
        elif command == 'showTiles':
            self.game.showTiles(player, move.source)
        elif command == 'declaredMahJongg':
            player.declaredMahJongg(move.source, move.withDiscard,
                move.lastTile, Meld(move.lastMeld))
            if player.balance != move.winnerBalance:
                logException('WinnerBalance is different for %s! player:%d, remote:%d,hand:%s' % \
                    (player, player.balance, move.winnerBalance, player.computeHandContent()))
        elif command == 'saveHand':
            self.game.saveHand()
        elif command == 'popupMsg':
            player.popupMsg(move.msg)
        elif command == 'activePlayer':
            self.game.activePlayer = player
        elif command == 'pickedTile':
            self.game.wall.dealTo(deadEnd=move.deadEnd)
            self.game.pickedTile(player, move.source, move.deadEnd)
            if self.thatWasMe(player):
                if move.source[0] in 'fy':
                    self.answers.append(('Bonus', move.source))
                else:
                    if self.game.lastDiscard:
                        answers = ['Discard', 'Mah Jongg']
                    else:
                        answers = ['Discard', 'Kong', 'Mah Jongg']
                    if not player.discarded and not player.originalCall:
                        answers.append('Original Call')
                    self.ask(move, answers)
        elif command == 'pickedBonus':
            assert not self.thatWasMe(player)
            player.makeTilesKnown(move.source)
        elif command == 'madeOriginalCall':
            player.originalCall = True
            if self.thatWasMe(player):
                answers = ['Discard', 'Mah Jongg']
                self.ask(move, answers)
        elif command == 'violatedOriginalCall':
            player.mayWin = False
            if self.thatWasMe(player):
                self.ask(move, ['OK'])
        elif command == 'declaredKong':
            self.invalidateOriginalCall(player)
            if not self.thatWasMe(player):
                player.makeTilesKnown(move.source)
            player.exposeMeld(move.source, claimed=False)
            if self.game.prevActivePlayer == myself and self.perspective:
                # even here we ask otherwise if all other players are robots we would
                # have no time to see it if a robot calls MJ on my discarded tile
                self.ask(move, ['OK'])
        elif command == 'hasDiscarded':
            if move.tile != player.lastTile:
                self.invalidateOriginalCall(player)
            self.game.hasDiscarded(player, move.tile)
            if not self.thatWasMe(player):
                if self.game.IAmNext():
                    self.ask(move, ['No Claim', 'Chow', 'Pung', 'Kong', 'Mah Jongg'])
                else:
                    self.ask(move, ['No Claim', 'Pung', 'Kong', 'Mah Jongg'])
        elif command in ['calledChow', 'calledPung', 'calledKong']:
            assert self.game.lastDiscard in move.source, '%s %s'% (self.game.lastDiscard, move.source)
            self.invalidateOriginalCall(player)
            if self.thatWasMe(player):
                player.addTile(self.game.lastDiscard)
                player.lastTile = self.game.lastDiscard.lower()
            else:
                player.addTile('Xy')
                player.makeTilesKnown(move.source)
            player.lastSource = 'd'
            player.exposeMeld(move.source)
            if self.thatWasMe(player):
                if command != 'calledKong':
                    # we will get a replacement tile first
                    self.ask(move, ['Discard', 'Mah Jongg'])
            elif self.game.prevActivePlayer == myself and self.perspective:
                # even here we ask: if our discard is claimed we need time
                # to notice - think 3 robots or network timing differences
                self.ask(move, ['OK'])
        elif command == 'error':
            if self.perspective:
                logWarning(move.source) # show messagebox
            else:
                logMessage(move.source, prio=syslog.LOG_WARNING)

    def selectChow(self, chows):
        """selects a chow to be completed. Add more AI here."""
        game = self.game
        myself = game.myself
        for chow in chows:
            belongsToPair = False
            for tileName in chow:
                if myself.concealedTiles.count(tileName) == 2:
                    belongsToPair = True
                    break
            if not belongsToPair:
                return chow

    def maySayChow(self):
        """returns answer arguments for the server if calling chow is possible.
        returns the meld to be completed"""
        game = self.game
        myself = game.myself
        chows = myself.possibleChows(game.lastDiscard)
        if chows:
            return self.selectChow(chows)

    def maySayPung(self):
        """returns answer arguments for the server if calling pung is possible.
        returns the meld to be completed"""
        if self.game.myself.concealedTiles.count(self.game.lastDiscard) >= 2:
            return [self.game.lastDiscard] * 3

    def maySayKong(self):
        """returns answer arguments for the server if calling or declaring kong is possible.
        returns the meld to be completed or to be declared"""
        game = self.game
        myself = game.myself
        if game.activePlayer == myself:
            if self.isRobotClient():
                tileNames = set([x for x in myself.concealedTiles if x[0] not in 'fy'])
            else:
                tileNames = [myself.handBoard.focusTile.element]
            for tileName in tileNames:
                assert tileName[0].isupper(), tileName
                if myself.concealedTiles.count(tileName) == 4:
                    return [tileName] * 4
                searchMeld = tileName.lower() * 3
                allMeldContent = ' '.join(x.joined for x in myself.exposedMelds)
                if searchMeld in allMeldContent:
                    return [tileName.lower()] * 3 + [tileName]
        else:
            if myself.concealedTiles.count(game.lastDiscard) == 3:
                return [game.lastDiscard] * 4

    def maySayMahjongg(self):
        """returns answer arguments for the server if calling or declaring Mah Jongg is possible"""
        game = self.game
        myself = game.myself
        withDiscard = game.lastDiscard if self.moves[-1].command != 'pickedTile' else None
        game.winner = myself
        try:
            hand = myself.computeHandContent(withTile=withDiscard)
        finally:
            game.winner = None
        if hand.maybeMahjongg():
            lastTile = withDiscard or myself.lastTile
            lastMeld = list(hand.computeLastMeld(lastTile).pairs)
            return meldsContent(hand.hiddenMelds), withDiscard, lastMeld
