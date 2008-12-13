#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2008 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

import sys, os,  datetime
import functools

NOTFOUND = []

try:
    from PyQt4 import  QtCore,  QtGui,  QtSql
    from PyQt4.QtCore import QVariant
    from PyQt4.QtGui import QColor, QPushButton,  QMessageBox
except ImportError,  e:
    NOTFOUND.append('PyQt4: %s' % e.message) 
    
try:
    from PyKDE4 import kdecore,  kdeui
    from PyKDE4.kdecore import ki18n,  i18n
    from PyKDE4.kdeui import KApplication,  KStandardAction,  KAction
except ImportError, e :
    NOTFOUND.append('PyKDE4: %s' % e.message) 
    
try:
    from board import Board
    from playerlist import PlayerList
    from tilesetselector import TilesetSelector
    from tileset import Tileset
    from genericdelegates import GenericDelegate,  IntegerColumnDelegate
    from config import Preferences,  ConfigDialog
except ImportError,  e:
    NOTFOUND.append('kmj modules: %s' % e.message)

if len(NOTFOUND):
    MSG = "\n".join(" * %s" % s for s in NOTFOUND)
    print MSG
    os.popen("kdialog --sorry '%s'" % MSG)
    sys.exit(3)


WINDS = 'ESWN'

class PlayerWind(Board):
    """a board containing just one wind"""
    windtilenr = {'N':'1', 'S':'2', 'E':'3', 'W':'4'}
    def __init__(self, name, player):
        super(PlayerWind, self).__init__(player)
        self.player = player
        self.name = '' # make pylint happy
        self.prevailing = False
        self.setWind(name, 0)

    def setWind(self, name,  roundctr):
        """change the wind"""
        self.name = name
        self.prevailing = name == WINDS[roundctr]
        self.__show()
        
    def __show(self):
        """why does pylint want a doc string for this private method?"""
        self.setTile("WIND_"+PlayerWind.windtilenr[self.name], 0, 0,  self.prevailing)

class ScoreModel(QtSql.QSqlQueryModel):
    """a model for our score table"""
    def __init__(self,  parent = None):
        super(ScoreModel, self).__init__(parent)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """score table data"""
        if role == QtCore.Qt.BackgroundRole and index.column()==2:
            prevailing = self.data(self.index(index.row(), 0)).toString()
            if prevailing == self.data(index).toString():
                return QVariant(QColor(235, 235, 173))
        if role == QtCore.Qt.BackgroundRole and index.column()==3:
            won = self.data(self.index(index.row(), 1)).toString()
            if won == 'true':
                return QVariant(QColor(165, 255, 165))
        return QtSql.QSqlQueryModel.data(self, index, role)

