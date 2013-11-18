#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (C) 2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

from __future__ import print_function

import os, sys, csv, subprocess, random

from optparse import OptionParser

from common import Debug
from util import removeIfExists, commit
from log import initLog

# fields in row:
RULESET = 0
AI = 1
COMMIT = 2
GAME = 3
TAGS = 4
PLAYERS = 5

def neutralize(rows):
    """remove things we do not want to compare"""
    for row in rows:
        for idx, field in enumerate(row):
            if field.startswith('Tester '):
                row[idx] = 'Tester'
            if 'MEM' in field:
                parts = field.split(',')
                for part in parts[:]:
                    if part.startswith('MEM'):
                        parts.remove(part)
                row[idx] = ','.join(parts)
        yield row

def readGames(csvFile):
    """returns a dict holding a frozenset of games for each variant"""
    if not os.path.exists(csvFile):
        return
    allRows = neutralize(csv.reader(open(csvFile,'r'), delimiter=';'))
    if not allRows:
        return
    # we want unique tuples so we can work with sets
    allRows = set(tuple(x) for x in allRows)
    games = dict()
    # build set of rows for every ai
    for variant in set(tuple(x[:COMMIT]) for x in allRows):
        games[variant] = frozenset(x for x in allRows if tuple(x[:COMMIT]) == variant)
    return games

def printDifferingResults(rowLists):
    """if most games get the same result with all tried variants,
    dump those games that do not"""
    allGameIds = {}
    for rows in rowLists:
        for row in rows:
            rowId = row[GAME]
            if rowId not in allGameIds:
                allGameIds[rowId] = []
            allGameIds[rowId].append(row)
    differing = []
    for key, value in allGameIds.items():
        if len(set(tuple(list(x)[GAME:]) for x in value)) > len(set(tuple(list(x)[:COMMIT]) for x in value)):
            differing.append(key)
    if not differing:
        print('no games differ')
    elif float(len(differing)) / len(allGameIds) < 0.20:
        print('differing games (%d out of %d): %s' % (len(differing), len(allGameIds),
             ', '.join(sorted(differing))))

def evaluate(games):
    """evaluate games"""
    if not games:
        return
    commonGames = set()
    for variant, rows in games.items():
        gameIds = set(x[GAME] for x in rows)
        if len(gameIds) != len(set(tuple(list(x)[GAME:]) for x in rows)):
            print('ruleset "%s" AI "%s" has different rows for games' % (variant[0], variant[1]), end=' ')
            for game in gameIds:
                if len(set(tuple(x[GAME:] for x in rows if x[GAME] == game))) > 1:
                    print(game, end=' ')
            print()
            break
        commonGames &= gameIds
    printDifferingResults(games.values())
    print()
    print('the 3 robot players always use the Default AI')
    print()
    print('common games:')
    print('{ruleset:<25} {ai:<20} {games:>5}     {points:>4}                      human'.format(
        ruleset='Ruleset', ai='AI variant', games='games', points='points'))
    for variant, rows in games.items():
        ruleset, aiVariant = variant
        print('{ruleset:<25} {ai:<20} {games:>5}  '.format(ruleset = ruleset[:25], ai=aiVariant[:20],
            games=len(commonGames)), end=' ')
        for playerIdx in range(4):
            print('{p:>8}'.format(p=sum(int(x[PLAYERS+1+playerIdx*4]) for x in rows if x[GAME] in commonGames)),
                end=' ')
        print()
    print()
    print('all games:')
    for variant, rows in games.items():
        ruleset, aiVariant = variant
        if len(rows) > len(commonGames):
            print('{ruleset:<25} {ai:<20} {rows:>5}  '.format(ruleset=ruleset[:25], ai=aiVariant[:20],
                rows=len(rows)), end=' ')
            for playerIdx in range(4):
                print('{p:>8}'.format(p=sum(int(x[PLAYERS+1+playerIdx*4]) for x in rows)), end=' ')
            print()

