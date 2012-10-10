# Software License Agreement (BSD License)
#
# Copyright (c) 2008, Willow Garage, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of Willow Garage, Inc. nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import yaml
import urllib
import os
import shutil
from common import *
import subprocess

class TagsDb(object):
    def __init__(self, distro_name, workspace):
        self.workspace = workspace
        self.distro_name = distro_name
        self.path  = os.path.abspath(os.path.join(self.workspace, 'rosdoc_tag_index'))
        if os.path.exists(self.path):
            shutil.rmtree(self.path)

        command = ['bash', '-c', 'export GIT_SSH="%s/buildfarm/scripts/git_ssh" \
                   && git clone git@github.com:eitanme/rosdoc_tag_index.git %s' \
                   %(workspace, self.path) ]

        proc = subprocess.Popen(command)
        proc.communicate()

        with open(os.path.join(self.path, "%s.yaml" % self.distro_name), 'r') as f:
            self.tags = yaml.load(f)
            self.tags = self.tags or {}

        with open(os.path.join(self.path, "%s-deps.yaml" % self.distro_name), 'r') as f:
            self.forward_deps = yaml.load(f)
            self.forward_deps = self.forward_deps or {}

        self.build_reverse_deps()

    def build_reverse_deps(self):
        #Build reverse dependencies
        self.reverse_deps = {}
        for stack, deps in self.forward_deps.iteritems():
            for dep in deps:
                self.reverse_deps.setdefault(dep, []).append(stack)

    def has_tags(self, key):
        return key in self.tags

    def get_tags(self, key):
        return self.tags[key]

    def set_tags(self, key, tags):
        self.tags[key] = tags

    def has_reverse_deps(self, key):
        return key in self.reverse_deps

    def get_reverse_deps(self, key):
        return self.reverse_deps[key]

    def add_forward_deps(self, key, deps):
        self.forward_deps[key] = deps
        self.build_reverse_deps()

    #Write new tag locations for a list of stacks
    def commit_db(self):
        with open(os.path.join(self.path, "%s.yaml" % self.distro_name), 'w') as f:
            yaml.dump(self.tags, f)

        with open(os.path.join(self.path, "%s-deps.yaml" % self.distro_name), 'w') as f:
            yaml.dump(self.forward_deps, f)

        old_dir = os.getcwd()
        os.chdir(self.path)
        print "Commiting changes to tags and deps lists...."
        command = ['git', 'commit', '-a', '-m', 'Updating tags and deps lists for %s' % (self.distro_name)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)

        env = os.environ
        env['GIT_SSH'] = "%s/buildfarm/scripts/git_ssh" % self.workspace
        call("git fetch origin", env)
        call("git merge origin/master", env)
        call("git push origin master", env)

        os.chdir(old_dir)
