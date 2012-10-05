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

def write_distro_specific_manifest(manifest_file, vcs_type, vcs_url, api_homepage):
    m_yaml = {}
    if os.path.isfile(manifest_file):
        with open(manifest_file, 'r') as f:
            m_yaml = yaml.load(f)

    m_yaml['api_documentation'] = api_homepage
    #TODO fill this in properly
    m_yaml['depends_on'] = []
    m_yaml['vcs'] = vcs_type
    m_yaml['vcs_url'] = vcs_url

    with open(manifest_file, 'w+') as f:
        yaml.safe_dump(m_yaml, f, default_flow_style=False)

def get_stack_package_paths(stack_folder):
    #TODO: This is a hack, in the chroot, the default python path does not
    #include the directory to which catkin installs
    sys.path.append("/usr/lib/pymodules/python2.7/")
    from catkin_pkg import packages as catkin_packages
    import rospkg

    location_cache = {}
    packages = []

    #find dry packages
    packages.extend([os.path.abspath(location_cache[pkg]) \
                     for pkg in rospkg.list_by_path(rospkg.MANIFEST_FILE, stack_folder, location_cache)])
    #find wet packages
    packages.extend([os.path.abspath(os.path.join(stack_folder, pkg_path)) \
                     for pkg_path in catkin_packages.find_package_paths(stack_folder)])

    #Remove any duplicates
    return list(set(packages))

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

    #svn encodes the version in the url
    if not 'version' in conf:
        rosinstall = yaml.dump([{conf['type']: {'local-name': stack, 'uri': conf['url']}}], default_style=False)
    else:
        rosinstall = yaml.dump([{conf['type']: {'local-name': stack, 'uri': conf['url'], 'version': conf['version']}}], default_style=False)

    print "Rosinstall for stack %s:\n%s"%(stack, rosinstall)
    with open(workspace+"/stack.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Created rosinstall file for stack %s, installing stack..."%stack
    #TODO Figure out why rosinstall insists on having ROS available when called with nobuild, but not catkin
    call("rosinstall %s %s/stack.rosinstall --nobuild --catkin" % (docspace, workspace))

    stack_path = os.path.abspath("%s/%s" % (docspace, stack))
    print "Stack path %s" % stack_path
    package_paths = get_stack_package_paths(stack_path)
    packages = [os.path.basename(p) for p in package_paths]
    print "Running documentation generation on\npackages: %s\npaths: %s" % (packages, package_paths)

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
    for package, package_path in zip(packages, package_paths):
        #Build a tagfile list from dependencies for use by rosdoc
        build_tagfile(apt_deps, tags_db, 'rosdoc_tags.yaml', deb_name, package)

        relative_doc_path = "%s/doc/%s/api/%s" % (docspace, ros_distro, package)
        pkg_doc_path = os.path.abspath(relative_doc_path)
        relative_tags_path = "%s/api/%s/tags/%s.tag" % (ros_distro, package, package)
        tags_path = os.path.abspath("%s/doc/%s" % (docspace, relative_tags_path))
        print "Documenting %s [%s]..." % (package, package_path)
        #Generate the command we'll use to document the stack
        command = ['bash', '-c', 'source /opt/ros/%s/setup.bash \
                   && export ROS_PACKAGE_PATH=%s:$ROS_PACKAGE_PATH \
                   && rosdoc_lite %s -o %s -g %s -t rosdoc_tags.yaml' \
                   %(ros_distro, stack_path, package_path, pkg_doc_path, tags_path) ]
        #proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        proc = subprocess.Popen(command)
        proc.communicate()

        #Some doc runs won't generate tag files, so we need to check if they
        #exist before adding them to the list
        homepage = 'http://ros.org/rosdoclite'
        if(os.path.exists(tags_path)):
            stack_tags.append({'location':'%s/%s'%(homepage, relative_tags_path), 
                                   'docs_url':'../../../api/%s/html'%(package), 
                                   'package':'%s'%package})

        #We also need to add information to each package manifest that we only
        #have availalbe in this script like vcs location and type
        write_distro_specific_manifest(os.path.join(pkg_doc_path, 'manifest.yaml'),
                                       conf['type'], conf['url'], "%s/%s" %(homepage, relative_doc_path))

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
    workspace = 'workspace'
    docspace = 'docspace'
    document_stack(workspace, docspace, ros_distro, stack, 'precise', 'amd64')


if __name__ == '__main__':
    main()
