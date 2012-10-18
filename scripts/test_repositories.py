#!/usr/bin/env python
import os
import sys
import yaml
import subprocess
import urllib
import string
import datetime
import fnmatch
import shutil
import optparse
from xml.etree.ElementTree import ElementTree
from common import *
from time import sleep



def test_repositories(ros_distro, repositories, workspace, use_devel_repo, test_depends_on):
    print "Testing on distro %s"%ros_distro    
    print "Testing repositories %s"%', '.join(repositories)
    if use_devel_repo:
        print "Testing from devel repo"
    else:
        print "Testing from release repo"
    if test_depends_on:
        print "Testing depends-on"
    else:
        print "Not testing depends on"


    # set directories
    tmpdir = os.path.join('tmp', 'test_repositories', get_timestamp())
    sourcespace = os.path.join(tmpdir, 'src')
    repositorybuildspace = os.path.join(tmpdir, 'build_repository')
    dependbuildspace = os.path.join(tmpdir, 'build_depend_on')
    os.makedirs(sourcespace)

    # Add ros to apt
    print "Add ros to apt sources"
    with open('/etc/apt/sources.list.d/ros-latest.list', 'w') as f:
        f.write("deb http://packages.ros.org/ros-shadow-fixed/ubuntu %s main"%os.environ['OS_PLATFORM'])
    call("wget http://packages.ros.org/ros.key -O %s/ros.key"%workspace)
    call("apt-key add %s/ros.key"%workspace)
    call("apt-get update")

    # install stuff we need
    print "Installing stuff we need for testing"
    call("apt-get install mercurial subversion python-catkin-pkg python-support cmake --yes")

    # parse the rosdistro file
    print "Parsing rosdistro file for %s"%ros_distro
    distro = RosDistro(ros_distro, prefetch_dependencies=test_depends_on, prefetch_upstream=False)
    devel = DevelDistro(ros_distro)
    for repository in repositories:
        print "Checking if repo %s exists in distr or devel file"%repository
        if not use_devel_repo and not repository in distro.repositories.keys():
            raise BuildException("Repository %s does not exist in Ros Distro"%repository)
        if use_devel_repo and not repository in devel.repositories.keys():
            raise BuildException("Repository %s does not exist in Devel Distro"%repository)

    # Create rosdep object
    print "Create rosdep object"
    rosdep = RosDepResolver(ros_distro)

    # download the repositories from source
    print "Downloading all repositories"
    rosinstall = ""
    for repository in repositories:
        if use_devel_repo:
            print "Using devel distro file to download repositories"
            rosinstall += devel.repositories[repository].get_rosinstall()
        else:
            print "Using release distro file to download repositories"
            rosinstall += distro.repositories[repository].get_rosinstall_latest()
    print "rosinstall file for all repositories: \n %s"%rosinstall
    with open(workspace+"/repository.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Create rosinstall file for repositories %s"%(', '.join(repositories))
    call("rosinstall %s %s/repository.rosinstall --catkin"%(sourcespace, workspace))

    # get the repositories build dependencies
    print "Get build dependencies of repositories"
    build_dependencies = get_dependencies(sourcespace, build_depends=True, test_depends=False)
    print "Install build dependencies of repositories: %s"%(', '.join(build_dependencies))
    apt_get_install(build_dependencies, rosdep)

    # replace the CMakeLists.txt file for repositories that use catkin
    print "Removing the CMakeLists.txt file generated by rosinstall"
    os.remove(os.path.join(sourcespace, 'CMakeLists.txt'))
    os.makedirs(repositorybuildspace)
    os.chdir(repositorybuildspace)
    print "Create a new CMakeLists.txt file using catkin"
    ros_env = get_ros_env('/opt/ros/%s/setup.bash'%ros_distro)
    call("catkin_init_workspace %s"%sourcespace, ros_env)
    print ros_env
    call("cmake ../src/", ros_env)        
    ros_env_repo = get_ros_env(os.path.join(repositorybuildspace, 'buildspace/setup.bash'))

    # build repositories
    print "Build repositories"
    call("make", ros_env)

    # get the repositories test dependencies
    print "Get test dependencies of repositories"
    test_dependencies = get_dependencies(sourcespace, build_depends=False, test_depends=True)
    print "Install test dependencies of repositories: %s"%(', '.join(test_dependencies))
    apt_get_install(test_dependencies, rosdep)

    # run tests
    print "Test repositories"
    call("make run_tests", ros_env)

    # see if we need to do more work or not
    if not test_depends_on:
        print "We're not testing the depends-on repositories"
        copy_test_results(workspace, repositorybuildspace)
        return

    # get repository depends-on list
    print "Get list of wet repositories that build-depend on %s"%repository
    depends_on = []
    for d in distro.depends_on(repositories, 'build'):
        if not d in depends_on and not d in repositories:
            depends_on.append(d)
    print "Build depends_on list for repositories: %s"%(', '.join(depends_on))
    if len(depends_on) == 0:
        copy_test_results(workspace, repositorybuildspace)
        print "No wet groovy repositories depend on our repositories. Test finished here"
        return

    # install depends_on repositories from source
    rosinstall = ""
    for d in depends_on:
        rosinstall += distro.packages[d].get_rosinstall_release()
    print "Rosinstall for depends_on:\n %s"%rosinstall
    with open(workspace+"/depends_on.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Created rosinstall file for depends on"

    # install all repository and system dependencies of the depends_on list
    print "Install all build_depends_on from source"        
    call("rosinstall --catkin %s %s/depends_on.rosinstall"%(sourcespace, workspace))

    # get build and test dependencies of depends_on list
    build_dep = []
    for d in get_dependencies(sourcespace, build_depends=True, test_depends=False):
        if not d in build_dep and not d in depends_on and not d in repositories:
            build_dep.append(d)
    print "Build dependencies of depends_on list are %s"%(', '.join(build_dep))
    test_dep = []
    for d in get_dependencies(sourcespace, build_depends=False, test_depends=True):
        if not d in test_dep and not d in depends_on and not d in repositories:
            test_dep.append(d)
    print "Test dependencies of depends_on list are %s"%(', '.join(test_dep))


    # install build dependencies
    print "Install all build dependencies of the depends_on list"
    apt_get_install(build_dep, rosdep)

    # replace the CMakeLists.txt file again
    print "Removing the CMakeLists.txt file generated by rosinstall"
    os.remove(os.path.join(sourcespace, 'CMakeLists.txt'))
    os.makedirs(dependbuildspace)
    os.chdir(dependbuildspace)
    print "Create a new CMakeLists.txt file using catkin"
    call("catkin_init_workspace %s"%sourcespace, ros_env)
    call("ls -l /opt/ros/groovy/share/genmsg/manifest.xml")
    print ros_env
    call("cmake ../src/", ros_env)        
    ros_env_depends_on = get_ros_env(os.path.join(dependbuildspace, 'buildspace/setup.bash'))

    # build repositories
    print "Build depends-on repositories"
    call("make", ros_env)

    # install test dependencies
    print "Install all test dependencies of the depends_on list"
    apt_get_install(test_dep, rosdep)

    # test repositories
    print "Test depends-on repositories"
    call("make run_tests", ros_env)
    copy_test_results(workspace, dependbuildspace)




def main():
    parser = optparse.OptionParser()
    parser.add_option("--devel", action="store_true", default=False)
    parser.add_option("--depends-on", action="store_true", default=False)
    (options, args) = parser.parse_args()

    if len(args) <= 1:
        print "Usage: %s ros_distro repository_name"%sys.argv[0]
        raise BuildException("Wrong number of parameters for test_repositories script")

    ros_distro = args[0]
    repositories = args[1:]
    workspace = os.environ['WORKSPACE']    
    print "Running test_repositories test on distro %s and repositories %s"%(ros_distro, ', '.join(repositories))

    test_repositories(ros_distro, repositories, workspace, options.devel, options.depends-on)



if __name__ == '__main__':
    # global try
    try:
        main()
        print "test_repositories script finished cleanly"

    # global catch
    except BuildException as ex:
        print ex.msg

    except Exception as ex:
        print "test_repositories script failed. Check out the console output above for details."
        raise ex
