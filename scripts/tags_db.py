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
        #command = ['bash', '-c', 'eval `ssh-agent` \
        #           && ssh-add %s/buildfarm/scripts/ssh_keys/id_rsa \
        #           && export GIT_SSH="%s/buildfarm/scripts/git_ssh" \
        #           && git clone git@github.com:eitanme/rosdoc_tag_index.git %s' \
        #           %(workspace, workspace, self.path) ]

        command = ['bash', '-c', 'export GIT_SSH="%s/buildfarm/scripts/git_ssh" \
                   && git clone git@github.com:eitanme/rosdoc_tag_index.git %s' \
                   %(workspace, self.path) ]

        proc = subprocess.Popen(command)
        proc.communicate()
        #call("eval `ssh-agent`")
        #call("ssh-add %s/buildfarm/scripts/ssh_keys/id_rsa" % workspace)
        #call("git clone git@github.com:eitanme/rosdoc_tag_index.git %s" % self.path)

    #Get all the tag locations for a list of stacks
    def get_stack_tags(self):
        tags = {}
        with open(os.path.join(self.path, "%s.yaml" % self.distro_name), 'r') as f:
            tags = yaml.load(f)

        return tags or {}

    #Write new tag locations for a list of stacks
    def write_stack_tags(self, current_tags):
        with open(os.path.join(self.path, "%s.yaml" % self.distro_name), 'w') as f:
            yaml.dump(current_tags, f)

        old_dir = os.getcwd()
        os.chdir(self.path)
        print "Commiting changes to tags list...."
        command = ['git', 'commit', '-a', '-m', 'Updating tags list for %s' % (self.distro_name)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)

        command = ['bash', '-c', 'export GIT_SSH="%s/buildfarm/scripts/git_ssh" \
                   && git pull origin master \
                   && git push origin master' \
                   %(self.workspace) ]

        proc = subprocess.Popen(command)
        proc.communicate()
        os.chdir(old_dir)

    #Get all the tag locations for a list of packages
    def get_reverse_deps(self):
        with open(os.path.join(self.path, "%s-deps.yaml" % self.distro_name), 'r') as f:
            deps = yaml.load(f)

        return deps or {}

    #Write new reverse deps for a list of packages
    def write_reverse_deps(self, deps):
        with open(os.path.join(self.path, "%s-deps.yaml" % self.distro_name), 'w') as f:
            yaml.dump(deps, f)

        old_dir = os.getcwd()
        os.chdir(self.path)
        print "Commiting changes to deps list...."
        command = ['git', 'commit', '-a', '-m', 'Updating deps list for %s' % (self.distro_name)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)

        command = ['bash', '-c', 'export GIT_SSH="%s/buildfarm/scripts/git_ssh" \
                   && git pull origin master \
                   && git push origin master' \
                   %(self.workspace) ]

        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.communicate()
        os.chdir(old_dir)