class Player(QtGui.QWidget):
    """all player related data, GUI and internal together"""
    def __init__(self, wind,  parent = None):
        super(Player, self).__init__(parent)
        self.__balance = 0
        self.__payment = 0
        self.nameid = 0 
        self.wind = PlayerWind(wind, self)
        self.nWidget = QtGui.QWidget()
        self.cbName = QtGui.QComboBox(self.nWidget)
        self.lblName = QtGui.QLabel(self.nWidget)
        self.lblName.hide()
        self.spValue = QtGui.QSpinBox()
        self.lblName.setBuddy(self.spValue)
        self.won = QtGui.QCheckBox("Mah Jongg")
        self.balanceLabel = QtGui.QLabel()
        self.layout = QtGui.QGridLayout(self)
        self.layout.addWidget(self.wind, 0, 0, 3, 1)
        self.layout.addWidget(self.nWidget, 0, 1, 1, 2)
        self.layout.addWidget(self.spValue, 1, 1, 1, 2)
        self.layout.addWidget(self.won, 2, 1, 1, 2)
        self.layout.addWidget(self.balanceLabel, 0, 2)
        self.scoreView = QtGui.QTableView()
        self.scoreView.verticalHeader().hide()
        self.scoreView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.layout.addWidget(self.scoreView, 3, 0, 4, 4)
        self.__fields = ['prevailing', 'won', 'wind', 
                                'points', 'payments', 'balance']
        self.scoreModel = ScoreModel(self)
        self.scoreModel.setHeaderData(self.__fields.index('won'),
                QtCore.Qt.Horizontal, QtCore.QVariant(""))
        self.scoreModel.setHeaderData(self.__fields.index('wind'),
                QtCore.Qt.Horizontal, QtCore.QVariant(""))
        # 0394 is greek big Delta, 2206 is mathematical Delta
        # this works with linux, on Windows we have to check if the used font
        # can display the symbol, otherwise use different font
        self.scoreModel.setHeaderData(self.__fields.index('payments'),
                QtCore.Qt.Horizontal, QtCore.QVariant(u"\u2206"))
        # 03A3 is greek big Sigma, 2211 is mathematical Sigma
        self.scoreModel.setHeaderData(self.__fields.index('balance'),
                QtCore.Qt.Horizontal, QtCore.QVariant(u"\u2211"))
        self.scoreView.setModel(self.scoreModel)
        delegate = GenericDelegate(self)
        delegate.insertColumnDelegate(self.__fields.index('payments'), IntegerColumnDelegate())
        delegate.insertColumnDelegate(self.__fields.index('balance'), IntegerColumnDelegate())
        self.scoreView.setItemDelegate(delegate)
        self.scoreView.setFocusPolicy(QtCore.Qt.NoFocus)

    def setNameList(self, names):
            """initialize the name combo box"""
            cb = self.cbName
            oldName = cb.currentText()
            cb.clear()
            cb.addItems(names)
            if oldName in names:
                cb.setCurrentIndex(cb.findText(oldName))

    def loadTable(self, dbhandle, gameid):
        """load the data for this game and this player"""
        self.scoreModel.setQuery("select %s from score "
        "where game = %d and player = %d" % \
            (', '.join(self.__fields), gameid,  self.nameid),  dbhandle)
        self.scoreView.hideColumn(0)
        self.scoreView.hideColumn(1)
        self.scoreView.resizeColumnsToContents()
        self.scoreView.horizontalHeader().setStretchLastSection(True)

    @property
    def balance(self):
        """the balance of this player"""
        return self.__balance

    def pay(self, payment):
        """make a payment to this player"""
        self.__balance += payment
        self.__payment += payment
        color ='green' if self.balance >= 0 else 'red'
        self.balanceLabel.setText(QtCore.QString(
            '<font color=%1>%2</font>').arg(color).arg(self.balance))
    
    def getName(self):
        """the name of the player"""
        return str(self.cbName.currentText())
        
    def setName(self, name):
        cb = self.cbName
        cb.setCurrentIndex(cb.findText(name))

    name = property(getName,  setName)
    
    @property
    def payment(self):
        """the payments for the current hand"""
        return self.__payment
        
    def __get_score(self):
        """why does pylint want a doc string for this private method?"""
        return self.spValue.value()
            
    def __set_score(self,  score):
        """why does pylint want a doc string for this private method?"""
        self.spValue.setValue(score)
        if score == 0:
            # do not display 0 but an empty field
            self.spValue.clear()
            self.__payment = 0

    score = property(__get_score,  __set_score)
    
    def fixName(self, nameid,  fix=True):
        """make the name of this player mutable(with combobox)
            or immutable (with label)"""
        self.nameid = nameid
        self.cbName.setVisible(not fix)
        self.lblName.setVisible(fix)
        if fix:
            self.lblName.setText(self.name)
            self.layout.removeWidget(self.cbName)
            self.layout.addWidget(self.lblName, 0, 1)
        else:
            self.layout.removeWidget(self.lblName)
            self.layout.addWidget(self.cbName, 0, 1)
         
