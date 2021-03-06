#!/usr/bin/env python3

# lzma-versions.py -- LZMA SDK release git import script
# 2012 - 2015 : Jordan Justen : Public domain

# Usage:
# * Download .zip, .tar.bz2, .7z releases from 7-zip website
# * Update knownSdkDates in this script if needed
# * Run ./lzma-versions.py
#
# Output:
# * A git repo under the lzma-sdk.git sub-directory

import argparse
import hashlib
import libarchive
import os
import re
import shutil
import tarfile
import time
import zipfile
from subprocess import Popen, PIPE

from itertools import dropwhile

basedir = os.getcwd()
edst = os.path.join(basedir, 'extracted')
repodir = os.path.join(basedir, 'lzma-sdk.git')
commitMsgFile = os.path.join(basedir, 'git-commit-log')
gitBin = os.path.join(
    next(filter(
        lambda p: os.path.exists(os.path.join(p, 'git')),
        os.environ['PATH'].split(os.pathsep)
        )),
    'git'
    )
repo_changed = False

files = os.listdir('.')

lzmaArcRe = re.compile(
    '''
        ^
        lzma
        (\d{3,})
        \.
        (?: zip | tar\.bz2 | 7z )
        $
    ''',
    re.VERBOSE
    )

archives = map(
    lambda f: lzmaArcRe.match(f),
    files
    )
archives = filter(lambda mo: mo is not None, archives)
archives = map(
    lambda mo: ('%.2f' % (int(mo.group(1))/100.0), mo.group(0)),
    archives
    )
archives = dict(archives)
versions = sorted(archives.keys(), key=lambda k: float(k))

def ReadCmdLineArgs():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract-all", action="store_true",
                    help="Re-extract all archives")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Print verbose messages")
    global args
    args = ap.parse_args()

class Archive:
    def __init__(self, archive):
        self.archive = archive

    def extractall(self, dst):
        if self.archive.endswith('.zip'):
            assert zipfile.is_zipfile(self.archive)
            zf = zipfile.ZipFile(self.archive, 'r')
            zf.extractall(dst)
        elif self.archive.endswith('.tar.bz2'):
            assert tarfile.is_tarfile(self.archive)
            tf = tarfile.open(self.archive, 'r')
            tf.extractall(dst)
        else:
            self.archive.endswith('.7z')
            savedir = os.getcwd()
            os.makedirs(dst)
            os.chdir(dst)
            libarchive.extract_file(self.archive)
            os.chdir(savedir)

def CheckArchives():
    for version in versions:
        archive = archives[version]
        print(archive + ':')
        dst = os.path.join('extract', version)
        if archive.endswith('.zip'):
            assert zipfile.is_zipfile(archive)
            zf = zipfile.ZipFile(archive, 'r')
            members = zf.namelist()
            print(members)
        else:
            assert tarfile.is_tarfile(archive)
            tf = tarfile.open(archive, 'r')
            members = tf.getnames()
            print(members)

        for m in members:
            assert not m.startswith('/')

def ExtractArchives():
    if args.extract_all and os.path.exists(edst):
        shutil.rmtree(edst)
    if not os.path.exists(edst):
        os.makedirs(edst)
    for version in versions:
        dst = os.path.join(edst, version)
        if os.path.exists(dst):
            continue
        src = os.path.join(os.getcwd(), archives[version])
        arc = Archive(src)
        print('Extracting {} ...'.format(version), end='', flush=True)
        arc.extractall(dst)
        print()

histories = {}

historyVersionRe = re.compile(
    '''
    ^ \s*
    (?: Version \s+ )?
    (\d+ \. \d+)
    \s+
    (?: .*? \s+ )?
    (\d{4}-\d{2}-\d{2})
    \s* $
    ''',
    re.VERBOSE | re.IGNORECASE
    )

def StripCommonIndentation(lines):
    assert len(lines) > 0
    commonIndent = len(lines[0])
    for line in lines:
        commonIndent = min(
            commonIndent,
            len(line) - len(line.lstrip())
            )
    return map(lambda s: s[commonIndent:], lines)

