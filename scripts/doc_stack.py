#!/usr/bin/env python
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
# Revision $Id: rosdoc 11469 2010-10-12 00:56:25Z kwc $

import urllib
import os
import sys
import yaml
import subprocess
import fnmatch
from common import *
from tags_db import *

def get_stack_packages(stack_folder):
    packages = []

    #Handle the case of a unary stack
    if os.path.isfile(os.path.join(stack_folder, 'manifest.xml')):
        packages.append(os.path.basename(stack_folder))
        #At this point, we don't need to search through subdirectories
        return packages

    #Get a list of all the directories in the stack folder
    #A folder is defined as a package if it contains a manifest.xml file
    print "Getting the packages that are a part of a given stack %s..." % stack_folder
    for root, dirnames, filenames in os.walk(stack_folder):
        if fnmatch.filter(filenames, 'manifest.xml'):
            packages.append(os.path.basename(root))

    return packages


#def get_stack_packages(stack_folder):
#    packages = []
#
#    #Handle the case of a unary stack
#    if os.path.isfile(os.path.join(stack_folder, 'manifest.xml')):
#        packages.append(os.path.basename(stack_folder))
#        #At this point, we don't need to search through subdirectories
#        return packages
#
#    #Get a list of all the directories in the stack folder
#    #A folder is defined as a package if it contains a manifest.xml file
#    print "Getting the packages that are a part of a given stack %s..." % stack_folder
#    subdirs = [name for name in os.listdir(stack_folder) if os.path.isdir(os.path.join(stack_folder, name))]
#    for subdir in subdirs:
#        if os.path.isfile(os.path.join(stack_folder, subdir, 'manifest.xml')):
#            packages.append(os.path.basename(subdir))
#    return packages

def build_tagfile(apt_deps, tags_db, rosdoc_tagfile, current_deb, current_package):
    #Get the relevant tags from the database
    apt_tags = tags_db.get_stack_tags()
    tags = []

    if apt_tags:
        for dep in apt_deps:
            if dep in apt_tags:
                #Make sure that we don't pass our own tagfile to ourself
                #bad things happen when we do this, we only need to perform
                #this check for our dep
                if dep == current_deb:
                    for tag in apt_tags[dep]:
                        if tag['package'] != current_package:
                            tags.append(tag)
                else:
                    tags.extend(apt_tags[dep])

    tags_file = file(rosdoc_tagfile, 'w')
    yaml.dump(tags, tags_file)

#As far as I know, the best way to check whether a stack is catkinized or not is to 
#download the current rosdistro for catkin and see if the name is in the rosdistro file
def is_catkin_stack(stack_name, ros_distro):
    f = urllib.urlopen('https://raw.github.com/ros/rosdistro/master/releases/%s.yaml'%ros_distro)
    catkin_repos = yaml.load(f.read())['repositories']
    return stack_name in catkin_repos

def get_stack_deb_name(stack_name, catkin_stack, ros_distro):
    if not catkin_stack:
        # Replacing underscores with dashes may not be sufficient, but I think
        # it is for the old deb stuff
        return "ros-%s-%s" % (ros_distro, stack_name.replace('_', '-'))
    else:
        ros_dep = RosDep(ros_distro)
        return ros_dep.to_apt(stack_name)

def document_stack(workspace, docspace, ros_distro, stack, platform, arch):
    print "Working on distro %s and stack %s" % (ros_distro, stack)
    print "Parsing doc file for %s" % ros_distro
    f = urllib.urlopen('https://raw.github.com/eitanme/rosdistro/master/releases/%s-doc.yaml'%ros_distro)
    repos = yaml.load(f.read())['repositories']

    print "Finding information for stack %s" % stack
    if not stack in repos.keys():
        raise Exception("Stack %s does not exist in %s rosdistro file" % (stack, ros_distro))

    conf = repos[stack]
    rosinstall = yaml.dump([{conf['type']: {'local-name': stack, 'uri': conf['url'], 'version': conf['version']}}], default_style=False)
    print "Rosinstall for stack %s:\n%s"%(stack, rosinstall)
    with open(workspace+"/stack.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Created rosinstall file for stack %s, installing stack..."%stack
    #TODO Figure out why rosinstall insists on having ROS available when called with nobuild, but not catkin
    call("rosinstall %s %s/stack.rosinstall --nobuild --catkin" % (docspace, workspace))

    stack_path = os.path.abspath("%s/%s" % (docspace, stack))
    print "Stack path %s" % stack_path
    packages = get_stack_packages(stack_path)
    print "Running documentation generation on packages %s" % packages

    #Check whether we're using a catkin stack or not
    catkin_stack = is_catkin_stack(stack, ros_distro)

    #Get the apt name of the current stack
    deb_name = get_stack_deb_name(stack, catkin_stack, ros_distro)

    apt = AptDepends(platform, arch)
    apt_deps = apt.depends(deb_name)
    apt_deps.append(deb_name)

    print "Installing all dependencies for %s" % stack
    if apt_deps:
        call("apt-get install %s --yes" % (' '.join(apt_deps)))
    print "Done installing dependencies"

    #Load information about existing tags
    tags_db = TagsDb(ros_distro, workspace)

    stack_tags = []
    for package in packages:
        #Build a tagfile list from dependencies for use by rosdoc
        build_tagfile(apt_deps, tags_db, 'rosdoc_tags.yaml', deb_name, package)

        html_path = os.path.abspath("%s/doc/%s/api/%s/html" % (docspace, ros_distro, package))
        #tags_path = os.path.abspath("%s/docs/tags/%s.tag" % (docspace, package))
        relative_tags_path = "%s/api/%s/tags/%s.tag" % (ros_distro, package, package)
        tags_path = os.path.abspath("%s/doc/%s" % (docspace, relative_tags_path))
        print "Documenting %s..." % package
        #Generate the command we'll use to document the stack
        command = ['bash', '-c', 'source /opt/ros/%s/setup.bash \
                   && export ROS_PACKAGE_PATH=%s:$ROS_PACKAGE_PATH \
                   && rosdoc_lite %s -o %s -g %s -t rosdoc_tags.yaml' \
                   %(ros_distro, stack_path, package, html_path, tags_path) ]
        #proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        proc = subprocess.Popen(command)
        proc.communicate()

        #Some doc runs won't generate tag files, so we need to check if they
        #exist before adding them to the list
        if(os.path.exists(tags_path)):
            stack_tags.append({'location':'http://ros.org/rosdoclite/%s'%relative_tags_path, 
                                   'docs_url':'../../../api/%s/html'%(package), 
                                   'package':'%s'%package})
        print "Done"

    doc_path = os.path.abspath("%s/doc/%s" % (docspace, ros_distro))

    #Copy the files to the appropriate place
    call("rsync -qr %s rosbuild@wgs32:/var/www/www.ros.org/html/rosdoclite" % (doc_path))

    #Write the new tags to the database
    tags_db.write_stack_tags(deb_name, stack_tags)

    #Tell jenkins that we've succeeded
    print "Preparing xml test results"
    try:
        os.makedirs(os.path.join(workspace, 'test_results'))
        print "Created test results directory"
    except:
        pass

    call("cp %s %s"%(os.path.join(workspace, 'buildfarm/templates/junit_dummy_ouput_template.xml'),
                     os.path.join(workspace, 'test_results/')))

def main():
    arguments = sys.argv[1:]
    ros_distro = arguments[0]
    stack = arguments[1]
    workspace = '/home/eitan/hidof/willow'
    docspace = 'docspace'
    document_stack(workspace, docspace, ros_distro, stack, 'precise', 'amd64')


if __name__ == '__main__':
    main()