class MahJongg(kdeui.KXmlGuiWindow):
    """the main window"""
    def __init__(self):
        super(MahJongg, self).__init__()
        self.dbhandle = QtSql.QSqlDatabase("QSQLITE")
        self.dbpath = kdecore.KGlobal.dirs().locateLocal("appdata","kmj.db")
        self.dbhandle.setDatabaseName(self.dbpath)
        dbExists = os.path.exists(self.dbpath)
        if not self.dbhandle.open():
            print self.dbhandle.lastError().text()
            sys.exit(1)
        if not dbExists:
            self.createTables()
            self.addTestData()
        self.playerwindow = None
        self.roundctr = 0
        self.winner = None
        self.shiftRules = 'SWEN,SE,WE' 
        self.setupUi()
        self.setupActions()
        self.creategui()
        self.setUp()
        
    def createTables(self):
        """creates empty tables"""
        query = QtSql.QSqlQuery(self.dbhandle)
        query.exec_("""CREATE TABLE game (
            id integer primary key,
            starttime text default current_timestamp,
            endtime text,
            p0 integer,
            p1 integer,
            p2 integer,
            p3 integer)""")
        query.exec_("""CREATE TABLE player (
            id INTEGER PRIMARY KEY,
            name TEXT)""")
        query.exec_("""CREATE TABLE score(
            game integer,
            hand integer,
            player integer,
            scoretime text,
            won integer,
            prevailing text,
            wind text,
            points integer,
            payments integer,
            balance integer)""")
            
    def addTestData(self):
        """adds test data to an empty data base"""
        query = QtSql.QSqlQuery(self.dbhandle)
        for name in ['Wolfgang',  'Petra',  'Klaus',  'Heide']:
            query.exec_('INSERT INTO player (name) VALUES("%s")' % name)
        
    def creategui(self):
        """create and translate GUI from the ui.rc file: Menu and toolbars"""
        xmlFile = os.path.join(os.getcwd(), 'kmjui.rc')
        if os.path.exists(xmlFile):
            self.setupGUI(kdeui.KXmlGuiWindow.Default, xmlFile)
        else:
            self.setupGUI()
        self.retranslateUi()
        
    def kmjAction(self,  name, icon, slot):
        """simplify defining actions"""
        res = KAction(self)
        res.setIcon(kdeui.KIcon(icon))
        self.connect(res, QtCore.SIGNAL('triggered()'), slot)
        self.actionCollection().addAction(name, res)
        return res
        
    def setupUi(self):
        """create all other widgets"""
        self.setObjectName("MainWindow")
        self.resize(793, 636)
        self.centralwidget = QtGui.QWidget(self)
        self.widgetLayout = QtGui.QGridLayout(self.centralwidget)

        self.players =  [Player(w, self) for w in WINDS]
        self.players[1].scoreView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        for idx, player in enumerate(self.players):
            self.widgetLayout.addWidget(player, 0, idx)
    
        self.setCentralWidget(self.centralwidget)

        self.actionPlayers = self.kmjAction("players",  "personal",  self.slotPlayers)
        self.actionNewHand = self.kmjAction("newhand",  "object-rotate-left",  self.newHand)
                               
        QtCore.QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        """retranslate"""
        self.actionPlayers.setText(i18n("&Players"))
        self.actionNewHand.setText(i18n("&New hand"))
    
    def changeEvent(self, event):
        """when the applicationwide language changes, recreate GUI"""
        if event.type() == QtCore.QEvent.LanguageChange:
            self.creategui()
                
    def slotPlayers(self):
        """show the player list"""
        if not self.playerwindow:
            self.playerwindow = PlayerList(self)
        self.playerwindow.show()

    def slotValidate(self):
        """validate data: Saving is only possible for valid data"""
        valid = not self.gameOver()
        if valid:
            if self.winner is not None and self.winner.score < 20: # TODO minimum score
                valid = False
        if valid:
            names = [p.name for p in self.players]
            for i in names:
                if names.count(i)>1:
                    valid = False
        self.actionNewHand.setEnabled(valid)

    def wonChanged(self):
        """if a new winner has been defined, uncheck any previous winner"""
        clicked = self.sender().parent()
        active = clicked.won.isChecked()
        if active:
            self.winner = clicked
            for player in self.players:
                if player != self.winner:
                    player.won.setChecked(False)
        else:
            if clicked == self.winner:
                self.winner = None
        self.slotValidate()

    def setupActions(self):
        """set up actions"""
        for idx, player in enumerate(self.players):
            self.connect(player.cbName, QtCore.SIGNAL(
                'currentIndexChanged(const QString&)'),
                self.slotValidate)
            self.connect(player.spValue, QtCore.SIGNAL(
                'valueChanged(int)'),
                self.slotValidate)
            self.connect(player.won, QtCore.SIGNAL('stateChanged(int)'), self.wonChanged)
            if idx != 3:
                self.connect(self.players[3].scoreView.verticalScrollBar(),
                        QtCore.SIGNAL('valueChanged(int)'),
                        player.scoreView.verticalScrollBar().setValue)
        kapp = KApplication.kApplication()
        KStandardAction.preferences(self.showSettings, self.actionCollection())
        KStandardAction.quit(kapp.quit, self.actionCollection())
        self.pref = Preferences()
        self.applySettings("settings")


    def applySettings(self,  name):
        """apply preferences"""
        for player in self.players:
            player.spValue.setRange(0, self.pref.upperLimit)
            player.wind.tileset = Tileset(self.pref.tileset)
        
    def showSettings(self):
        """show preferences dialog. If it already is visible, do nothing"""
        if  kdeui.KConfigDialog.showDialog("settings"):
            return
        self.confDialog = ConfigDialog(self, "settings", self.pref)
        self.connect(self.confDialog, QtCore.SIGNAL('settingsChanged(QString)'), 
           self.applySettings);
        self.confDialog.show()
        
    def setUp(self):
        """init a new game"""
        query = QtSql.QSqlQuery(self.dbhandle)
        if not query.exec_("select id,name from player"):
            print query.lastError().text()
            sys.exit(1)
        idField, nameField = range(2)
        self.playerIds = {}
        self.playerNames = {}
        while query.next():
            nameid = query.value(idField).toInt()[0]
            name = str(query.value(nameField).toString())
            self.playerIds[name] = nameid
            self.playerNames[nameid] = name
        self.gameid = 0
        self.roundctr = 0
        self.handctr = 0
        self.rotated = 0
        self.starttime = datetime.datetime.now().replace(microsecond=0)
        # initialize the four winds with the first four players:
        names = self.playerNames.values()
        for idx, player in enumerate(self.players):
            player.setNameList(names)
            player.name = names[idx]
            player.wind.setWind(WINDS[idx],  0)
        self.newHand()

    def saveHand(self):
        """compute and save the scores. Makes player names immutable."""
        if self.winner is None:
            ret = QtGui.QMessageBox.question(None, "Draw?",
                        "Nobody said Mah Jongg. Is this a draw?",
                        QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if ret == QtGui.QMessageBox.No:
                return False
        self.payHand()      
        query = QtSql.QSqlQuery(self.dbhandle)
        query.prepare("INSERT INTO SCORE "
            "(game,hand,player,scoretime,won,prevailing,wind,points,payments, balance) "
            "VALUES(:game,:hand,:player,:scoretime,"
            ":won,:prevailing,:wind,:points,:payments,:balance)")
        query.bindValue(':game', QtCore.QVariant(self.gameid))
        scoretime = datetime.datetime.now().replace(microsecond=0).isoformat()
        query.bindValue(':scoretime', QtCore.QVariant(scoretime))
        for player in self.players:
            name = player.name
            playerid = self.playerIds[name]
            player.fixName(playerid)
            query.bindValue(':hand', QtCore.QVariant(self.handctr))
            query.bindValue(':player', QtCore.QVariant(playerid))
            query.bindValue(':wind', QtCore.QVariant(player.wind.name))
            query.bindValue(':won', QtCore.QVariant(player.won.isChecked()))
            query.bindValue(':prevailing', QtCore.QVariant(WINDS[self.roundctr]))
            query.bindValue(':points', QtCore.QVariant(player.score))
            query.bindValue(':payments', QtCore.QVariant(player.payment))
            query.bindValue(':balance', QtCore.QVariant(player.balance))
            if not query.exec_():
                print 'inserting into score:', query.lastError().text()
                sys.exit(1)
        for player in self.players:
            player.loadTable(self.dbhandle, self.gameid)
        return True
        
    def newHand(self):
        """save this hand and start the next"""
        if self.gameOver():
            # we should never get here
            raise Exception('game over')

        if self.handctr > 0:
            if not self.saveHand():
                return
            if self.winner is None or self.winner.wind.name != 'E':
                self.rotateWinds()
        else:
            query = QtSql.QSqlQuery(self.dbhandle)
            query.prepare("INSERT INTO GAME (starttime,p0,p1,p2,p3)"
                " VALUES(:starttime,:p0,:p1,:p2,:p3)")
            query.bindValue(":starttime", QtCore.QVariant(self.starttime.isoformat()))
            for idx, player in enumerate(self.players):
                query.bindValue(":p%d" % idx, QtCore.QVariant(
                        self.playerIds[player.name]))
            if not query.exec_():
                print 'inserting into game:', query.lastError().text()
                sys.exit(1)
            # now find out which game id we just generated. Clumsy and racy.
            if not query.exec_("select id from game where starttime = '%s'" % \
                               self.starttime.isoformat()):
                print 'getting gameid:', query.lastError().text()
                sys.exit(1)
            query.first()
            self.gameid = query.value(0).toInt()[0]
            
        for player in self.players:
            player.score = 0
        if self.winner:
            self.winner.won.setChecked(False)
        self.handctr += 1

    def gameOver(self):
        """is over after 4 completed rounds"""
        return self.roundctr == 4
        
    def rotateWinds(self):
        """suprise: rotates the winds"""
        self.rotated += 1
        if self.rotated == 4:
            if self.roundctr < 4:
                self.roundctr += 1
            self.rotated = 0
        if self.gameOver():
            endtime = datetime.datetime.now().replace(microsecond=0).isoformat()
            query = QtSql.QSqlQuery(self.dbhandle)
            query.prepare('UPDATE game set endtime = :endtime where id = :id')
            query.bindValue(':endtime', QtCore.QVariant(endtime))
            query.bindValue(':id', QtCore.QVariant(self.gameid))
            if not query.exec_():
                print 'updating game.endtime:', query.lastError().text()
                sys.exit(1)
        else:
            winds = [player.wind.name for player in self.players]
            winds = winds[3:] + winds[0:3]
            for idx,  newWind in enumerate(winds):
                self.players[idx].wind.setWind(newWind,  self.roundctr)
            if 0 < self.roundctr < 4 and self.rotated == 0:
                self.shiftSeats()

    def findPlayer(self, wind):
        """returns the index and the player for wind"""
        for player in self.players:
            if player.wind.name == wind:
                return player
        raise Exception("no player has wind %s" % wind)
                
    def swapPlayers(self, winds):
        """swap the winds for the players with wind in winds"""
        swappers = list(self.findPlayer(winds[x]) for x in (0, 1))
        mbox = QtGui.QMessageBox()
        mbox.setWindowTitle("Swap seats")
        mbox.setText("By the rules, %s and %s should now exchange their seats. " % \
            (swappers[0].name, swappers[1].name))
        yesAnswer = QPushButton("&Exchange")
        mbox.addButton(yesAnswer, QMessageBox.YesRole)
        noAnswer = QPushButton("&Keep seat")
        mbox.addButton(noAnswer, QMessageBox.NoRole)
        mbox.exec_()
        if mbox.clickedButton() == yesAnswer:
            wind0 = swappers[0].wind
            wind1 = swappers[1].wind
            new0,  new1 = wind1.name,  wind0.name
            wind0.setWind(new0,  self.roundctr)
            wind1.setWind(new1,  self.roundctr)
        
    def shiftSeats(self):
        """taken from the OEMC 2005 rules
        2nd round: S and W shift, E and N shift"""
        myRules = self.shiftRules.split(',')[self.roundctr-1]
        while len(myRules):
            self.swapPlayers(myRules[0:2])
            myRules = myRules[2:]
            
    def payHand(self):
        """pay the scores"""
        for idx1, player1 in enumerate(self.players):
            for idx2, player2 in enumerate(self.players):
                if idx1 != idx2:
                    if player1.wind.name == 'E' or player2.wind.name == 'E':
                        efactor = 2
                    else:
                        efactor = 1
                    if player2 != self.winner:
                        player1.pay(player1.score * efactor)
                    if player1 != self.winner:
                        player1.pay(-player2.score * efactor)

class About(object):
    """we need persistent data but do not want to spoil global namespace"""
    def __init__(self):
        self.appName     = "kmj"
        self.catalog     = ""
        self.programName = ki18n ("kmj")
        self.version     = "0.1"
        self.description = ki18n ("kmj - computes payments among the 4 players")
        self.kmjlicense     = kdecore.KAboutData.License_GPL
        self.kmjcopyright   = ki18n ("(c) 2008 Wolfgang Rohdewald")
        self.aboutText        = ki18n("This is the classical Mah Jongg for four players. "
            "If you are looking for the Mah Jongg solitaire please use the "
            "application kmahjongg. Right now this programm only allows to "
            "enter the scores, it will then compute the payments and show "
            "the ranking of the players.")
        self.homePage    = ""
        self.bugEmail    = "wolfgang@rohdewald.de"
        
        self.about  = kdecore.KAboutData (self.appName, self.catalog,
                        self.programName,
                        self.version, self.description,
                        self.kmjlicense, self.kmjcopyright, self.aboutText,
                        self.homePage, self.bugEmail)
                                
ABOUT = About()

kdecore.KCmdLineArgs.init (sys.argv, ABOUT.about)
APP = kdeui.KApplication()
MAINWINDOW = MahJongg()
MAINWINDOW.show()
APP.exec_()
