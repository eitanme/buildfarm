import urllib
import os
import subprocess
import sys
import fnmatch
import yaml
from xml.etree.ElementTree import ElementTree

class RosDistro:
    def __init__(self, name):
        url = urllib.urlopen('https://raw.github.com/ros/rosdistro/master/releases/%s.yaml'%name)
        distro = yaml.load(url.read())
        self.repositories = {}
        self.packages = []
        for name, data in distro['repositories'].iteritems():
            repo = RosDistroRepo(data)
            self.repositories[name] = repo
            for p in repo.packages:
                self.packages.append(p)


class RosDistroRepo:
    def __init__(self, data):
        self.url = data['url']
        self.version = data['version']
        self.packages = []
        if 'packages' in data.keys():
            self.packages = data['packages'].keys()
            
    def get_rosinstall_release(self, version=None):
        if not version:
            version = self.version
        rosinstall = ""
        for p in self.packages:
            rosinstall += yaml.dump([{'git': {'local-name': p, 'uri': self.url, 'version': '/'.join(['release', p, version])}}], default_style=False)
        return rosinstall


    def get_rosinstall_prerelease(self):
        rosinstall = ""
        for p in self.packages:
            rosinstall += yaml.dump([{'git': {'local-name': p, 'uri': self.url, 'version': '/'.join(['release', p])}}], default_style=False)
        return rosinstall



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

class RosDepResolver:
    def __init__(self, ros_distro):
        self.r2a = {}
        self.a2r = {}
        self.env = os.environ
        self.env['ROS_DISTRO'] = ros_distro

        print "Ininitalize rosdep database"
        call("apt-get install --yes lsb-release python-rosdep")
        call("rosdep init", self.env)
        call("rosdep update", self.env)

        print "Building dictionaries from a rosdep's db"
        raw_db = call("rosdep db", self.env).split('\n')

        for entry in raw_db:
            split_entry = entry.split()
            if len(split_entry) != 3 or split_entry[1] != '->':
                continue
            ros_entry, arrow, apt_entry = split_entry
            self.r2a[ros_entry] = apt_entry
            self.a2r[apt_entry] = ros_entry

    def to_ros(self, apt_entry):
        return self.a2r[apt_entry]

    def to_apt(self, ros_entry):
        return self.r2a[ros_entry]

    def has_ros(self, ros_entry):
        return ros_entry in self.r2a

    def has_apt(self, apt_entry):
        return apt_entry in self.a2r
        
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
            res = call("rosdep resolve %s"%r, self.env).split('\n') 
            if len(res) == 1:
                raise Exception("Could not resolve rosdep")
            a = call("rosdep resolve %s"%r, self.env).split('\n')[1]
            print "Rosdep %s resolved into %s"%(r, a)
            self.r2a[r] = a
            self.a2r[a] = r
            return a

    def to_stack(self, a):
        if not a in self.a2r:
            print "%s not in apt-to-rosdep cache"%a
        return self.a2r[a]



def copy_test_results(workspace, buildspace):
    print "Preparing xml test results"
    try:
        os.makedirs(os.path.join(workspace, 'test_results'))
        print "Created test results directory"
    except:
        pass
    os.chdir(os.path.join(workspace, 'test_results'))
    print "Copy all test results"
    count = 0
    for root, dirnames, filenames in os.walk(os.path.join(buildspace, 'test_results')):
        for filename in fnmatch.filter(filenames, '*.xml'):
            call("cp %s %s/test_results/"%(os.path.join(root, filename), workspace))
            count += 1
    if count == 0:
        print "No test results, so I'll create a dummy test result xml file"
        call("cp %s %s"%(os.path.join(workspace, 'buildfarm/templates/junit_dummy_ouput_template.xml'),
                         os.path.join(workspace, 'test_results/')))



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

def build_dependency_graph(source_folder):
    sys.path.append("/usr/lib/pymodules/python2.7/")
    from catkin_pkg import packages
    pkgs = packages.find_packages(source_folder)
    local_packages = [os.path.basename(k) for k in pkgs.keys()]

    depends = {}
    for full_name, pkg in pkgs.iteritems():
        name = os.path.basename(full_name)
        depends[name] = []
        for d in pkg.build_depends + pkg.test_depends + pkg.run_depends:
            #we only want to build a graph for our local deps
            if d.name in local_packages:
                depends[name].append(d.name)

    return depends

def build_dependency_graph_manifest(source_folder):
    sys.path.append("/usr/lib/pymodules/python2.7/")
    import rospkg

    depends = {}
    location_cache = {}
    local_packages = rospkg.list_by_path(rospkg.MANIFEST_FILE, source_folder, location_cache)
    for name, path in location_cache.iteritems():
        manifest = rospkg.parse_manifest_file(path, rospkg.MANIFEST_FILE)
        depends[name] = []
        for d in manifest.depends + manifest.rosdeps:
            if d.name in local_packages:
                depends[name].append(str(d.name))

    return depends

def reorder_paths(order, packages, paths):
    #we want to make sure that we can still associate packages with paths
    new_paths = []
    for package in order:
        old_index = [i for i, name in enumerate(packages) if package == name][0]
        new_paths.append(paths[old_index])

    return order, new_paths

def get_dependency_build_order(depends):
    import networkx as nx
    graph = nx.DiGraph()

    for name, deps in depends.iteritems():
        graph.add_node(name)
        graph.add_edges_from([(name, d) for d in deps])

    order = nx.topological_sort(graph)
    order.reverse()

    return order

def get_dependencies(source_folder):
    # get the dependencies
    print "Get the dependencies of source folder %s"%source_folder
    sys.path.append("/usr/lib/pymodules/python2.7/")
    from catkin_pkg import packages
    pkgs = packages.find_packages(source_folder)
    local_packages = pkgs.keys()
    if len(pkgs) > 0:
        print "In folder %s, found packages %s"%(source_folder, ', '.join(local_packages))
    else:
        raise BuildException("Found no packages in folder %s. Are you sure your packages have a packages.xml file?"%source_folder)

    depends = []
    for name, pkg in pkgs.iteritems():
        for d in pkg.build_depends + pkg.test_depends:
            if not d.name in depends and not d.name in local_packages:
                depends.append(d.name)
    return depends



class BuildException(Exception):
    def __init__(self, msg):
        self.msg = msg
