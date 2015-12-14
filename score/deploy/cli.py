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


import os
from subprocess import Popen, PIPE

import click
import score.init
import score.uwsgi
from score.uwsgi.cli import zergling_status
import time

import score.deploy
from ._app import NoSuchAppling, phonetics


def appling_name(app_alias):
    if len(app_alias) > 2:
        return app_alias
    return '%s-%s' % (phonetics[app_alias[0]], phonetics[app_alias[1]])


def get_appling(ctx, alias):
    parts = alias.split('/')
    if len(parts) == 2:
        app = ctx.deploy.apps[parts[0]]
        return app.appling(appling_name(parts[1]))
    found = []
    for app in ctx.deploy.apps:
        try:
            appling = ctx.deploy.apps[app].appling(appling_name(parts[0]))
            found.append(appling)
        except NoSuchAppling:
            pass
    if not found:
        raise click.ClickException('Appling %s not found' % appling)
    if len(found) > 2:
        raise click.ClickException('Multiple applings with alias %s found:\n  -'
                                   % (alias, '\n  -'.join(found)))
    return found[0]


@click.group()
@click.argument('conf', type=click.Path(file_okay=True, dir_okay=False))
@click.pass_context
def main(ctx, conf):
    """
    Manages deployment processes.
    """
    ctx.obj = score.init.init_from_file(conf)


@main.command('init')
@click.option('-d', '--debug', is_flag=True, default=False)
@click.pass_context
def init(ctx, debug):
    """
    First-Time initializer
    """
    for appname in ctx.obj.deploy.apps:
        ctx.obj.deploy.apps[appname].initialize()


@main.command('cleanup')
@click.argument('app', required=False)
@click.pass_context
def cleanup(ctx, app=None):
    if app:
        app = ctx.obj.deploy.apps[app]
        app.cleanup()
        return
    for app in ctx.obj.deploy.apps:
        app = ctx.obj.deploy.apps[app]
        app.cleanup()


@main.command('status')
@click.pass_context
def status(ctx):
    """
    Status info on deployment
    """
    for name in ctx.obj.deploy.apps:
        app = ctx.obj.deploy.apps[name]
        print(name)
        for zergling in sorted(app.zerglings(), key=lambda z: z.name):
            status = []
            folder = os.path.join(app.folder, zergling.name)
            proc = Popen(['hg', 'status',
                          '--modified', '--added', '--removed',
                          '--deleted', '--no-status'],
                         cwd=folder, stdout=PIPE, stderr=PIPE)
            out, err = proc.communicate()
            if proc.returncode:
                status.append(err)
            else:
                if out:
                    status.append('modified')
                status += zergling_status(zergling)
            if status:
                status = ' (%s)' % ', '.join(status)
            else:
                status = ''
            print('    %s%s' % (zergling.name, status))


@main.command('mkling')
@click.argument('app')
@click.pass_context
def mkling(ctx, app):
    """
    Creates a new appling
    """
    app = ctx.obj.deploy.apps[app]
    app.mkling()


@main.command('update')
@click.option('-f', '--force', is_flag=True, default=False)
@click.argument('alias')
@click.pass_context
def update(ctx, alias, force):
    """
    Updates and an appling's repository
    """
    appling = get_appling(ctx.obj, alias)
    if not force and appling.zergling.is_running():
        raise click.ClickException(
            'Zergling running, pass --force to update anyway.')
    appling.update()
    if appling.zergling.is_running():
        appling.reload()


@main.command('start')
@click.option('-m', '--multi-mode', is_flag=True, default=False)
@click.argument('alias')
@click.pass_context
def start(ctx, alias, multi_mode):
    """
    Starts a dormant appling
    """
    appling = get_appling(ctx.obj, alias)
    appling.start(pause_others=not multi_mode)


@main.command('pause')
@click.argument('alias')
@click.pass_context
def pause(ctx, alias):
    """
    Pauses a running appling
    """
    appling = get_appling(ctx.obj, alias)
    try:
        appling.zergling.pause()
    except score.uwsgi.AlreadyPaused:
        pass


@main.command('stop')
@click.argument('alias')
@click.pass_context
def stop(ctx, alias):
    appling = get_appling(ctx.obj, alias)
    appling.stop()


@main.command('reload')
@click.argument('alias')
@click.pass_context
def reload(ctx, alias):
    """
    Reloads an appling
    """
    appling = get_appling(ctx.obj, alias)
    zergling = appling.zergling
    zergling.reload()
    while zergling.is_starting():
        time.sleep(0.1)
    if not zergling.is_running():
        raise click.ClickException('Instance did not start.')


@main.command('log')
@click.argument('alias')
@click.pass_context
def log(ctx, alias):
    """
    Prints log file of appling
    """
    appling = get_appling(ctx.obj, alias)
    with open(appling.zergling.logfile) as file:
        chunk = file.read(1024)
        while chunk:
            print(chunk)
            chunk = file.read(1024)
