#!/usr/bin/env python
import os
import sys
import rosdistro
import yaml
import subprocess
import urllib
import datetime
from xml.etree.ElementTree import ElementTree



def call(command, envir=None):
    print "Executing command '%s'"%command
    helper = subprocess.Popen(command.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, env=envir)
    res, err = helper.communicate()
    print str(res)
    print str(err)
    if helper.returncode != 0:
        msg = "Failed to execute command '%s'"%command
        print "/!\  %s"%msg
        raise BuildException(msg)
    return res


def get_dependencies(stack_folder):
    # get the stack dependencies
    print "Get the dependencies of stack in folder %s"%stack_folder
    try:
        print "Parsing stack.xml..."
        root = ElementTree(None, os.path.join(stack_folder, 'stack.xml'))
        stack_dependencies = [d.text for d in root.findall('depends')]
        system_dependencies = [d.text for d in root.findall('build_depends')]
        print "Stack Dependencies: %s"%(' '.join(stack_dependencies))
        print "System Dependencies: %s"%(' '.join(system_dependencies))
        return stack_dependencies + system_dependencies
    except Exception, ex:
        raise BuildException("Failed to parse stack.xml of stack in folder %s"%stack_folder)


    
class RosDep:
    def __init__(self, ros_distro):
        self.r2a = {}
        self.a2r = {}
        self.env = os.environ
        self.env['ROS_DISTRO'] = ros_distro

        # Initialize rosdep database
        print "Ininitalize rosdep database"
        call("apt-get install --yes lsb-release python-rosdep")
        call("rosdep init", self.env)
        call("rosdep update", self.env)

    def to_apt(self, r):
        if r in self.r2a:
            return self.r2a[r]
        else:
            a = call("rosdep resolve %s"%r, self.env).split('\n')[1]
            print "Rosdep %s resolved into %s"%(r, a)
            self.r2a[r] = a
            self.a2r[a] = r
            return a

    def to_stack(self, a):
        if not a in self.a2r:
            print "%s not in apt-to-rosdep cache"%a
        return self.a2r[a]



class BuildException(Exception):
    def __init__(self, msg):
        self.msg = msg

