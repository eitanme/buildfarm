import urllib
import os
import subprocess
import sys
import fnmatch
import yaml
import threading
import time
import datetime
from Queue import Queue
from threading import Thread
from xml.etree.ElementTree import ElementTree

def append_pymodules_if_needed():
    #TODO: This is a hack, in the chroot, the default python path does not
    if not os.path.abspath("/usr/lib/pymodules/python2.7") in sys.path:
        sys.path.append("/usr/lib/pymodules/python2.7")




## {{{ http://code.activestate.com/recipes/577187/ (r9)
class Worker(Thread):
    """Thread executing tasks from a given tasks queue"""
    def __init__(self, tasks):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.start()
    
    def run(self):
        while True:
            func, args, kargs = self.tasks.get()
            try: func(*args, **kargs)
            except Exception, e: print e
            self.tasks.task_done()

class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, num_threads):
        self.tasks = Queue(num_threads)
        for _ in range(num_threads): Worker(self.tasks)

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()



class DevelDistro:
    def __init__(self, name):
        url = urllib.urlopen('https://raw.github.com/ros/rosdistro/master/releases/%s-devel.yaml'%name)
        distro = yaml.load(url.read())['repositories']
        self.repositories = {}
        for name, data in distro.iteritems():
            repo = DevelDistroRepo(name, data)
            self.repositories[name] = repo

class DevelDistroRepo:
    def __init__(self, name, data):
        self.name = name
        self.url = data['url']
        self.type = data['type']
        self.version = None
        if 'version' in data.keys():
            self.version = data['version']
            
    def get_rosinstall(self):
        if self.version:
            return yaml.dump([{self.type: {'local-name': self.name, 'uri': '%s'%self.url, 'version': '%s'%self.version}}], default_style=False)
        else:
            return yaml.dump([{self.type: {'local-name': self.name, 'uri': '%s'%self.url}}], default_style=False)




class RosDistro:
    def __init__(self, name, initialize_dependencies=False):
        url = urllib.urlopen('https://raw.github.com/ros/rosdistro/master/releases/%s.yaml'%name)
        distro = yaml.load(url.read())['repositories']
        self.repositories = {}
        self.packages = {}
        self.threadpool = ThreadPool(5)
        for repo_name, data in distro.iteritems():
            if 'packages' in data.keys():
                pkgs = []
                url = data['url']
                version = data['version']
                for pkg_name in data['packages'].keys():
                    pkg = RosDistroPackage(pkg_name, url, version)
                    if initialize_dependencies:
                        self.threadpool.add_task(pkg.initialize_dependencies)
                    pkgs.append(pkg)
                    self.packages[pkg_name] = pkg
                self.repositories[repo_name] = RosDistroRepo(repo_name, pkgs)
                
        # wait for all packages to be initialized
        if initialize_dependencies:
            for name, pkg in self.packages.iteritems():
                while not pkg.initialized:
                    time.sleep(0.1)
            print "All package dependencies initialized"
                
                    
        



class RosDistroRepo:
    def __init__(self, name, pkgs):
        self.name = name
        self.pkgs = pkgs
    
    def get_rosinstall_release(self, version=None):
        rosinstall = ""
        for p in self.pkgs:
            rosinstall += p.get_rosinstall_release(version)
        return rosinstall

    def get_rosinstall_latest(self):
        rosinstall = ""
        for p in self.pkgs:
            rosinstall += p.get_rosinstall_latest()
        return rosinstall



class RosDistroPackage:
    def __init__(self, name, url, version, initialize_dependencies=False):
        self.lock = threading.Lock()
        self.initialized = False
        self.name = name
        self.url = url
        self.version = version.split('-')[0]
        
    def initialize_dependencies(self):
        with self.lock:
            http = self.url
            http = http.replace('.git', '/release')
            http = http.replace('git://', 'http://raw.')
            url = '%s/%s/%s/package.xml'%(http, self.name, self.version)
            package_xml = urllib.urlopen(url).read()
            append_pymodules_if_needed()
            from catkin_pkg import package
            try:
                pkg = package.parse_package_string(package_xml)
            except package.InvalidPackage as e:
                print "!!!!!! Invalid package.xml for package %s at url %s"%(self.name, url)
                raise BuildException("Invalid package.xml")
            self.build_depends_on1 = [d.name for d in pkg.build_depends]
            self.test_depends_on1 = [d.name for d in pkg.test_depends]
            self.initialized = True

    def get_rosinstall_release(self, version=None):
        if not version:
            version = self.version
        return yaml.safe_dump([{'git': {'local-name': self.name, 'uri': self.url, 'version': '?'.join(['release', self.name, version])}}], 
                              default_style=False).replace('?', '/')

    def get_rosinstall_latest(self):
        return yaml.dump([{'git': {'local-name': self.name, 'uri': self.url, 'version': '?'.join(['release', self.name])}}], 
                         default_style=False).replace('?', '/')





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

    def has_package(self, package):
        return package in self.dep
        
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
            split_entry = entry.split(' -> ')
            if len(split_entry) < 2:
                continue
            ros_entry = split_entry[0]
            apt_entries = split_entry[1].split(' ')
            self.r2a[ros_entry] = apt_entries
            for a in apt_entries:
                self.a2r[a] = ros_entry

    def to_aptlist(self, ros_entries):
        res = []
        for r in ros_entries:
            for a in self.to_apt(r):
                if not a in res:
                    res.append(a)
        return res

    def to_ros(self, apt_entry):
        if not apt_entry in self.a2r.keys():
            print "Could not find %s in keys. Have keys %s"%(apt_entry, ', '.join(self.a2r.keys()))
        return self.a2r[apt_entry]

    def to_apt(self, ros_entry):
        if not ros_entry in self.r2a.keys():
            print "Could not find %s in keys. Have keys %s"%(ros_entry, ', '.join(self.r2a.keys()))
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



