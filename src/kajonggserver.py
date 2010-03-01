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

The DBPasswordChecker is based on an example from the book
Twisted Network Programming Essentials by Abe Fettig. Copyright 2006
O'Reilly Media, Inc., ISBN 0-596-10032-9
"""

import syslog
syslog.openlog('kajonggserver')

from twisted.spread import pb
from twisted.internet import error
from twisted.internet.defer import Deferred, maybeDeferred, DeferredList
from zope.interface import implements
from twisted.cred import checkers, portal, credentials, error as credError
import random
#from PyKDE4.kdecore import ki18n
#from PyKDE4.kdeui import KApplication
#from about import About
from game import RemoteGame, Players, WallEmpty
from client import Client
from query import Query, InitDb
import predefined  # make predefined rulesets known, ignore pylint warning
from scoringengine import Ruleset, Meld, PAIR, PUNG, KONG, CHOW
from util import m18n, m18nE, m18ncE, syslogMessage, debugMessage, logWarning, SERVERMARK, \
  logException
from common import WINDS, InternalParameters

TABLEID = 0

def srvError(cls, *args):
    """send all args needed for m18n encoded in one string.
    For an explanation see util.translateServerString"""
    raise cls(SERVERMARK+SERVERMARK.join(list([str(x) for x in args])))

class DBPasswordChecker(object):
    """checks against our sqlite3 databases"""
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, cred):
        """get user id from data base"""
        query = Query('select id, password from player where host=? and name=?',
            list([Query.serverName, cred.username]))
        if not len(query.data):
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        userid, password = query.data[0]
        defer1 = maybeDeferred(cred.checkPassword, password)
        defer1.addCallback(self._checkedPassword, userid)
        return defer1

    def _checkedPassword(self, matched, userid):
        """after the password has been checked"""
        if not matched:
            raise srvError(credError.UnauthorizedLogin, m18nE('Wrong username or password'))
        return userid

class Message(object):
    """holds a Deferred and related data, used as part of a DeferredBlock"""
    def __init__(self, deferred, player):
        self.deferred = deferred
        self.player = player
        self.result = None
        self.answer = None
        self.args = None
        self.kwargs = None

    def __str__(self):
        return '%s: result=%s answer:%s/%s args:%s' % (self.player, self.result, type(self.answer), self.answer, self.args)

class DeferredBlock(object):
    """holds a list of deferreds and waits for each of them individually,
    with each deferred having its own independent callbacks. Fires a
    'general' callback after all deferreds have returned."""

    blocks = []

    def __init__(self, table):
        self.garbageCollection()
        self.table = table
        self.requests = []
        self.__callback = None
        self.outstanding = 0
        self.completed = False
        DeferredBlock.blocks.append(self)

    def garbageCollection(self):
        """delete completed blocks"""
        for block in DeferredBlock.blocks[:]:
            if block.completed:
                DeferredBlock.blocks.remove(block)

    def add(self, deferred, player):
        """add deferred for player to this block"""
        assert not self.__callback
        assert not self.completed
        msg = Message(deferred, player)
        self.requests.append(msg)
        self.outstanding += 1
        deferred.addCallback(self.__gotAnswer, msg).addErrback(self.__failed, msg)

    def removeRequest(self, request):
        """we do not want this request anymore"""
        self.requests.remove(request)
        self.outstanding -= 1

    def callback(self, cb):
        """to be done after all players answered"""
        assert not self.completed
        self.__callback = cb
        if self.outstanding <= 0:
            cb(self.requests)

    def __gotAnswer(self, result, request, *args, **kwargs):
        """got answer from player"""
        assert not self.completed
        if isinstance(result, tuple):
            request.answer = result[0]
            request.args = result[1:]
        else:
            request.answer = result
        request.kwargs = kwargs
        self.outstanding -= 1

        if request.answer in ['Chow', 'Pung', 'Kong', 'Mah Jongg']:
            block = DeferredBlock(self.table)
            block.tellAll(request.player, 'popupMsg', msg=request.answer)

        if self.outstanding <= 0 and self.__callback:
            self.completed = True
            self.__callback(self.requests)

    def __failed(self, result, request, *args, **kwargs):
        """a player did not or not correctly answer"""
        if result.type in  [pb.PBConnectionLost]:
            msg = m18nE('The game server lost connection to player %1')
            self.table.abort(msg, request.player.name)
        else:
            msg = m18nE('Unknown error for player %1: %2\n%3')
            self.table.abort(msg, request.player.name, result.getErrorMessage(), result.getTraceback())

    def __sendMove(self, other, about, command, **kwargs):
        """send info about player 'about' to player 'other'"""
        if InternalParameters.showTraffic:
            if not isinstance(other.remote, Client):
                debugMessage('SERVER to %s about %s: %s %s' % (other, about, command, kwargs))
        if isinstance(other.remote, Client):
            defer = Deferred()
            defer.addCallback(other.remote.remote_move, command, **kwargs)
            defer.callback(about.name)
        else:
            defer = self.table.server.callRemote(other.remote, 'move', about.name, command, **kwargs)
        if defer:
            # the remote player might already be disconnected
            self.add(defer, other)

    def tellPlayer(self, player, command,  **kwargs):
        """address only one player"""
        self.__sendMove(player, player, command, **kwargs)

    def tellOthers(self, player, command, **kwargs):
        """tell others about 'player'"""
        for other in self.table.game.players:
            if other != player:
                self.__sendMove(other, player, command, **kwargs)

    def tellAll(self, player, command, **kwargs):
        """tell something to all players"""
        for other in self.table.game.players:
            self.__sendMove(other, player, command, **kwargs)

class Table(object):
    """a table on the game server"""
    TableId = 0
    def __init__(self, server, owner, rulesetStr):
        self.server = server
        self.owner = owner
        self.rulesetStr = rulesetStr
        self.ruleset = Ruleset.fromList(rulesetStr)
        self.owningPlayer = None
        Table.TableId = Table.TableId + 1
        self.tableid = Table.TableId
        self.users = [owner]
        self.preparedGame = None
        self.game = None

    def addUser(self, user):
        """add user to this table"""
        if user.name in list(x.name for x in self.users):
            raise srvError(pb.Error, m18nE('You already joined this table'))
        if len(self.users) == 4:
            raise srvError(pb.Error, m18nE('All seats are already taken'))
        self.users.append(user)
        if len(self.users) == 4:
            self.readyForGameStart()

    def delUser(self, user):
        """remove user from this table"""
        if user in self.users:
            self.game = None
            self.users.remove(user)
            if user is self.owner:
                # silently pass ownership
                if self.users:
                    self.owner = self.users[0]

    def __repr__(self):
        """for debugging output"""
        return str(self.tableid) + ':' + ','.join(x.name for x in self.users)

    def readyForGameStart(self, user):
        """the table initiator told us he wants to start the game"""
        if len(self.users) < 4 and self.owner != user:
            raise srvError(pb.Error,
                m18nE('Only the initiator %1 can start this game, you are %2'),
                self.owner.name, user.name)
        names = list(x.name for x in self.users)
        # the server and all databases save the english name but we
        # want to make sure a translation exists for the client GUI
        robotNames = [
            m18ncE('kajongg', 'ROBOT 1'),
            m18ncE('kajongg', 'ROBOT 2'),
            m18ncE('kajongg', 'ROBOT 3')]
        while len(names) < 4:
            names.append(robotNames[3 - len(names)])
        game = RemoteGame(names, self.ruleset, client=Client())
        self.preparedGame = game
        for player, user in zip(game.players, self.users):
            player.remote = user
            if user == self.owner:
                self.owningPlayer = player
        for player in game.players:
            if not player.remote:
                player.remote = Client(player.name)
                player.remote.table = self
        random.shuffle(game.players)
        for player, wind in zip(game.players, WINDS):
            player.wind = wind
        # send the names for players E,S,W,N in that order:
        # for each database, only one Game instance should save.
        dbPaths = ['127.0.0.1:' + Query.dbhandle.databaseName()]
        block = DeferredBlock(self)
        for player in game.players:
            if isinstance(player.remote, User):
                peer = player.remote.mind.broker.transport.getPeer()
                path = peer.host + ':' + player.remote.dbPath
                shouldSave = path not in dbPaths
                if shouldSave:
                    dbPaths.append(path)
            else:
                shouldSave = False
            block.tellPlayer(player, 'readyForGameStart', tableid=self.tableid, shouldSave=shouldSave,
                seed=game.seed, source='//'.join(x.name for x in game.players))
        block.callback(self.startGame)

    def startGame(self, requests):
        """if all players said ready, start the game"""
        for msg in requests:
            if msg.answer != True:
                # this player answered "I am not ready", exclude her from table
                self.server.leaveTable(msg.player.remote, self.tableid)
                self.preparedGame = None
                return
        self.game = self.preparedGame
        self.preparedGame = None
        # if the players on this table also reserved seats on other tables,
        # clear them
        for user in self.users:
            for tableid in self.server.tables.keys()[:]:
                if tableid != self.tableid:
                    self.server.leaveTable(user, tableid)
        self.startHand()

    def pickTile(self, results=None, deadEnd=False):
        """the active player gets a tile from wall. Tell all clients."""
        player = self.game.activePlayer
        block = DeferredBlock(self)
        try:
            tile = self.game.wall.dealTo(deadEnd=deadEnd)[0]
            self.game.pickedTile(player, tile, deadEnd)
        except WallEmpty:
            block.callback(self.endHand)
        else:
            block.tellPlayer(player, 'pickedTile', source=tile, deadEnd=deadEnd)
            if tile[0] in 'fy':
                block.tellOthers(player, 'pickedTile', source=tile, deadEnd=deadEnd)
            else:
                block.tellOthers(player, 'pickedTile', source= 'Xy', deadEnd=deadEnd)
            block.callback(self.moved)

    def pickDeadEndTile(self, results=None):
        """the active player gets a tile from the dead end. Tell all clients."""
        self.pickTile(results, deadEnd=True)

    def startHand(self, results=None):
        """all players are ready to start a hand, so do it"""
        self.game.prepareHand()
        self.game.deal()
        block = DeferredBlock(self)
        block.tellAll(self.owningPlayer, 'initHand',
            divideAt=self.game.divideAt)
        for player in self.game.players:
            block.tellPlayer(player, 'setTiles', source=player.concealedTiles + player.bonusTiles)
            block.tellOthers(player, 'setTiles', source= ['Xy']*13+player.bonusTiles)
        block.callback(self.dealt)

    def endHand(self, results):
        """hand is over, show all concealed tiles to all players"""
        block = DeferredBlock(self)
        for player in self.game.players:
            block.tellOthers(player, 'showTiles', source=player.concealedTiles)
        block.callback(self.saveHand)

    def saveHand(self, results):
        """save the hand to the database and proceed to next hand"""
        self.game.saveHand()
        block = DeferredBlock(self)
        block.tellAll(self.owningPlayer, 'saveHand')
        block.callback(self.nextHand)

    def nextHand(self, results):
        """next hand: maybe rotate"""
        rotate = self.game.maybeRotateWinds()
        if self.game.finished():
            self.abort(m18nE('The game is over!'))
            return
        self.game.sortPlayers()
        playerNames = '//'.join(self.game.players[x].name for x in WINDS)
        block = DeferredBlock(self)
        block.tellAll(self.owningPlayer, 'readyForHandStart', source=playerNames,
          rotate=rotate)
        block.callback(self.startHand)

    def abort(self, message, *args):
        """abort the table. Reason: message/args"""
        self.server.abortTable(self, message, *args)

    def claimTile(self, player, claim, meldTiles, nextMessage):
        """a player claims a tile for pung, kong, chow or Mah Jongg.
        meldTiles contains the claimed tile, concealed"""
        claimedTile = player.game.lastDiscard
        if claimedTile not in meldTiles:
            msg = m18nE('Tile %1 discarded by %2 is not in meld %3')
            self.abort(msg, str(claimedTile), player.name, ''.join(meldTiles))
            return
        meld = Meld(meldTiles)
        concKong =  len(meldTiles) == 4 and meldTiles[0][0].isupper() and meldTiles == [meldTiles[0]]*4
        # this is a concealed kong with 4 concealed tiles, will be changed to x#X#X#x#
        # by exposeMeld()
        if not concKong and meld.meldType not in [PAIR, PUNG, KONG, CHOW]:
            msg = m18nE('%1 wrongly said %2 for meld %3')
            self.abort(msg, player.name, m18n(claim), str(meld))
            return
        checkTiles = meldTiles[:]
        checkTiles.remove(claimedTile)
        if not player.hasConcealedTiles(checkTiles):
            msg = m18nE('%1 wrongly said %2: claims to have concealed tiles %3 but only has %4')
            self.abort(msg, player.name, m18n(claim), ''.join(checkTiles), ''.join(player.concealedTiles))
            return
        self.game.activePlayer = player
        player.addTile(claimedTile)
        player.lastTile = claimedTile.lower()
        player.lastSource = 'd'
        player.exposeMeld(meldTiles)
        block = DeferredBlock(self)
        block.tellAll(player, nextMessage, source=meldTiles)
        if claim == 'Kong':
            block.callback(self.pickDeadEndTile)
        else:
            block.callback(self.moved)

    def declareKong(self, player, meldTiles):
        """player declares a Kong, meldTiles is a list"""
        if not player.hasConcealedTiles(meldTiles) and not player.hasExposedPungOf(meldTiles[0]):
            msg = m18nE('declareKong:%1 wrongly said Kong for meld %2')
            args = (player.name, ''.join(meldTiles))
            syslogMessage(m18n(msg, *args), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedTiles:%s' % ''.join(player.concealedTiles), syslog.LOG_ERR)
            syslogMessage('declareKong:concealedMelds:%s' % \
                ' '.join(x.joined for x in player.concealedMelds), syslog.LOG_ERR)
            syslogMessage('declareKong:exposedMelds:%s' % \
                ' '.join(x.joined for x in player.exposedMelds), syslog.LOG_ERR)
            self.abort(msg, *args)
            return
        player.exposeMeld(meldTiles, claimed=False)
        block = DeferredBlock(self)
        block.tellAll(player, 'declaredKong', source=meldTiles)
        block.callback(self.pickDeadEndTile)

    def claimMahJongg(self, player, concealedMelds, withDiscard, lastMeld):
        """a player claims mah jongg. Check this and if correct, tell all."""
        ignoreDiscard = withDiscard
        for part in concealedMelds.split():
            meld = Meld(part)
            for pair in meld.pairs:
                if pair == ignoreDiscard:
                    ignoreDiscard = None
                else:
                    if not pair in player.concealedTiles:
                        msg = m18nE('%1 claiming MahJongg: She does not really have tile %2')
                        self.abort(msg, player.name, pair)
                    player.concealedTiles.remove(pair)
            player.concealedMelds.append(meld)
        if player.concealedTiles:
            msg = m18nE('%1 claiming MahJongg: She did not pass all concealed tiles to the server')
            self.abort(msg, player.name)
        player.declaredMahJongg(concealedMelds, withDiscard, player.lastTile, lastMeld)
        if not player.computeHandContent().maybeMahjongg():
            msg = m18nE('%1 claiming MahJongg: This is not a winning hand: %2')
            self.abort(msg, player.name, player.computeHandContent().string)
        block = DeferredBlock(self)
        block.tellAll(player, 'declaredMahJongg', source=concealedMelds, lastTile=player.lastTile,
                     lastMeld=list(lastMeld.pairs), withDiscard=withDiscard, winnerBalance=player.balance)
        block.callback(self.endHand)

    def dealt(self, results):
        """all tiles are dealt, ask east to discard a tile"""
        block = DeferredBlock(self)
        block.tellAll(self.game.activePlayer, 'activePlayer')
        block.callback(self.pickTile)

    def nextTurn(self):
        """the next player becomes active"""
        self.game.nextTurn()
        block = DeferredBlock(self)
        block.tellAll(self.game.activePlayer, 'activePlayer')
        block.callback(self.pickTile)

    def moved(self, requests):
        """a player did something"""
        answers = [x for x in requests if x.answer not in ['No Claim', 'OK', None]]
        if not answers:
            self.nextTurn()
            return
        if len(answers) > 1:
            for answerMsg in ['Mah Jongg', 'Kong', 'Pung', 'Chow', 'OK']:
                if answerMsg in [x.answer for x in answers]:
                    # ignore answers with lower priority:
                    answers = [x for x in answers if x.answer == answerMsg]
                    break
        if len(answers) > 1 and answers[0].answer == 'Mah Jongg':
            answeredPlayers = [x.player for x in answers]
            nextPlayer = self.game.nextPlayer()
            while nextPlayer not in answeredPlayers:
                nextPlayer = self.game.nextPlayer(nextPlayer)
            answers = [x for x in answers if x.player == nextPlayer]
        if len(answers) > 1:
            self.abort('More than one player said %s' % answers[0].answer)
            return
        assert len(answers) == 1, answers
        player, answer, args = answers[0].player, answers[0].answer, answers[0].args
        if InternalParameters.showTraffic:
            debugMessage('%s ANSWER: %s %s' % (player, answer, args))
        if answer in ['Discard', 'Bonus']:
            if player != self.game.activePlayer:
                msg = '%s said %s but is not the active player' % (player, answer)
                self.abort(msg)
                return
        if answer == 'Discard':
            tile = args[0]
            if tile not in player.concealedTiles:
                self.abort('player %s discarded %s but does not have it' % (player, tile))
                return
            block = DeferredBlock(self)
            block.tellAll(player, 'hasDiscarded', tile=tile)
            self.game.hasDiscarded(player, tile)
            block.callback(self.moved)
        elif answer == 'Chow':
            if self.game.nextPlayer() != player:
                self.abort('player %s illegally said Chow' % player)
                return
            self.claimTile(player, answer, args[0], 'calledChow')
        elif answer == 'Pung':
            self.claimTile(player, answer, args[0], 'calledPung')
        elif answer == 'Kong':
            if player == self.game.activePlayer:
                self.declareKong(player, args[0])
            else:
                self.claimTile(player, answer, args[0], 'calledKong')
        elif answer == 'Mah Jongg':
            self.claimMahJongg(player, args[0], args[1], Meld(args[2]))
        elif answer == 'Bonus':
            block = DeferredBlock(self)
            block.tellOthers(player, 'pickedBonus', source=args[0])
            block.callback(self.pickTile)
        else:
            logException('unknown args: %s %s %s' % (player, answer, args))

class MJServer(object):
    """the real mah jongg server"""
    def __init__(self):
        self.tables = {}
        self.users = list()
        Players.load()
    def login(self, user):
        """accept a new user"""
        if not user in self.users:
            self.users.append(user)

    def callRemote(self, user, *args, **kwargs):
        """if we still have a connection, call remote, otherwise clean up"""
        if user.mind:
            try:
                return user.mind.callRemote(*args, **kwargs)
            except (pb.DeadReferenceError, pb.PBConnectionLost), errObj:
                user.mind = None
                self.logout(user)

    def ignoreLostConnection(self, failure):
        """if the client went away, do not dump error messages on stdout"""
        failure.trap(pb.PBConnectionLost)

    def broadcast(self, *args):
        """tell all users of this server"""
        if InternalParameters.showTraffic:
            debugMessage('SERVER broadcasts: %s' % ' '.join([str(x) for x in args]))
        for user in self.users:
            defer = self.callRemote(user, *args)
            if defer:
                defer.addErrback(self.ignoreLostConnection)

    def tableMsg(self):
        """build a message containing table info"""
        msg = list()
        for table in self.tables.values():
            msg.append(tuple([table.tableid, table.rulesetStr, tuple(x.name for x in table.users)]))
        return msg

    def requestTables(self, user):
        """user requests the table list"""
        defer = self.callRemote(user, 'tablesChanged', self.tableMsg())
        if defer:
            defer.addErrback(self.ignoreLostConnection)

    def broadcastTables(self):
        """tell all users about changed tables"""
        self.broadcast('tablesChanged', self.tableMsg())

    def _lookupTable(self, tableid):
        """return table by id or raise exception"""
        if tableid not in self.tables:
            raise srvError(pb.Error, m18nE('table with id <numid>%1</numid> not found'), tableid)
        return self.tables[tableid]

    def newTable(self, user, ruleset=None):
        """user creates new table and joins it"""
        table = Table(self, user, ruleset)
        self.tables[table.tableid] = table
        self.broadcastTables()
        return table.tableid

    def joinTable(self, user, tableid):
        """user joins table"""
        self._lookupTable(tableid).addUser(user)
        self.broadcastTables()
        return True

    def leaveTable(self, user, tableid):
        """user leaves table. If no human user is left on table, delete it"""
        table = self._lookupTable(tableid)
        table.delUser(user)
        if not table.users:
            del self.tables[tableid]
        self.broadcastTables()
        return True

    def startGame(self, user, tableid):
        """try to start the game"""
        return self._lookupTable(tableid).readyForGameStart(user)

    def abortTable(self, table, message, *args):
        """abort a table"""
        syslogMessage(m18n(message, *args))
        if table.tableid in self.tables:
            for user in table.users:
                table.delUser(user)
            self.broadcast('abort', table.tableid, message, *args)
            del self.tables[table.tableid]
            self.broadcastTables()

    def logout(self, user):
        """remove user from all tables"""
        if user in self.users and user.mind:
            defer = self.callRemote(user,'serverDisconnects')
            if defer:
                defer.addErrback(self.ignoreLostConnection)
            user.mind = None
            for block in DeferredBlock.blocks:
                for request in block.requests:
                    if request.player.remote == user:
                        block.removeRequest(request)
                    if block.table.game:
                        self.abortTable(block.table, m18nE('Player %1 has logged out'), user.name)
                    else:
                        self.leaveTable(user, block.table.tableid)
            if user in self.users: # avoid recursion : a disconnect error calls logout
                self.users.remove(user)

class User(pb.Avatar):
    """the twisted avatar"""
    def __init__(self, userid):
        self.userid = userid
        self.name = Query(['select name from player where id=%d' % userid]).data[0][0]
        self.mind = None
        self.server = None
        self.dbPath = None
    def attached(self, mind):
        """override pb.Avatar.attached"""
        self.mind = mind
        self.server.login(self)
    def detached(self, mind):
        """override pb.Avatar.detached"""
        self.server.logout(self)
        self.mind = None
    def perspective_setDbPath(self, dbPath):
        """perspective_* methods are to be called remotely"""
        self.dbPath = dbPath
    def perspective_requestTables(self):
        """perspective_* methods are to be called remotely"""
        return self.server.requestTables(self)
    def perspective_joinTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.joinTable(self, tableid)
    def perspective_leaveTable(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.leaveTable(self, tableid)
    def perspective_newTable(self, ruleset):
        """perspective_* methods are to be called remotely"""
        return self.server.newTable(self, ruleset)
    def perspective_startGame(self, tableid):
        """perspective_* methods are to be called remotely"""
        return self.server.startGame(self, tableid)
    def perspective_logout(self):
        """perspective_* methods are to be called remotely"""
        self.server.logout(self)
        self.mind = None

class MJRealm(object):
    """connects mind and server"""
    implements(portal.IRealm)

    def __init__(self):
        self.server = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        """as the tutorials do..."""
        if not pb.IPerspective in interfaces:
            raise NotImplementedError,  "No supported avatar interface"
        avatar = User(avatarId)
        avatar.server = self.server
        avatar.attached(mind)
        return pb.IPerspective, avatar, lambda a = avatar:a.detached(mind)

def kajonggServer():
    """start the server"""
    from twisted.internet import reactor
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('', '--port', dest='port', help=m18n('the server will listen on PORT'),
        metavar='PORT', default=8149)
    parser.add_option('', '--showtraffic', dest='showtraffic', action='store_true',
        help=m18n('the server will show network messages'), default=False)
    parser.add_option('', '--showsql', dest='showsql', action='store_true',
        help=m18n('show database SQL commands'), default=False)
    parser.add_option('', '--seed', dest='seed',
        help=m18n('for testing purposes: Initializes the random generator with SEED'),
        metavar='SEED', default=0)
    parser.add_option('', '--db', dest='dbpath', help=m18n('name of the database'), default=None)
    (options, args) = parser.parse_args()
    InternalParameters.seed = int(options.seed)
    port = int(options.port)
    InternalParameters.showTraffic |= options.showtraffic
    InternalParameters.showSql |= options.showsql
    if options.dbpath:
        InternalParameters.dbPath = options.dbpath
    InitDb()
    realm = MJRealm()
    realm.server = MJServer()
    kajonggPortal = portal.Portal(realm, [DBPasswordChecker()])
    try:
        reactor.listenTCP(port, pb.PBServerFactory(kajonggPortal))
    except error.CannotListenError, errObj:
        logWarning(errObj)
    else:
        reactor.run()


if __name__ == '__main__':
    kajonggServer()
