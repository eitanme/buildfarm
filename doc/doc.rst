Overview and Usage of "doc" Script
-----------------------------------------------------

Overview
=====================================================

The ``doc`` script wraps the ``rosdoc_lite`` tool to provide stack-level API documentation. Running this script generates html documentation for each stack along with a set of doxygen "tag" files used for cross-referencing support. To find the list of stacks available for documentation, the script pulls from the ``rosdistro`` repository. The script also automatically pulls from the ``rosdoc_tag_index`` repository to find the list of available tag files for a given distribution and updates this same repository at the end of a documentation run. Upon completion, the script uses ``rsync`` to push the generated documentation and tag files to Willow Garage's servers.

Usage
=====================================================
The ``doc`` script takes two arguments:
 * distro - The ROS distribution on which to run (Ex: fuerte)
 * stack - The name of the stack to document (Ex: actionlib)

 The ``doc`` script is run using the standard jenkins buildfarm tools. For example, to run documentation  for fuerte actionlib locally in a chroot for 32-bit Ubunutu Precise, the following command could be used:
      % ./run_local_debug precise i386 /home/eitan/hidof/willow_garage/jenkins_workspace doc fuerte navigation