def proposeGames(games, optionAIVariants, rulesets):
    """fill holes: returns games for testing such that the csv file
    holds more games tested for all variants"""
    if not games:
        return []
    for key, value in games.items():
        games[key] = frozenset(int(x[GAME]) for x in value)  # we only want the game
    for ruleset in rulesets.split(','):
        for aiVariant in optionAIVariants.split(','):
            variant = tuple([ruleset, aiVariant])
            if variant not in games:
                games[variant] = frozenset()
    allgames = reduce(lambda x, y: x|y, games.values())
    occ = []
    for game in allgames:
        count = sum(game in x for x in games.values())
        if count < len(games.values()):
            occ.append((game, count))
    result = []
    for game in list(x[0] for x in sorted(occ, key=lambda x: -x[1])):
        for variant, ids in games.items():
            ruleset, aiVariant = variant
            if game not in ids:
                result.append((variant, game))
    return result

def srcDir():
    """the path of the directory where kajonggtest has been started in"""
    return os.path.dirname(sys.argv[0])

def startServers(options):
    """starts count servers and returns a list of them"""
    serverProcesses = [None] * options.servers
    for idx in range(options.servers):
        socketName = 'sock{idx}.{rnd}'.format(idx=idx, rnd=random.randrange(10000000))
        cmd = ['{src}/kajonggserver.py'.format(src=srcDir()),
                '--local', '--continue',
                '--socket={sock}'.format(sock=socketName)]
        if options.debug:
            cmd.append('--debug={dbg}'.format(dbg=options.debug))
        serverProcesses[idx] = (subprocess.Popen(cmd), socketName)
    return serverProcesses

def stopServers(serverProcesses):
    """stop server processes"""
    for process, socketName in serverProcesses:
        process.terminate()
        _ = process.wait()
        removeIfExists(socketName)


def doJobs(jobs, options, serverProcesses):
    """now execute all jobs"""
    # pylint: disable=too-many-branches
    # too many local branches

    try:
        commit() # make sure we are at a point where comparisons make sense
    except UserWarning as exc:
        print(exc)
        print()
        print('Disabling CSV output')
        options.csv = None

    clients = [None] * options.clients
    srvIdx = 0
    try:
        while jobs:
            for qIdx, client in enumerate(clients):
                if client:
                    result = client.poll()
                    if result is None:
                        continue
                    clients[qIdx] = None
                if not jobs:
                    break
                _, game = jobs.pop(0)
                ruleset, aiVariant = _
                # never login to the same server twice at the
                # same time with the same player name
                player = qIdx // len(serverProcesses) + 1
                cmd = ['{src}/kajongg.py'.format(src=srcDir()),
                      '--game={game}'.format(game=game),
                      '--socket={sock}'.format(sock=serverProcesses[srvIdx][1]),
                      '--player=Tester {player}'.format(player=player),
                      '--ruleset={ap}'.format(ap=ruleset)]
                if aiVariant != 'Default':
                    cmd.append('--ai={ai}'.format(ai=aiVariant))
                if options.csv:
                    cmd.append('--csv={csv}'.format(csv=options.csv))
                if options.gui:
                    cmd.append('--demo')
                else:
                    cmd.append('--nogui')
                if options.playopen:
                    cmd.append('--playopen')
                if options.debug:
                    cmd.append('--debug={dbg}'.format(dbg=options.debug))
                clients[qIdx] = subprocess.Popen(cmd)
                srvIdx += 1
                srvIdx %= len(serverProcesses)
#    except KeyboardInterrupt:
#        pass
    finally:
        for client in clients:
            if client:
                _ = os.waitpid(client.pid, 0)[1]

