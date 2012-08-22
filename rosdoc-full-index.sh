cat > $WORKSPACE/script.sh <<DELIM
#!/usr/bin/env bash
set -o errexit
set -x

# bzr 2.1 is broken, have to add ppa
sudo apt-get install -y python-software-properties
sudo add-apt-repository ppa:bzr/ppa
sudo apt-get update

sudo apt-get install python-setuptools mercurial bzr git-core doxygen python-epydoc python-svn pkg-config python-vcstools python-rospkg python-rosinstall python-rosdep -y 
sudo easy_install -U sphinx

export ROS_LANG_DISABLE=roseus:rosoct:rosjava:rosruby

# use ros-fuerte for indexer
sudo apt-get install ros-fuerte-documentation -y

# create repos.rosinstall
wget -O /tmp/generate_index.py https://code.ros.org/svn/ros/stacks/rosorg/trunk/rosdoc_rosorg/scripts/generate_index.py
chmod +x /tmp/generate_index.py
/tmp/generate_index.py /tmp/repos.rosinstall --rosdistro fuerte
cat /tmp/repos.rosinstall

rosinstall -j8 /tmp/rosdoc_checkout /tmp/repos.rosinstall --rosdep-yes  --continue-on-error -n

echo "DISK USAGE"
du -sh /tmp/rosdoc_checkout/*
du -s /tmp/rosdoc_checkout/* | sort -rn
. /opt/ros/fuerte/setup.sh
. /tmp/rosdoc_checkout/setup.sh

env
if [ ! -e /etc/ros/rosdep/sources.list.d/20-default.list ] ; then
  sudo rosdep init
fi
rosdep update

rosdep install rosdoc_rosorg -y

echo "running rosdoc_rosorg on index"
cd `rospack find rosdoc_rosorg` && rosrun rosdoc_rosorg rosdoc_rosorg.py -o /tmp/doc --upload=wgs32:/var/www/www.ros.org/html/doc/api --checkout=/tmp/rosdoc_checkout  --repos=/tmp/repos.rosinstall
DELIM


set -o errexit
echo $WORKSPACE
cat $WORKSPACE/script.sh

wget https://code.ros.org/svn/ros/stacks/ros_release/trunk/hudson/scripts/run_chroot.py --no-check-certificate -O $WORKSPACE/run_chroot.py
chmod +x $WORKSPACE/run_chroot.py
cd $WORKSPACE && $WORKSPACE/run_chroot.py --distro=lucid --arch=amd64 --script=$WORKSPACE/script.sh --ssh-key-file=/home/rosbuild/rosbuild-ssh.tar