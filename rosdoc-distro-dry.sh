#TODO: this should be converted to use the new dispatch-style chroot

#TODO: this does not work with catkin-ized stacks because there is no
#source in them.  Possibilities include using "apt-get src", but that
#would not help with packages like tf, which require built source.  It
#may be the case that catkin-ized stacks must manually generate and
#push docs in the future.

cat > $WORKSPACE/script.sh <<DELIM
#!/usr/bin/env bash
set -o errexit
set -x

sudo apt-get install python-setuptools mercurial git-core python-sphinx python-svn doxygen python-epydoc -y 1> /dev/null

echo "installing vcstools"
sudo easy_install -U vcstools
echo "installing index via rosinstall"
sudo easy_install -U rosinstall
export ROS_LANG_DISABLE=roseus:rosoct:rosjava
sudo apt-get install ros-$DISTRO-ros-comm -y
# 8 parallel checkouts
rosinstall -j 8 /tmp/rosdoc_checkout http://code.ros.org/svn/ros/stacks/rosorg/trunk/rosdoc_rosorg/index/repos-$DISTRO.rosinstall --rosdep-yes  --continue-on-error
cat /tmp/rosdoc_checkout/setup.bash
cat /tmp/rosdoc_checkout/setup.sh
. /tmp/rosdoc_checkout/setup.sh

rosrun rosdoc_rosorg create_distro_index.py $DISTRO /tmp/distro-$DISTRO.yaml
rosrun rosdoc_rosorg install_distro_index.py /tmp/distro-$DISTRO.yaml
rosmake rosdoc_rosorg --no-rosdep

echo "running rosdoc_rosorg on index"
cd /tmp/rosdoc_checkout/rosorg/rosdoc_rosorg && rosrun rosdoc_rosorg rosdoc_rosorg.py -o /tmp/doc --upload=wgs32:/var/www/www.ros.org/html/doc/$DISTRO/api --checkout=/tmp/rosdoc_checkout --distro-index=/tmp/distro-$DISTRO.yaml --repos=/tmp/rosdoc_checkout/rosorg/rosdoc_rosorg/index/repos-$DISTRO.rosinstall
DELIM


set -o errexit
echo $WORKSPACE
cat $WORKSPACE/script.sh

wget https://code.ros.org/svn/ros/stacks/ros_release/trunk/hudson/scripts/run_chroot.py --no-check-certificate -O $WORKSPACE/run_chroot.py
chmod +x $WORKSPACE/run_chroot.py
cd $WORKSPACE && $WORKSPACE/run_chroot.py --distro=lucid --arch=amd64 --script=$WORKSPACE/script.sh --ramdisk --ramdisk-size=25000M --ssh-key-file=/home/rosbuild/rosbuild-ssh.tar
