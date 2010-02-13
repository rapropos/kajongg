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

import socket, subprocess, time, datetime

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet.defer import Deferred
from PyQt4.QtCore import SIGNAL, SLOT, Qt, QSize, QTimer, QPoint
from PyQt4.QtGui import QDialog, QDialogButtonBox, QLayout, QVBoxLayout, QHBoxLayout, QGridLayout, \
    QLabel, QComboBox, QLineEdit, QPushButton, QPalette, QGraphicsProxyWidget, QGraphicsRectItem, \
    QWidget, QPixmap, QProgressBar, QColor, QGraphicsItem, QRadioButton, QApplication

import util
from util import m18n, m18nc, m18ncE, logWarning, logException, logMessage, WINDS, syslogMessage, debugMessage, InternalParameters
import syslog
from scoringengine import Ruleset, PredefinedRuleset, meldsContent, Meld
from game import Players, Game, RemoteGame
from query import Query
from move import Move
from board import Board
from tile import Tile
from client import Client
from statesaver import StateSaver

from PyKDE4.kdeui import KDialogButtonBox
from PyKDE4.kdeui import KMessageBox

class Login(QDialog):
    """login dialog for server"""
    def __init__(self):
        QDialog.__init__(self, None)
        self.setWindowTitle(m18n('Login') + ' - Kajongg')
        self.buttonBox = KDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.connect(self.buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(self.buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        vbox = QVBoxLayout(self)
        grid = QGridLayout()
        lblServer = QLabel(m18n('Game server:'))
        grid.addWidget(lblServer, 0, 0)
        self.cbServer = QComboBox()
        self.cbServer.setEditable(True)
        grid.addWidget(self.cbServer, 0, 1)
        lblServer.setBuddy(self.cbServer)
        lblUsername = QLabel(m18n('Username:'))
        grid.addWidget(lblUsername, 1, 0)
        self.cbUser = QComboBox()
        self.cbUser.setEditable(True)
        self.cbUser.setMinimumWidth(350) # is this good for all platforms?
        lblUsername.setBuddy(self.cbUser)
        grid.addWidget(self.cbUser, 1, 1)
        lblPassword = QLabel(m18n('Password:'))
        grid.addWidget(lblPassword, 2, 0)
        self.edPassword = QLineEdit()
        self.edPassword.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        grid.addWidget(self.edPassword, 2, 1)
        lblPassword.setBuddy(self.edPassword)
        vbox.addLayout(grid)
        vbox.addWidget(self.buttonBox)

        # now load data:
        self.servers = Query('select url, lastname from server order by lasttime desc').data
        if not self.servers:
            self.servers = [('localhost:%d' % util.PREF.serverPort, ''), ]
        for server in self.servers:
            self.cbServer.addItem(server[0])
        if self.cbServer.count() == 0:
            self.cbServer.addItem('localhost')
        self.connect(self.cbServer, SIGNAL('editTextChanged(QString)'), self.serverChanged)
        self.connect(self.cbUser, SIGNAL('editTextChanged(QString)'), self.userChanged)
        self.serverChanged()
        self.state = StateSaver(self)

    def serverChanged(self, text=None):
        Players.load()
        self.cbUser.clear()
        self.cbUser.addItems(list(x[1] for x in Players.allNames.values() if x[0] == self.host))
        self.setServerDefaults(0)

    def setServerDefaults(self, idx):
        """set last username and password for the selected server"""
        userIdx = self.cbUser.findText(self.servers[idx][1])
        if userIdx >= 0:
            self.cbUser.setCurrentIndex(userIdx)

    def userChanged(self, text):
        if text == '':
            return
        passw = Query("select password from player where host=? and name=?",
            list([self.host, str(text)])).data
        if passw:
            self.edPassword.setText(passw[0][0])
        else:
            self.edPassword.clear()

    @apply
    def host():
        def fget(self):
            text = str(self.cbServer.currentText())
            if ':' not in text:
                return text
            hostargs = text.rpartition(':')
            return ''.join(hostargs[0])
        return property(**locals())

    @apply
    def port():
        def fget(self):
            text = str(self.cbServer.currentText())
            if ':' not in text:
                return util.PREF.serverPort
            hostargs = str(self.cbServer.currentText()).rpartition(':')
            try:
                return int(hostargs[2])
            except Exception:
                return util.PREF.serverPort
        return property(**locals())

    @apply
    def username():
        def fget(self):
            return str(self.cbUser.currentText())
        return property(**locals())

    @apply
    def password():
        def fget(self):
            return str(self.edPassword.text())
        return property(**locals())

class SelectChow(QDialog):
    """asks which of the possible chows is wanted"""
    def __init__(self, chows):
        QDialog.__init__(self)
        self.chows = chows
        self.selectedChow = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(m18n('Which chow do you want to expose?')))
        self.buttons = []
        for chow in chows:
            button = QRadioButton('-'.join([chow[0][1], chow[1][1], chow[2][1]]), self)
            self.buttons.append(button)
            layout.addWidget(button)
            self.connect(button, SIGNAL('toggled(bool)'), self.toggled)

    def toggled(self, checked):
        """a radiobutton has been toggled"""
        button = self.sender()
        if button.isChecked():
            self.selectedChow = self.chows[self.buttons.index(button)]
            self.accept()

    def closeEvent(self, event):
        """allow close only if a chow has been selected"""
        if self.selectedChow:
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            QDialog.keyPressEvent(self, event)

class DlgButton(QPushButton):
    """special button for ClientDialog"""
    def __init__(self, parent):
        QPushButton.__init__(self, parent)
        self.parent = parent

    def keyPressEvent(self, event):
        """forward horizintal arrows to the hand board"""
        key = Board.mapChar2Arrow(event)
        if key in [Qt.Key_Left, Qt.Key_Right]:
            game = self.parent.client.game
            if game.activePlayer == game.myself:
                game.myself.handBoard.keyPressEvent(event)
                self.setFocus()
                return
        QPushButton.keyPressEvent(self, event)

class ClientDialog(QDialog):
    """a simple popup dialog for asking the player what he wants to do"""
    def __init__(self, client, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(m18n('Choose') + ' - Kajongg')
        self.client = client
        self.layout = QGridLayout(self)
        self.btnLayout = QHBoxLayout()
        self.layout.addLayout(self.btnLayout, 0, 0)
        self.progressBar = QProgressBar()
        self.timer = QTimer()
        self.connect(self.timer, SIGNAL('timeout()'), self.timeout)
        self.layout.addWidget(self.progressBar, 1, 0)
        self.layout.setAlignment(self.btnLayout, Qt.AlignCenter)
        self.move = None
        self.deferred = None
        self.orderedButtons = []
        self.visibleButtons = []
        self.buttons = {}
        self.btnColor = None
        self.default = None
        self.__declareButton(m18ncE('kajongg','&OK'))
        self.__declareButton(m18ncE('kajongg','&No Claim'))
        self.__declareButton(m18ncE('kajongg','&Discard'))
        self.__declareButton(m18ncE('kajongg','&Pung'))
        self.__declareButton(m18ncE('kajongg','&Kong'))
        self.__declareButton(m18ncE('kajongg','&Chow'))
        self.__declareButton(m18ncE('kajongg','&Mah Jongg'))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.default = self.buttons[self.answers[0]]
            self.selectDefault()
            event.accept()
        else:
            QDialog.keyPressEvent(self, event)

    def __declareButton(self, caption):
        """define a button"""
        btn = DlgButton(self)
        btn.setVisible(False)
        name = caption.replace('&', '')
        btn.setObjectName(name)
        btn.setText(m18nc('kajongg', caption))
        self.btnLayout.addWidget(btn)
        btn.setAutoDefault(True)
        self.connect(btn, SIGNAL('clicked(bool)'), self.selectedAnswer)
        self.orderedButtons.append(btn)
        self.buttons[name] = btn

    def ask(self, move, answers, deferred, tile=None):
        """make buttons specified by answers visible. The first answer is default.
        The default button only appears with blue border when this dialog has
        focus but we always want it to be recognizable. Hence setBackgroundRole."""
        self.move = move
        self.answers = answers
        self.deferred = deferred
        self.visibleButtons = []
        for btn in self.orderedButtons:
            name = btn.objectName()
            btn.setVisible(name in self.answers)
            if name in self.answers:
                self.visibleButtons.append(btn)
            btn.setEnabled(name in self.answers)
        self.show()
        self.default = self.buttons[self.answers[0]]
        self.default.setFocus()
        myTurn = self.client.game.activePlayer == self.client.game.myself
        if InternalParameters.autoMode:
            self.selectDefault()
            return

        self.progressBar.setVisible(not myTurn)
        if myTurn:
            hBoard = self.client.game.myself.handBoard
            hBoard.showFocusRect(hBoard.focusTile)
        else:
            msecs = 50
            self.progressBar.setMinimum(0)
            self.progressBar.setMaximum(self.client.game.ruleset.claimTimeout * 1000 / msecs)
            self.progressBar.reset()
            self.timer.start(msecs)

    def showEvent(self, event):
        """try to place the dialog such that it does not cover interesting information"""
        if not self.parent().clientDialogGeometry:
            parentG = self.parent().geometry()
            parentHeight = parentG.height()
            geometry = self.geometry()
            geometry.moveTop(parentG.y() + 30)
            geometry.moveLeft(parentG.x() + parentG.width()/2) # - self.width()/2)
            self.parent().clientDialogGeometry = geometry
        self.setGeometry(self.parent().clientDialogGeometry)

    def timeout(self):
        """the progressboard wants an update"""
        pBar = self.progressBar
        pBar.setValue(pBar.value()+1)
        pBar.setVisible(True)
        if pBar.value() == pBar.maximum():
            # timeout: we always return the original default answer, not the one with focus
            self.default = self.buttons[self.answers[0]]
            self.selectDefault()
            pBar.setVisible(False)

    def selectDefault(self):
        """select default answer"""
        self.timer.stop()
        answer = str(self.default.objectName())
        self.deferred.callback(answer)
        self.parent().clientDialogGeometry = self.geometry()
        self.hide()

    def selectedAnswer(self, checked):
        """the user clicked one of the buttons"""
        self.default = self.sender()
        self.selectDefault()

class ReadyHandQuestion(QDialog):
    def __init__(self, deferred, parent=None):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.deferred = deferred
        layout = QVBoxLayout(self)
        buttonBox = QDialogButtonBox()
        layout.addWidget(buttonBox)
        self.OKButton = buttonBox.addButton(m18n("&Ready for next hand?"),
          QDialogButtonBox.AcceptRole)
        self.connect(self.OKButton, SIGNAL('clicked(bool)'), self.accept)
        self.setWindowFlags(Qt.Dialog) # Qt.WindowStaysOnTopHint)
        self.setWindowTitle('kajongg')
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("accept()"))

    def accept(self):
        if self.isVisible():
            self.deferred.callback(None)
            self.hide()

    def keyPressEvent(self, event):
        """catch and ignore the Escape key"""
        if event.key() == Qt.Key_Escape:
            event.ignore()
        else:
            QDialog.keyPressEvent(self, event)


class HumanClient(Client):

    serverProcess = None

    def __init__(self, tableList, callback=None):
        Client.__init__(self)
        self.tableList = tableList
        self.callback = callback
        self.connector = None
        self.table = None
        self.discardBoard = tableList.field.discardBoard
        self.serverProcess = None
        self.clientDialog = None
        self.readyHandQuestion = None
        self.login = Login()
        if not self.login.exec_():
            raise Exception(m18n('Login aborted'))
        if self.login.host == 'localhost':
            if not self.serverListening():
                # give the server up to 5 seconds time to start
                HumanClient.startLocalServer()
                for second in range(5):
                    if self.serverListening():
                        break
                    time.sleep(1)
        self.username = self.login.username
        self.root = self.connect()
        self.root.addCallback(self.connected).addErrback(self._loginFailed)

    def isRobotClient(self):
        return False

    def isHumanClient(self):
        return True

    def isServerClient(self):
        return False

    def serverListening(self):
        """is somebody listening on that port?"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect((self.login.host, self.login.port))
        except socket.error:
            return False
        else:
            return True

    @staticmethod
    def startLocalServer():
        """start a local server"""
        try:
            HumanClient.serverProcess = subprocess.Popen(['kajonggserver'])
            syslogMessage(m18n('started the local kajongg server: pid=<numid>%1</numid>', HumanClient.serverProcess.pid))
        except Exception, exc:
            logException(exc)

    @staticmethod
    def stopLocalServer():
        if HumanClient.serverProcess:
            syslogMessage(m18n('stopped the local kajongg server: pid=<numid>%1</numid>', HumanClient.serverProcess.pid))
            HumanClient.serverProcess.kill()
            HumanClient.serverProcess = None

    def __del__(self):
        HumanClient.stopLocalServer()

    def remote_tablesChanged(self, tables):
        """update table list"""
        Client.remote_tablesChanged(self, tables)
        self.tableList.load(self.tables)
        if not self.tables:
            # if we log into the server and there is no table on the server,
            # automatically create a table. This is helpful if we want to
            # play against 3 robots on localhost.
            self.tableList.newTable()

    def readyForGameStart(self, seed, playerNames, shouldSave=True):
        """playerNames are in wind order ESWN"""
        if sum(not x.startswith('ROBOT') for x in playerNames.split('//')) == 1:
            # we play against 3 robots and we already told the server to start: no need to ask again
            wantStart = True
        else:
            assert not self.table
            msg = m18n("The game can begin. Are you ready to play now?\n" \
                "If you answer with NO, you will be removed from the table.")
            wantStart = KMessageBox.questionYesNo (None, msg) == KMessageBox.Yes
        if wantStart:
            Client.readyForGameStart(self, seed, playerNames, self.tableList.field, shouldSave=shouldSave)
        return wantStart

    def readyForHandStart(self, playerNames, rotate):
        """playerNames are in wind order ESWN"""
        if self.game.handctr:
            if InternalParameters.autoMode:
                self.clientReadyForHandStart(None, playerNames, rotate)
                return
            deferred = Deferred()
            deferred.addCallback(self.clientReadyForHandStart, playerNames, rotate)
            self.readyHandQuestion = ReadyHandQuestion(deferred, self.game.field)
            self.readyHandQuestion.show()
            return deferred

    def clientReadyForHandStart(self, none, playerNames, rotate):
        Client.readyForHandStart(self, playerNames, rotate)

    def ask(self, move, answers):
        """server sends move. We ask the user. answers is a list with possible answers,
        the default answer being the first in the list."""
        self.answers = answers
        deferred = Deferred()
        deferred.addCallback(self.answered, move)
        handBoard = self.game.myself.handBoard
        IAmActive = self.game.myself == self.game.activePlayer
        handBoard.setEnabled(IAmActive)
        if not self.clientDialog or not self.clientDialog.isVisible():
            self.clientDialog = ClientDialog(self, self.game.field)
        self.clientDialog.setModal(not IAmActive)
        self.clientDialog.ask(move, answers, deferred)
        return deferred

    def selectChow(self, chows):
        """which possible chow do we want to expose?"""
        if len(chows) == 1:
            return chows[0]
        selDlg = SelectChow(chows)
        assert selDlg.exec_()
        return selDlg.selectedChow

    def answered(self, answer, move):
        """the user answered our question concerning move"""
        if InternalParameters.autoMode:
            self.game.hidePopups()
            return Client.ask(self, move, self.answers)
        message = None
        myself = self.game.myself
        try:
            if answer == 'Discard':
                # do not remove tile from hand here, the server will tell all players
                # including us that it has been discarded. Only then we will remove it.
                myself.handBoard.setEnabled(False)
                return answer, myself.handBoard.focusTile.element
            elif answer == 'Chow':
                chows = myself.possibleChows(self.game.lastDiscard)
                if len(chows):
                    meld = self.selectChow(chows)
                    self.callServer('claim', self.table[0], answer)
                    return answer, meld
                message = m18n('You cannot call Chow for this tile')
            elif answer == 'Pung':
                meld = myself.possiblePung(self.game.lastDiscard)
                if meld:
                    self.callServer('claim', self.table[0], answer)
                    return answer, meld
                message = m18n('You cannot call Pung for this tile')
            elif answer == 'Kong':
                if self.game.activePlayer == myself:
                    meld = myself.containsPossibleKong(myself.handBoard.focusTile.element)
                    if meld:
                        self.callServer('claim', self.table[0], answer)
                        return answer, meld
                    message = m18n('You cannot declare Kong, you need to have 4 identical tiles')
                else:
                    meld = myself.possibleKong(self.game.lastDiscard)
                    if meld:
                        self.callServer('claim', self.table[0], answer)
                        return answer, meld
                    message = m18n('You cannot call Kong for this tile')
            elif answer == 'Mah Jongg':
                withDiscard = self.game.lastDiscard if self.moves[-1].command == 'hasDiscarded' else None
                hand = myself.computeHandContent(withTile=withDiscard)
                if hand.maybeMahjongg():
                    self.callServer('claim', self.table[0], answer)
                    lastTile = withDiscard or myself.lastTile
                    return answer, meldsContent(hand.hiddenMelds), withDiscard, \
                        list(hand.lastMeld(lastTile).pairs)
                message = m18n('You cannot say Mah Jongg with this hand')
            else:
                # the other responses do not have a parameter
                return answer
        finally:
            if message:
                KMessageBox.sorry(None, message)
                self.clientDialog.hide()
                return self.ask(move, self.clientDialog.answers)
            else:
                self.game.hidePopups()

    def checkRemoteArgs(self, tableid):
        """as the name says"""
        if self.table and tableid != self.table.tableid:
            raise Exception('HumanClient.remote_move for wrong tableid %d instead %d' % \
                            (tableid, self.table[0]))

    def remote_move(self, tableid, playerName, command, **kwargs):
        """the server sends us info or a question and always wants us to answer"""
        self.checkRemoteArgs(tableid)
        return Client.remote_move(self, tableid, playerName, command,  **kwargs)

    def remote_abort(self, tableid, message, *args):
        """the server aborted this game"""
        self.checkRemoteArgs(tableid)
        logWarning(m18n(message, *args))
        if self.game:
            self.game.close()

    def remote_serverDisconnects(self):
        """the kajongg server ends our connection"""
        self.perspective = None

    def connect(self):
        """connect self to server"""
        factory = pb.PBClientFactory()
        self.connector = self.tableList.field.reactor.connectTCP(self.login.host, self.login.port, factory)
        cred = credentials.UsernamePassword(self.login.username, self.login.password)
        return factory.login(cred, client=self)

    def _loginFailed(self, failure):
        """login failed"""
        self.login = None  # no longer needed
        logWarning(failure.getErrorMessage())
        if self.callback:
            self.callback()

    def connected(self, perspective):
        """we are online. Update table server and continue"""
        lasttime = datetime.datetime.now().replace(microsecond=0).isoformat()
        qData = Query('select url from server where url=?',
            list([self.host])).data
        if not qData:
            Query('insert into server(url,lastname,lasttime) values(?,?,?)',
                list([self.host, self.username, lasttime]))
        else:
            Query('update server set lastname=?,lasttime=? where url=?',
                list([self.username, lasttime, self.host]))
            Query('update player set password=? where host=? and name=?',
                list([self.login.password, self.host, self.username]))
        self.login = None  # no longer needed
        self.perspective = perspective
        if self.callback:
            self.callback()

    @apply
    def host():
        def fget(self):
            return self.connector.getDestination().host
        return property(**locals())

    def logout(self):
        """clean visual traces and logout from server"""
        d = self.callServer('logout')
        if d:
            d.addBoth(self.loggedOut)
        return d

    def loggedOut(self, result):
        self.discardBoard.hide()
        if self.readyHandQuestion:
            self.readyHandQuestion.hide()
        if self.clientDialog:
            self.clientDialog.hide()

    def callServer(self, *args):
        """if we are online, call server"""
        if self.perspective:
            try:
                return self.perspective.callRemote(*args)
            except pb.DeadReferenceError:
                self.perspective = None
                logWarning(m18n('The connection to the server %1 broke, please try again later.',
                                  self.host))
