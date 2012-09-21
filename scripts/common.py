import urllib
import os
import subprocess
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



def get_ros_env(setup_file):
    ros_env = os.environ
    print "Retrieve the ROS build environment by sourcing %s"%setup_file
    command = ['bash', '-c', 'source %s && env'%setup_file]
    proc = subprocess.Popen(command, stdout = subprocess.PIPE)
    for line in proc.stdout:
        (key, _, value) = line.partition("=")
        ros_env[key] = value.split('\n')[0]
    proc.communicate()
    if proc.returncode != 0:
        msg = "Failed to source %s"%setup_file
        print "/!\  %s"%msg
        raise BuildException(msg)
    print "ROS environment: %s"%str(ros_env)
    return ros_env


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

class BuildException(Exception):
    def __init__(self, msg):
        self.msg = msg