def get_timestamp():
    return str(datetime.datetime.now()).replace(' ','_').replace(':','.')

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

def call_with_list(command, envir=None):
    print "Executing command '%s'"%' '.join(command)
    helper = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, env=envir)
    res, err = helper.communicate()
    print str(res)
    print str(err)
    if helper.returncode != 0:
        msg = "Failed to execute command '%s'"%command
        print "/!\  %s"%msg
        raise BuildException(msg)
    return res

def call(command, envir=None):
    return call_with_list(command.split(' '))

def get_nonlocal_dependencies(catkin_packages, stacks, manifest_packages):
    append_pymodules_if_needed()
    from catkin_pkg import packages
    import rospkg

    depends = []
    #First, we build the catkin deps
    for name, path in catkin_packages.iteritems():
        pkg_info = packages.parse_package(path)
        depends.extend([d.name \
                        for d in pkg_info.build_depends + pkg_info.test_depends + pkg_info.run_depends \
                        if not d.name in catkin_packages and not d.name in depends])

    #Next, we build the manifest deps for stacks
    for name, path in stacks.iteritems():
        stack_manifest = rospkg.parse_manifest_file(path, rospkg.STACK_FILE)
        depends.extend([d.name \
                        for d in stack_manifest.depends + stack_manifest.rosdeps \
                        if not d.name in catkin_packages \
                        and not d.name in stacks \
                        and not d.name in depends])

    #Next, we build manifest deps for packages
    for name, path in manifest_packages.iteritems():
        pkg_manifest = rospkg.parse_manifest_file(path, rospkg.MANIFEST_FILE)
        depends.extend([d.name \
                        for d in pkg_manifest.depends + pkg_manifest.rosdeps \
                        if not d.name in catkin_packages \
                        and not d.name in stacks \
                        and not d.name in manifest_packages \
                        and not d.name in depends])


    return depends

def build_local_dependency_graph(catkin_packages, manifest_packages):
    append_pymodules_if_needed()
    from catkin_pkg import packages
    import rospkg

    depends = {}
    #First, we build the catkin dep tree
    for name, path in catkin_packages.iteritems():
        depends[name] = []
        pkg_info = packages.parse_package(path)
        for d in pkg_info.build_depends + pkg_info.test_depends + pkg_info.run_depends:
            if d.name in catkin_packages and d.name != name:
                depends[name].append(d.name)

    #Next, we build the manifest dep tree
    for name, path in manifest_packages.iteritems():
        manifest = rospkg.parse_manifest_file(path, rospkg.MANIFEST_FILE)
        depends[name] = []
        for d in manifest.depends + manifest.rosdeps:
            if (d.name in catkin_packages or d.name in manifest_packages) and d.name != name:
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



def get_dependencies(source_folder, build_depends=True, test_depends=True):
    # get the dependencies
    print "Get the dependencies of source folder %s"%source_folder
    append_pymodules_if_needed()
    from catkin_pkg import packages
    pkgs = packages.find_packages(source_folder)
    local_packages = pkgs.keys()
    if len(pkgs) > 0:
        print "In folder %s, found packages %s"%(source_folder, ', '.join(local_packages))
    else:
        raise BuildException("Found no packages in folder %s. Are you sure your packages have a packages.xml file?"%source_folder)

    depends = []
    for name, pkg in pkgs.iteritems():
        if build_depends:
            for d in pkg.build_depends:
                if not d.name in depends and not d.name in local_packages:
                    depends.append(d.name)
        if test_depends:
            for d in pkg.test_depends:
                if not d.name in depends and not d.name in local_packages:
                    depends.append(d.name)

    return depends



class BuildException(Exception):
    def __init__(self, msg):
        self.msg = msg
