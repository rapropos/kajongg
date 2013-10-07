# -*- coding: utf-8 -*-

"""
Copyright (C) 2013-2013 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QBrush, QColor

from util import m18nc, logDebug
from message import Message
from common import Internal, isAlive
from player import PlayingPlayer
from game import PlayingGame
from handboard import HandBoard

class VisiblePlayingPlayer(PlayingPlayer):
    """this player instance has a visual representation"""
    # pylint: disable=R0904
    # too many public methods
    def __init__(self, game):
        assert game
        self.handBoard = None # because Player.init calls clearHand()
        PlayingPlayer.__init__(self, game)
        self.__front = self.game.wall[self.idx] # need front before setting handBoard
        self.handBoard = HandBoard(self)
        self.voice = None

    def clearHand(self):
        """clears attributes related to current hand"""
        super(VisiblePlayingPlayer, self).clearHand()
        if self.game and self.game.wall:
            # is None while __del__
            self.front = self.game.wall[self.idx]
        if self.handBoard:
            self.handBoard.showMoveHelper(False)
            self.handBoard.setEnabled(self.game and self.game.belongsToHumanPlayer() and self == self.game.myself)

    def hide(self):
        """clear visible data and hide"""
        self.clearHand()
        self.handBoard.hide()

    @property
    def idx(self):
        """our index in the player list"""
        if not self in self.game.players:
            # we will be added next
            return len(self.game.players)
        return self.game.players.index(self)

    @property
    def front(self):
        """front"""
        return self.__front

    @front.setter
    def front(self, value):
        """also assign handBoard to front"""
        self.__front = value
        if value and self.handBoard:
            self.handBoard.setParentItem(value)

    def handTotalForWall(self):
        """returns the totale for the new hand. Same as current unless we need to discard.
        In that case, make an educated guess about the discard. For player==game.myself, use
        the focussed tile."""
        hand = self.hand
        if hand and hand.tileNames and self._concealedTileNames:
            if hand.lenOffset == 1 and not hand.won:
                if self == self.game.myself:
                    removeTile = self.handBoard.focusTile.element
                elif self.lastTile:
                    removeTile = self.lastTile
                else:
                    removeTile = self._concealedTileNames[0]
                assert removeTile[0] not in 'fy', 'hand:%s remove:%s lastTile:%s' % (
                    hand, removeTile, self.lastTile)
                hand -= removeTile
                assert not hand.lenOffset
        return hand.total()

    def syncHandBoard(self, adding=None):
        """update display of handBoard. Set Focus to tileName."""
        self.handBoard.sync(adding)

    def colorizeName(self):
        """set the color to be used for showing the player name on the wall"""
        if not isAlive(self.front.nameLabel):
            # TODO: should never happen
            logDebug('colorizeName: nameLabel is not alive')
            return
        if self == self.game.activePlayer and self.game.client:
            color = Qt.blue
        elif Internal.field.tilesetName == 'jade':
            color = Qt.white
        else:
            color = Qt.black
        self.front.nameLabel.setBrush(QBrush(QColor(color)))

    def getsFocus(self, dummyResults=None):
        """give this player focus on his handBoard"""
        self.handBoard.setEnabled(True)
        self.handBoard.hasFocus = True

    def popupMsg(self, msg):
        """shows a yellow message from player"""
        if msg != Message.NoClaim:
            self.speak(msg.name.lower())
            yellow = self.front.message
            yellow.setText('  '.join([unicode(yellow.msg), m18nc('kajongg', msg.name)]))
            yellow.setVisible(True)

    def hidePopup(self):
        """hide the yellow message from player"""
        if isAlive(self.front.message):
            self.front.message.msg = ''
            self.front.message.setVisible(False)

    def speak(self, text):
        """speak if we have a voice"""
        if self.voice:
            self.voice.speak(text, self.front.rotation())

    def sortMeldsByX(self):
        """TODO: when we have ScoringHandBoard, get rid of this again"""
        # in a real game, the player melds do not have tiles
        pass

class VisiblePlayingGame(PlayingGame):
    """for the client"""
    # pylint: disable=R0913
    playerClass =  VisiblePlayingPlayer

    def __init__(self, names, ruleset, gameid=None, wantedGame=None, shouldSave=True, \
            client=None, playOpen=False, autoPlay=False):
        PlayingGame.__init__(self, names, ruleset, gameid, wantedGame=wantedGame, shouldSave=shouldSave,
            client=client, playOpen=playOpen, autoPlay=autoPlay)
        for player in self.players:
            player.clearHand()
        Internal.field.adjustView()
        Internal.field.updateGUI()
        self.wall.decorate()

    def close(self):
        """close the game"""
        field = Internal.field
        if isAlive(field):
            field.setWindowTitle('Kajongg')
        if field:
            field.discardBoard.hide()
            if isAlive(field.centralScene):
                field.centralScene.removeTiles()
            field.clientDialog = None
            for player in self.players:
                player.hide()
            if self.wall:
                self.wall.hide()
            field.actionAutoPlay.setChecked(False)
            field.startingGame = False
            field.game = None
            field.updateGUI()
        return PlayingGame.close(self)