def HistoryDone(version, historyVersion, historyDate, versionLog):
    if historyVersion is not None:
        versionLog = StripCommonIndentation(versionLog)
        histories[version][historyVersion] = {
            'date': historyDate,
            'log': versionLog,
            }

def ReadHistory(version):
    assert version not in histories
    dst = os.path.join(edst, version)
    chlog = os.path.join(dst, 'history.txt')
    if not os.path.exists(chlog):
        chlog = os.path.join(dst, 'DOC', 'lzma-history.txt')
        if not os.path.exists(chlog): return
    f = open(chlog, encoding='iso-8859-1')
    history = f.readlines()
    f.close()
    history = map(lambda s: s.rstrip(), history)
    history = filter(lambda s: len(s) > 0, history)

    histories[version] = {}

    historyVersion = None
    for line in history:
        if (
            line.strip().lower().split() ==
            'HISTORY of the LZMA'.lower().split()
           ):
            break
        mo = historyVersionRe.match(line)
        if mo is not None:
            if historyVersion is not None:
                HistoryDone(
                    version,
                    historyVersion,
                    historyDate,
                    versionLog
                    )
            historyVersion = mo.group(1)
            historyDate = mo.group(2)
            if historyVersion not in versions:
                print('Need', historyVersion)
                assert historyVersion in versions
            versionLog = [line]
        else:
            if historyVersion is not None:
                versionLog.append(line)
    if historyVersion is not None:
        HistoryDone(
            version,
            historyVersion,
            historyDate,
            versionLog
            )

def GetDirectoryForVersion(version):
    return os.path.join(edst, version)

knownSdkDates = {
    '4.62': '2008-12-02',
    '9.07': '2009-08-29',
    '9.10': '2009-12-22',
    '9.20': '2010-11-18',
    '9.22': '2011-04-19',
    '15.05': '2015-06-14',
    '15.06': '2015-08-16',
    '15.07': '2015-09-21',
    '15.08': '2015-10-05',
    '15.10': '2015-11-01',
    '15.11': '2015-11-14',
    '15.13': '2015-12-31',
    '15.14': '2015-12-31',
    '18.00': '2018-01-10',
    '18.01': '2018-01-28',
    }
def GetDateForVersion(version):
    if version in knownSdkDates:
        return knownSdkDates[version]
    if version in histories[versions[-1]]:
        return histories[versions[-1]][version]['date']
    return None

def GetChangelog(version):
    dst = GetDirectoryForVersion(version)
    src = os.path.join(basedir, archives[version])
    cl=[]

    f = open(src, 'rb')
    data = f.read()
    f.close()
    if version in histories[versions[-1]]:
        cl += histories[versions[-1]][version]['log']
        # Get changelogs work better with a subject followed by a blank line
        if len(cl) > 1 and cl[1].strip() != '':
            cl.insert(1, '')
    else:
        date = GetDateForVersion(version)
        if date is not None:
            cl.append('%-14s %s' % (version, date))
        else:
            cl.append(version)
    cl.append('')
    hashes = 'md5 sha1'.split()
    for alg in hashes:
        hobj = hashlib.new(alg)
        hobj.update(data)
        hval = hobj.hexdigest()
        cl.append(
            '%s: %s %s' % (
                alg,
                hval,
                archives[version],
                )
            )
    return '\n'.join(cl)

def CheckForHistoryInconsistencies():
    for i in range(len(versions)):
        version = versions[i]
        for j in range(i + 1, len(versions)):
            version2 = versions[j]
            if version not in histories: continue
            if version2 not in histories: continue
            if version not in histories[version]: continue
            if version not in histories[version2]: continue
            log1 = histories[version][version]
            log1 = ' '.join(log1).lower().split()
            log2 = histories[version2][version]
            log2 = ' '.join(log2).lower().split()
            assert log1 == log2