def main():
    print
    print
    print
    print "============================================================"
    print "==== Begin ci devel script.    Ignore the output above ====="
    print "============================================================"
    print
    print
    print

    if len(sys.argv) != 3:
        print "Usage: %s ros_distro stack_name"%sys.argv[0]
        raise BuildException("Wrong number of parameters for ci devel script")
    else:
        ros_distro = sys.argv[1]
        stack = sys.argv[2]
        print "Working on distro %s and stacks %s"%(ros_distro, stack)

    workspace = os.environ['WORKSPACE']
    buildspace = os.path.join(workspace, 'tmp', str(datetime.datetime.now()).replace(' ','_'))
    stackbuildspace = os.path.join(buildspace, 'build_stack')
    os.makedirs(buildspace)

    # Add ros to apt
    print "Add ros to apt sources"
    with open('/etc/apt/sources.list.d/ros-latest.list', 'w') as f:
        f.write("deb http://packages.ros.org/ros-shadow-fixed/ubuntu %s main"%os.environ['OS_PLATFORM'])
    call("wget http://packages.ros.org/ros.key -O %s/ros.key"%workspace)
    call("apt-key add %s/ros.key"%workspace)
    call("apt-get update")

    # install vcs tools
    print "Installing vcs tools"
    call("apt-get install mercurial --yes")
    #call("apt-get install git --yes")   
    call("apt-get install subversion --yes")

    # Create rosdep object
    print "Create rosdep object"
    rosdep = RosDep(ros_distro)

    # parse the devel distro file
    print "Parsing devel yaml file for %s"%ros_distro
    f = urllib.urlopen('https://raw.github.com/ros/rosdistro/master/releases/%s-devel.yaml'%ros_distro)
    devel = yaml.load(f.read())['repositories']

    # download the stacks from source
    print "Downloading stack %s"%stack
    if not stack in devel.keys():
        raise BuildException("Stack %s does not exist in devel distro file"%stack)
    conf = devel[stack]
    rosinstall = yaml.dump([{conf['type']: {'local-name': stack, 'uri': conf['url'], 'version': conf['version']}}], default_style=False)
    print "Rosinstall for stack %s:\n %s"%(stack, rosinstall)
    with open(workspace+"/stack.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Create rosinstall file for stack %s"%stack
    call("rosinstall %s %s/stack.rosinstall --catkin"%(buildspace, workspace))

    # get the stack dependencies
    print "Get all stack dependencies"
    dependencies = get_dependencies(os.path.join(buildspace, stack))
    if len(dependencies) > 0:
        print "Install all dependencies of stacks: %s"%(', '.join(dependencies))
        call("apt-get install %s --yes"%(' '.join([rosdep.to_apt(r) for r in dependencies])))

    raise
    # get the ros build environment
    print "Retrieve the ROS build environment by sourcing /opt/ros/%s/setup.bask"%ros_distro
    build_env = {}
    command = ['bash', '-c', 'source /opt/ros/%s/setup.bash && env'%ros_distro]
    proc = subprocess.Popen(command, stdout = subprocess.PIPE)
    for line in proc.stdout:
        (key, _, value) = line.partition("=")
        build_env[key] = value
    proc.communicate()

    # build stacks
    print "Configure, build and test stacks"
    os.makedirs(stackbuildspace)
    os.chdir(stackbuildspace)
    call("cmake ..", build_env)
    call("make", build_env)
    call("make -k test", build_env)

    # get stack depends-on list
    print "Get list of stacks that depend on %s"%stack
    apt = AptDepends(os.environ['OS_PLATFORM'], os.environ['ARCH'])
    depends_on_apt = []
    depends_on = []
    for stack_apt in stacks_apt:
        for d in apt.depends_on(stack_apt):
            if not d in depends_on_apt and not d in stacks_apt and d in distro_apt:
                depends_on_apt.append(d)
                depends_on.append(rosdep.to_stack(d))
    print "Depends_on list for stacks: %s"%(', '.join(depends_on))

    # install depends_on stacks from source
    rosinstall = yaml.dump([{'git': {'local-name': stack, 'uri': distro._repoinfo[stack].url, 'version': 'master'}} for stack in depends_on], default_style=False)
    print "Rosinstall for depends_on:\n %s"%rosinstall
    with open(workspace+"/depends_on.rosinstall", 'w') as f:
        f.write(rosinstall)
    print "Create rosinstall file for depends on"
    call("rosinstall --catkin %s %s/depends_on.rosinstall"%(buildspace, workspace))

    # install all stack and system dependencies of the depends_on list
    print "Install all dependencies of the depends_on list"
    res = []
    for s in depends_on:
        dep = get_dependencies(os.path.join(buildspace, s))
        for d in dep:
            if not d in res:
                res.append(d)

    res_apt = []
    for d_apt in [rosdep.to_apt(d) for d in res]:
        if not d_apt in stacks_apt and not d_apt in depends_on_apt:
            res_apt.append(d_apt)
    print "Dependencies of depends_on list are %s"%(', '.join(res_apt))
    call("apt-get install --yes %s"%(' '.join(res_apt)))


    # build depend_on stacks
    print "Configure, build and test depend_on stacks"
    os.makedirs(dependbuildspace)
    os.chdir(dependbuildspace)
    call("cmake ..", build_env)
    call("make", build_env)
    call("make -k test", build_env)



if __name__ == '__main__':
    # global try
    try:
        main()
        sys.exit(0)

    # global catch
    except BuildException as ex:
        print ex.msg

    else:
        print "Prerelease Test Failed. Check out the console output above for details."

    print
    print
    print
    print "============================================================"
    print "==== End of prerelease script. Ignore the output below ====="
    print "============================================================"
    print
    print
    print

    sys.exit(-1)
