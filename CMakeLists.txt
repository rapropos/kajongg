# vim: set expandtab shiftwidth=4 softtabstop=4:

project(kajongg)

cmake_minimum_required(VERSION 2.8.12)
set(PYTHON_MIN_VERSION "3.5.0")
set(QT_MIN_VERSION "5.2")
set(KF5_MIN_VERSION "5.15.0")
set(TWISTED_MIN_VERSION "16.6.0")

find_package(ECM 1.2.0 REQUIRED NO_MODULE)
    
set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/cmake-modules ${ECM_MODULE_PATH} ${ECM_KDE_MODULE_DIR})

find_package(PythonInterp ${PYTHON_MIN_VERSION} REQUIRED)
find_package(Twisted ${TWISTED_MIN_VERSION} REQUIRED)
find_package(Qt5 ${QT_MIN_VERSION} REQUIRED NO_MODULE COMPONENTS Core Gui Svg Widgets)
find_package(KF5 ${KF5_MIN_VERSION} REQUIRED COMPONENTS Config DocTools)

include(FeatureSummary)
include(ECMPackageConfigHelpers)
include(ECMSetupVersion)
include(KDEInstallDirs)
include(ECMInstallIcons)
include(KDECMakeSettings)

include(FindPythonInterp)

include(KDEPython)

set(PROJECT_NAME kajongg)

add_subdirectory( voices )
add_subdirectory( doc )
add_subdirectory( icons )

set(SRCFILES
    src/permutations.py
    src/about.py
    src/animation.py
    src/mjresource.py
    src/background.py
    src/backgroundselector.py
    src/board.py
    src/chat.py
    src/handboard.py
    src/message.py
    src/client.py
    src/intelligence.py
    src/altint.py
    src/common.py
    src/wind.py
    src/rand.py
    src/config.py
    src/kdestub.py
    src/deferredutil.py
    src/differ.py
    src/meld.py
    src/player.py
    src/game.py
    src/games.py
    src/genericdelegates.py
    src/guiutil.py
    src/humanclient.py
    src/mi18n.py
    src/login.py
    src/kde.py
    src/dialogs.py
    src/mainwindow.py
    src/move.py
    src/modeltest.py
    src/playerlist.py
    src/predefined.py
    src/qtreactor.py
    src/query.py
    src/rulesetselector.py
    src/hand.py
    src/rule.py
    src/rulecode.py
    src/scene.py
    src/scoringdialog.py
    src/scoring.py
    src/user.py
    src/servertable.py
    src/servercommon.py
    src/server.py
    src/sound.py
    src/tables.py
    src/tile.py
    src/uitile.py
    src/tileset.py
    src/tilesetselector.py
    src/tree.py
    src/statesaver.py
    src/wall.py
    src/uiwall.py
    src/visible.py
    src/log.py
    src/qt.py
    src/configdialog.py
    src/tilesource.py
    src/util.py)

set(DATAFILES
    src/tilesetselector.ui
    src/backgroundselector.ui
    src/kajonggui.rc)

find_package(KF5KMahjongglib REQUIRED)

# In KDE4, this was done with PYKDE4_INSTALL_PYTHON_FILES and PYKDE4_ADD_EXECUTABLE
# because including PYKDE4 does not seem appropriate when not using PYKDE4 bindings,
# I expanded those macros, reducing to what we actually need. No Windows support here yet.
# Those macros come from ./cmake-modules/KDEPython.cmake


configure_file(src/kdepaths.py.in src/kdepaths.py)

KDE_INSTALL_PYTHON_FILES(${SRCFILES} src/kajongg.py src/kajonggserver.py)
KDE_INSTALL_PYTHON_FILES(${CMAKE_CURRENT_BINARY_DIR}/src/kdepaths.py)
KDE_ADD_PYTHON_EXECUTABLE(kajongg.py kajongg)
KDE_ADD_PYTHON_EXECUTABLE(kajonggserver.py kajonggserver)

install(FILES ${DATAFILES} DESTINATION ${DATA_INSTALL_DIR}/kajongg)

install(PROGRAMS org.kde.kajongg.desktop DESTINATION ${KDE_INSTALL_APPDIR})
install(FILES org.kde.kajongg.appdata.xml DESTINATION ${KDE_INSTALL_METAINFODIR})

feature_summary(WHAT ALL INCLUDE_QUIET_PACKAGES FATAL_ON_MISSING_REQUIRED_PACKAGES)
