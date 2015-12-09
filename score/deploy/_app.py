# Copyright © 2015 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.


from score.uwsgi import NotRunning
import random
import os
import logging
import shutil
import sys
import time
import venv
from subprocess import Popen, PIPE


log = logging.getLogger(__name__)


def mkname():
    words = ["alfa", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
             "hotel", "india", "juliett", "kilo", "lima", "mike", "november",
             "oscar", "papa", "quebec", "romeo", "sierra", "tango", "uniform",
             "victor", "whiskey", "xray", "yankee", "zulu", "zero", "wun",
             "too", "tree", "fower", "five", "six", "seven", "ait", "niner"]
    return '%s-%s' % (random.choice(words), random.choice(words))


hg_reset = 'hg st --no-status --unknown --print0 --color false | ' \
           'xargs -0 rm --force && ' \
           'hg up --clean'


class App:

    def __init__(self, name, repository, paste_ini):
        self.name = name
        self.repository = repository
        self.paste_ini = paste_ini
        self._folder = None
        self._overlord = None

    @property
    def folder(self):
        if self._folder is None:
            self._folder = os.path.join(self.conf.root, self.name)
        return self._folder

    @property
    def overlord(self):
        if self._overlord is None:
            self._overlord = self.conf.uwsgi.Overlord(self.name)
        return self._overlord

    def zerglings(self):
        return self.overlord.zerglings()

    def zergling(self, name):
        return self.overlord.zergling(name)

    def appling(self, name):
        return AppLing(self, name)

    def initialize(self):
        try:
            os.makedirs(self.folder)
        except OSError as e:
            raise Exception('Cannot initialize folder of %s: %s' %
                            (self.name, str(e)))
        try:
            self.overlord.stop()
        except NotRunning:
            pass
        self.cleanup()
        self.overlord.regenini()
        self.overlord.start()

    def mkling(self, name=None):
        if not name:
            name = mkname()
        log.info('Creating %s/%s' % (self.name, name))
        appling = AppLing(self, name)
        appling.initialize()
        return appling

    def cleanup(self):
        suffix = 0
        running_zerglings = []
        for zergling in self.overlord.zerglings():
            if zergling.is_running() or zergling.is_starting():
                running_zerglings.append(zergling.name)
                continue
            zergling.delete()
            folder = os.path.join(self.folder, zergling.name)
            if not os.path.isdir(folder):
                continue
            while True:
                newname = '_unused_%d' % suffix
                try:
                    os.rename(folder, os.path.join(self.folder, newname))
                    break
                except OSError:
                    suffix += 1
        for folder_name in os.listdir(self.folder):
            folder = os.path.join(self.folder, folder_name)
            if not os.path.isdir(folder):
                # not a folder -> delete
                shutil.rmtree(folder)
                continue
            if folder_name.startswith('_unused_'):
                # recycled folder -> keep
                continue
            if folder_name in running_zerglings:
                # running process -> keep
                continue
            # none of the above -> delete
            shutil.rmtree(folder)


class AppLing:

    def __init__(self, app, name):
        self.app = app
        self.name = name
        self.folder = os.path.join(app.folder, name)
        self._zergling = None

    @property
    def zergling(self):
        if self._zergling is None:
            self._zergling = self.app.overlord.zergling(self.name)
        return self._zergling

    def update(self):
        log.info('Updating %s' % self)
        stdout = sys.stdout
        proc = Popen(['hg', 'pull'],
                     cwd=self.folder, stdout=stdout, stderr=PIPE)
        _, err = proc.communicate()
        if proc.returncode:
            raise Exception('Error pulling %s:\n%s' %
                            (self, str(err, 'UTF-8')))
        proc = Popen(['hg', 'update', '--clean'],
                     cwd=self.folder, stdout=stdout, stderr=PIPE)
        _, err = proc.communicate()
        if proc.returncode:
            raise Exception('Error updating %s:\n%s' %
                            (self, str(err, 'UTF-8')))

    def start(self, *, deactivate_others=False):
        log.info('Starting %s' % self)
        venvpath = os.path.join(self.folder, '.venv')
        self.zergling.regenini(virtualenv=venvpath)
        self.zergling.start(quiet=True)
        if not deactivate_others:
            return
        while self.zergling.is_starting():
            time.sleep(0.1)
        if not self.zergling.is_running():
            raise Exception('Instance did not start')
        for zergling in self.app.zerglings():
            if zergling.name == self.name:
                continue
            try:
                zergling.stop()
            except NotRunning:
                pass

    def __str__(self):
        return '<AppLing %s/%s>' % (self.app.name, self.name)

    def initialize(self):
        deploy = self.app.conf
        self._zergling = deploy.uwsgi.Zergling(
            self.app.overlord, self.name,
            os.path.join(self.folder, self.app.paste_ini))
        self._init_folder()
        self._init_venv()
        logpath = os.path.join(self.folder, 'zergling.log')
        os.unlink(logpath)
        os.symlink(self.zergling.logfile, logpath)

    def _init_venv(self):
        venvpath = os.path.join(self.folder, '.venv')
        if not os.path.exists(venvpath):
            venv.create(venvpath)
        proc = Popen([os.path.join('.venv', 'bin', 'python'),
                      'setup.py', 'install'],
                     cwd=self.folder, stdout=sys.stdout, stderr=PIPE)
        _, err = proc.communicate()
        if proc.returncode:
            raise Exception('Error installing %s:\n%s' %
                            (self, str(err, 'UTF-8')))
        self.zergling.regenini(virtualenv=venvpath)

    def _init_folder(self):
        for folder_name in os.listdir(self.app.folder):
            folder = os.path.join(self.app.folder, folder_name)
            if not os.path.isdir(folder):
                continue
            if not folder_name.startswith('_unused_'):
                continue
            os.rename(folder, self.folder)
            proc = Popen(hg_reset, shell=True, cwd=self.folder,
                         stdout=sys.stdout, stderr=PIPE)
            out, err = proc.communicate()
            if proc.returncode:
                log.warn('Error cleaning up folder %s. Deleting.' %
                         folder_name)
                shutil.rmtree(self.folder)
                continue
            return True
        self._clone()
        return False

    def _clone(self):
        proc = Popen(['hg', 'clone', self.repository, self.name],
                     cwd=self.folder, stdout=sys.stdout, stderr=PIPE)
        _, err = proc.communicate()
        if proc.returncode:
            log.error(err)
            raise Exception('Error cloning %s:\n%s' % (self, err))
