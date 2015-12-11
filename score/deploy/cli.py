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


def parse_alias(alias):
    return alias.split('/')


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
    appname, lingname = parse_alias(alias)
    app = ctx.obj.deploy.apps[appname]
    appling = app.appling(lingname)
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
    appname, lingname = parse_alias(alias)
    app = ctx.obj.deploy.apps[appname]
    appling = app.appling(lingname)
    appling.start(pause_others=not multi_mode)


@main.command('stop')
@click.argument('alias')
@click.pass_context
def stop(ctx, alias):
    appname, lingname = parse_alias(alias)
    app = ctx.obj.deploy.apps[appname]
    appling = app.appling(lingname)
    appling.stop()


@main.command('reload')
@click.argument('alias')
@click.pass_context
def reload(ctx, alias):
    """
    Reloads an appling
    """
    appname, lingname = parse_alias(alias)
    app = ctx.obj.deploy.apps[appname]
    appling = app.appling(lingname)
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
    appname, lingname = parse_alias(alias)
    app = ctx.obj.deploy.apps[appname]
    with open(app.zergling(lingname).logfile) as file:
        chunk = file.read(1024)
        while chunk:
            print(chunk)
            chunk = file.read(1024)
