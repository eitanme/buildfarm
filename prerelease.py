#!/usr/bin/env python
import os
import sys
import rosdistro
import yaml
import subprocess
import urllib
from xml.etree.ElementTree import ElementTree


class AptDepends:
    def __init__(self, ubuntudistro, arch):
        url = urllib.urlopen('http://packages.ros.org/ros-shadow-fixed/ubuntu/dists/%s/main/binary-%s/Packages'%(ubuntudistro, arch))
        self.dep = {}
        package = None
        for l in url.read().split('\n'):
            if 'Package: ' in l:
                package = l.split('Package: ')[1]
            if 'Depends: ' in l:
                if not package:
                    raise BuildException("Found 'depends' but not 'package' while parsing the apt repository index file")
                self.dep[package] = [d.split(' ')[0] for d in (l.split('Depends: ')[1].split(', '))]
                package = None
        
    def depends1(self, package):
        return self.depends(package, one=True)

    def depends(self, package, res=[], one=False):
        if package in self.dep:
            for d in self.dep[package]:
                if not d in res:
                    res.append(d)
                if not one:
                    self.depends(d, res, one)
        return res
            
    def depends_on1(self, package):
        return self.depends_on(package, one=True)

    def depends_on(self, package, res=[], one=False):
        for p, dep in self.dep.iteritems():
            if package in dep:
                if not p in res:
                    res.append(p)
                if not one:
                    self.depends_on(p, res, one)
        return res
        




def call(command, envir=None):
    print "Executing command '%s'"%command
    helper = subprocess.Popen(command.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, env=envir)
    res, err = helper.communicate()
    print str(res)
    print str(err)
    if helper.returncode != 0:
        msg = "Failed to execute command '%s'"%command
        print "/!\  %s"%msg
        generate_xml(msg, str(res), str(err))
        raise BuildException(msg)
    return res


def rosdep_to_apt(rosdep):
    env = os.environ
    env['ROS_DISTRO'] = 'fuerte'
    apt = call("rosdep resolve %s"%rosdep, env).split('\n')[1]
    print "Rosdep %s resolved into %s"%(rosdep, apt)
    return apt


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

def generate_xml(msg, stdout, stderr):
    # open template xlm file
    with open('%s/buildfarm/junit_ouput_template.xml'%workspace) as f:
        result_xml = f.read()
    result_xml = result_xml.replace('@MSG@', msg)

    # write resulting file
    xml_file = '%s/xml_output/jenkins_failure.xml'%workspace
    ensure_dir(xml_file)
    with open(xml_file, 'w') as f:
        f.write(result_xml)


def get_dependencies(stack_folder):
    # get the stack dependencies
    print "Get the dependencies of stack in folder %s"%stack_folder
    try:
        print "Parsing stack.xml..."
        root = ElementTree(None, stack_folder + '/stack.xml')
        stack_dependencies = [d.text for d in root.findall('depends')]
        system_dependencies = [d.text for d in root.findall('build_depends')]
        print "Stack Dependencies: %s"%(' '.join(stack_dependencies))
        print "System Dependencies: %s"%(' '.join(system_dependencies))
        return stack_dependencies + system_dependencies
    except Exception, ex:
        raise BuildException("Failed to parse stack.xml of stack in folder %s"%stack_folder)


    
class BuildException(Exception):
    def __init__(self, msg):
        self.msg = msg



workspace = os.environ['WORKSPACE']

