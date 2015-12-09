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


from score.init import ConfigurationError, ConfiguredModule
import os
from ._app import App


defaults = {
}


def init(confdict, uwsgi_conf):
    conf = defaults.copy()
    conf.update(confdict)
    if 'rootdir' not in conf:
        raise ConfigurationError(__package__, 'No root folder provided')
    if not os.path.isdir(conf['rootdir']):
        raise ConfigurationError(__package__,
                                 'Provided root folder does not exist:\n' +
                                 conf['rootdir'])
    apps = {}
    for key in conf:
        if not key.endswith('.hg'):
            continue
        name = key[:-3]
        inikey = '%s.ini' % name
        if inikey not in conf:
            raise ConfigurationError(__package__,
                                     'No ini path provided for ' + name)
        apps[name] = App(name, conf[key], conf[inikey])
    return ConfiguredDeployModule(uwsgi_conf, conf['rootdir'], apps)


class ConfiguredDeployModule(ConfiguredModule):

    def __init__(self, uwsgi, root, apps):
        super().__init__(__package__)
        self.uwsgi = uwsgi
        self.root = root
        self._apps = apps
        for name in apps:
            apps[name].conf = self

    @property
    def apps(self):
        return dict(self._apps.items())