def ReadHistories():
    for version in versions:
        ReadHistory(version)
    CheckForHistoryInconsistencies()
    for version in versions:
        date = GetDateForVersion(version)
        if date is None:
            print('No date found for version {}!'.format(version))
        assert date is not None

def RunGitCommandInRepostitoryWithOutput(cmd):
    if type(cmd) == str: cmd = cmd.split()
    if args.verbose:
        print('Running:', ' '.join(cmd))
    p = Popen(cmd, executable=gitBin, cwd=repodir, stdout=PIPE,
              encoding='utf-8')
    r = p.wait()
    return p.stdout.readlines()

def RunGitCommandInRepostitory(cmd, addToEnv=None):
    if type(cmd) == str: cmd = cmd.split()
    if args.verbose:
        print('Running:', ' '.join(cmd))

    if addToEnv is not None:
        env = os.environ.copy()
        env.update(addToEnv)
    else:
        env = None

    output = PIPE
    if args.verbose:
        output = None
    p = Popen(cmd, executable=gitBin, cwd=repodir, env=env, stdout=output,
              stderr=output)
    return p.wait()

def InitializeRepository():
    if not os.path.exists(repodir):
        os.makedirs(repodir)

    if not os.path.exists(os.path.join(repodir, '.git')):
        r = RunGitCommandInRepostitory('git init')
        assert r == 0

def ReadTags():
    global tags
    output = RunGitCommandInRepostitoryWithOutput('git tag')
    tags = set(map(lambda s: s.strip(), output))

def CopyVersionToRepository(version):
    for item in os.listdir(repodir):
        if item == '.git': continue
        fullpath = os.path.join(repodir, item)
        if os.path.isfile(fullpath): os.remove(fullpath)
        else: shutil.rmtree(fullpath)
    versionSrc = GetDirectoryForVersion(version)
    for item in os.listdir(versionSrc):
        assert item != '.git'
        fullsrc = os.path.join(versionSrc, item)
        fulldst = os.path.join(repodir, item)
        if os.path.isfile(fullsrc): shutil.copy2(fullsrc, fulldst)
        else: shutil.copytree(fullsrc, fulldst)

def AddVersionToRepository(version):
    global tags

    if version in tags:
        if args.verbose:
            print(version, 'is already in repository')
        return

    global repo_changed
    repo_changed = True

    CopyVersionToRepository(version)

    r = RunGitCommandInRepostitory('git add --all')
    assert r == 0
    f = open(commitMsgFile, 'w', encoding='utf-8')
    f.write(GetChangelog(version))
    f.close()

    date = GetDateForVersion(version)
    if date is not None:
        addToEnv = {
            'GIT_AUTHOR_DATE': time.strftime(
                                   '%a, %d %b %Y %H:%M:%S +0000',
                                   time.strptime(
                                       date + ' 12:00 UTC',
                                       '%Y-%m-%d %H:%M %Z'
                                       )),
            }
    else:
        addToEnv = None
    r = RunGitCommandInRepostitory(
        ('git', 'commit', '--author=Igor Pavlov <support@7-zip.org>', '-F', commitMsgFile),
        addToEnv = addToEnv
        )
    assert r == 0
    os.remove(commitMsgFile)

    r = RunGitCommandInRepostitory(
        ('git', 'tag', version)
        )
    assert r == 0

    print(version, 'was added to the repository')

def AddSdkVersions():
    for version in versions:
        AddVersionToRepository(version)

    if repo_changed:
        r = RunGitCommandInRepostitory('git gc')
        assert r == 0

def PrintSdkVersions():
    for version in versions:
        print(version)
        print(GetChangelog(version))

def UpdateRepository():
    InitializeRepository()
    ReadTags()
    AddSdkVersions()

ReadCmdLineArgs()
ExtractArchives()
ReadHistories()
if args.verbose:
    PrintSdkVersions()
UpdateRepository()
if not repo_changed:
    print('No new versions were found')
