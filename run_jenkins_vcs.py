#!/usr/bin/env python

import sys
import jenkins
import urllib
import yaml
import datetime
import os
from rospkg import environment


# Schedule a set of jobs in Jenkins
def run_jenkins_vcs(jenkins_instance, 
                    ubuntu_distro, arch, name, email, vcs, uri, branch,
                    script, script_args, user_name):

    # open template xlm file
    f = urllib.urlopen('https://raw.github.com/willowgarage/buildfarm/master/templates/jenkins_template.xml')
    job_xml = f.read()

    # open trigger file
    f = urllib.urlopen('https://raw.github.com/willowgarage/buildfarm/master/templates/jenkins_conf.yaml')
    jc = yaml.load(f)

    # get arguments
    params = {}
    params['UBUNTU_DISTRO'] = ubuntu_distro
    params['ARCH'] = arch
    params['EMAIL'] = email
    params['TRIGGER'] = jc['triggers']['vcs']
    params['VCS'] = jc['vcs'][vcs].replace('@(URI)', uri)#.replace('@(BRANCH)', branch)
    params['SCRIPT'] = script
    params['NODE'] = params['SCRIPT']
    params['TIME'] = str(datetime.datetime.now())
    params['SCRIPT_ARGS'] = ' '.join(script_args)
    params['USERNAME'] = user_name
    params['HOSTNAME'] = os.uname()[1]

    # replace @(xxx) in template file
    for key, value in params.iteritems():
        job_xml = job_xml.replace("@(%s)"%key, value)

    # schedule a new job
    job_name = "%s-%s-%s-%s"%(params['SCRIPT'], name, params['UBUNTU_DISTRO'], params['ARCH'])
    if jenkins_instance.job_exists(job_name):
        jenkins_instance.reconfig_job(job_name, job_xml)
        print "Reconfigured job %s"%job_name
    else:
        jenkins_instance.create_job(job_name, job_xml)
        print "Created job %s"%job_name
    jenkins_instance.build_job(job_name)
    print "Started job %s"%job_name
    print "When the test finishes, you will receive an email at %s"%params['EMAIL']
    
    return job_name



def main():
    if len(sys.argv) < 8:
        print "Usage: %s ubuntu_distro arch job_name email {svn/git/hg} uri branch script [script_args]"%(sys.argv[0])
        sys.exit(0)

    ubuntu_distro = sys.argv[1]
    arch = sys.argv[2]
    name = sys.argv[3]
    email = sys.argv[4]
    vcs = sys.argv[5]
    uri = sys.argv[6]
    branch = sys.argv[7]
    script = sys.argv[8]
    script_args = sys.argv[9:]

    # create jenkins instance 
    with open(os.path.join(environment.get_ros_home(), 'catkin-debs', 'server.yaml')) as f:
        info = yaml.load(f)
    jenkins_instance = jenkins.Jenkins('http://jenkins.willowgarage.com:8080/', info['username'], info['password'])
    print "Created Jenkins instance"

    # run job
    job_name = run_jenkins_vcs(jenkins_instance, 
                               ubuntu_distro, arch, name, email, vcs, uri, branch,
                               script, script_args, info['username'])




if __name__ == "__main__":
    main()