def main():
    print
    print "==========================================================================="
    print "======================== PRERELEASE SCRIPT ================================"
    print "==========================================================================="
    print

    if len(sys.argv) <= 2:
        print "Usage: %s ros_distro stack_name"%sys.argv[0]
        raise BuildException("Wrong number of parameters for prerelase script")
    else:
        ros_distro = sys.argv[1]
        stack = sys.argv[2]
        print "Working on distro %s and stack %s"%(ros_distro, stack)

    buildspace = workspace + '/tmp/'  # should become '/tmp/'
    envbuilder = 'source /opt/ros/%s/setup.bash'%ros_distro

    # Add ros to apt
    print "Add ros stuff to apt"
    with open('/etc/apt/sources.list.d/ros-latest.list', 'w') as f:
        f.write("deb http://packages.ros.org/ros/ubuntu %s main"%os.environ['OS_PLATFORM'])
    call("apt-get update")

    # Initialize rosdep database
    print "Ininitalize rosdep database"
    call("apt-get install --yes --force-yes lsb-release python-rosdep")
    call("rosdep init")
    call("rosdep update")

    # parse the rosdistro file
    print "Parsing rosdistro file for %s"%ros_distro
    distro = rosdistro.Rosdistro(ros_distro)
    stack_to_apt = {}
    for d in distro._repoinfo.keys():
        stack_to_apt[d] = rosdep_to_apt(d)
    apt_to_stack = {}
    for s, a in stack_to_apt.iteritems():
        apt_to_stack[a] = s

    # download the stack from source
    print "Downloading stack %s"%stack
    if not stack in distro._repoinfo.keys():
        print "Stack %s does not exist in Rosdistro"%stack
        return False
    with open(workspace+"/stack.rosinstall", 'w') as f:
        rosinstall = yaml.dump([{'git': {'local-name': stack, 'uri': distro._repoinfo[stack].url, 'version': 'master'}}], default_style=False)
        print "Rosinstall for stack %s:\n %s"%(stack, rosinstall)
        f.write(rosinstall)
    print "Create rosinstall file for stack %s"%stack
    call("rosinstall %s %s/stack.rosinstall --catkin"%(buildspace, workspace))


    # get the stack dependencies
    dependencies = get_dependencies(buildspace + stack)
    if len(dependencies) > 0:
        print "Install all dependencies of stack %s: %s"%(stack,' '.join(dependencies))
        call("apt-get install %s --yes --force-yes"%(' '.join([rosdep_to_apt(r) for r in dependencies])))

    # get the build environment
    build_env = {}
    command = ['bash', '-c', '%s && env'%envbuilder]
    proc = subprocess.Popen(command, stdout = subprocess.PIPE)
    for line in proc.stdout:
        (key, _, value) = line.partition("=")
        build_env[key] = value
    proc.communicate()

    # build stack
    stackbuildspace = buildspace + '/build_stack'
    print "Creating build folder"
    os.mkdir(stackbuildspace)
    os.chdir(stackbuildspace)
    print "Configure cmake"
    call("cmake ..", build_env)
    print "Building and testing stack"
    call("make", build_env)
    call("make -k test", build_env)

    # get stack depends-on list
    print "Get list of stacks that depend on %s"%stack
    apt = AptDepends(os.environ['OS_PLATFORM'], os.environ['ARCH'])
    depends_on = apt.depends_on(stack_to_apt[stack])
    print "Depends_on list for stack %s: %s"%(stack, str(depends_on))
    print "Select all wet stacks from depends_on list"
    depends_on_wet = [d for d in depends_on if d in apt_to_stack.keys()]
    print "Wet depends_on list for stack %s: %s"%(stack, str(depends_on_wet))

    # install wet depends_on stacks from source
    with open(workspace+"/depends_on.rosinstall", 'w') as f:
        rosinstall = yaml.dump([{'git': {'local-name': stack, 'uri': distro._repoinfo[stack].url, 'version': 'master'}} for stack in [apt_to_stack[a] for a in depends_on_wet]], default_style=False)
        print "Rosinstall for wet depends_on:\n %s"%rosinstall
        f.write(rosinstall)
    print "Create rosinstall file for wet depends on"
    call("rosinstall --catkin %s %s/depends_on.rosinstall"%(buildspace, workspace))
    
    # list of packages we won't install from apt
    #no_apt_list = apt.depends(stack_to_apt[stack]) # skip the apt dependencies of the stack, they might have changed
    no_apt_list = []
    no_apt_list.append(stack_to_apt[stack])
    for d in depends_on_wet:
        no_apt_list.append(d)
    print "List of packages we won't install from apt: %s"%(' '.join(no_apt_list))

    # install all stack and system dependencies of the wet depends_on list
    print "Install all dependencies of the wet depends_on list"
    res = []
    for s in [apt_to_stack[a] for a in depends_on_wet]:
        dep = get_dependencies(buildspace + s)
        for d in dep:
            if not d in res:
                res.append(d)

    res_apt = []
    for d_apt in [rosdep_to_apt(d) for d in res]:
        if not d_apt in no_apt_list:
            res_apt.append(d_apt)
    print "Dependencies of wet depends_on list are %s"%str(res_apt)
    call("apt-get install --yes --force-yes %s"%(' '.join(res_apt)))



    # build wet depend_on stacks
    dependbuildspace = buildspace + '/build_depend_on'
    print "Creating build folder"
    os.mkdir(dependbuildspace)
    os.chdir(dependbuildspace)
    print "Configure cmake"
    call("cmake ..", build_env)
    print "Building and testing stack"
    call("make", build_env)
    call("make -k test", build_env)


    return True




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
    print "==========================================================================="
    print "====== End of prerelease script. Ignore the output below =================="
    print "==========================================================================="
    print
    sys.exit(-1)