def parse_options():
    """parse options"""
    parser = OptionParser()
    parser.add_option('', '--gui', dest='gui', action='store_true',
        default=False, help='show graphical user interface')
    parser.add_option('', '--ruleset', dest='rulesets',
        default='ALL', help='play like a robot using RULESET: comma separated list. If missing, test all rulesets',
        metavar='RULESET')
    parser.add_option('', '--ai', dest='aiVariants',
        default=None, help='use AI variants: comma separated list',
        metavar='AI')
    parser.add_option('', '--csv', dest='csv',
        default='kajongg.csv', help='write results to CSV',
        metavar='CSV')
    parser.add_option('', '--game', dest='game',
        help='start first game with GAMEID, increment for following games.'
            ' Without this, random values are used.',
        metavar='GAMEID', type=int, default=0)
    parser.add_option('', '--count', dest='count',
        help='play COUNT games. Default is 99999',
        metavar='COUNT', type=int, default=99999)
    parser.add_option('', '--playopen', dest='playopen', action='store_true',
        help='all robots play with visible concealed tiles' , default=False)
    parser.add_option('', '--clients', dest='clients',
        help='start CLIENTS kajongg instances simultaneously',
        metavar='CLIENTS', type=int, default=1)
    parser.add_option('', '--servers', dest='servers',
        help='start SERVERS kajonggserver instances. Default is one server for two clients',
        metavar='SERVERS', type=int, default=0)
    parser.add_option('', '--fill', dest='fill', action='store_true',
        help='fill holes in results', default=False)
    parser.add_option('', '--debug', dest='debug',
        help=Debug.help())

    return parser.parse_args()

def improve_options(options):
    """add sensible defaults"""
    if options.game and not options.count:
        options.count = 1
    options.clients = min(options.clients, options.count)
    if options.servers == 0:
        options.servers = max(1, options.clients // 2)

    cmd = ['{src}/kajongg.py'.format(src=srcDir()), '--rulesets=']
    knownRulesets = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0].split('\n')
    knownRulesets = list(x.strip() for x in knownRulesets if x.strip())
    if options.rulesets == 'ALL':
        options.rulesets = ','.join(knownRulesets)
        print('testing all rulesets:', options.rulesets)
    else:
        wantedRulesets = options.rulesets.split(',')
        wrong = False
        for ruleset in wantedRulesets:
            matches = list(x for x in knownRulesets if ruleset in x)
            if len(matches) == 0:
                print('ruleset', ruleset, 'is not known', end=' ')
                wrong = True
            elif len(matches) > 1:
                print('ruleset', ruleset, 'is ambiguous:', matches)
                wrong = True
        if wrong:
            sys.exit(1)

    return options

def main():
    """parse options, play, evaluate results"""

    initLog('kajonggtest')

    (options, args) = parse_options()

    evaluate(readGames(options.csv))

    options = improve_options(options)

    errorMessage = Debug.setOptions(options.debug)
    if errorMessage:
        print(errorMessage)
        sys.exit(2)

    if args and ''.join(args):
        print('unrecognized arguments:', ' '.join(args))
        sys.exit(2)

    if not options.count and not options.fill:
        sys.exit(0)

    if not options.aiVariants:
        options.aiVariants = 'Default'

    print()

    serverProcesses = startServers(options)
    try:
        if options.fill:
            jobs = proposeGames(readGames(options.csv), options.aiVariants, options.rulesets)
            doJobs(jobs, options, serverProcesses)

        if options.count:
            if options.game:
                games = list(range(int(options.game), options.game+options.count))
            else:
                games = list(int(random.random() * 10**9) for _ in range(options.count))
            jobs = []
            rulesets = options.rulesets.split(',')
            allAis = options.aiVariants.split(',')
            for game in games:
                jobs.extend([(tuple([x, y]), game) for x in rulesets for y in allAis])
            doJobs(jobs, options, serverProcesses)
    finally:
        stopServers(serverProcesses)

    if options.csv:
        evaluate(readGames(options.csv))

# is one server for two clients.
if __name__ == '__main__':
    main()
