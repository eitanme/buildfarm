#!/bin/sh -e

set -x
./buildfarm/sanity_check.sh

/bin/echo "vvvvvvvvvvvvvvvvvvv  catkin-workspace-all.sh vvvvvvvvvvvvvvvvvvvvvv"

if [ -z "$WORKSPACE" ] ; then
    /bin/echo "Don't see no workspace."
    exit 1
fi

cd $WORKSPACE

# get ros system tools
#sudo apt-get install -y python-pip
#sudo pip install --upgrade rosinstall
#sudo pip install --upgrade rosdep
if [ ! -d rosdep ]; then
  hg clone https://kforge.ros.org/rosrelease/rosdep
fi
cd rosdep
hg pull
hg up
sudo python setup.py install
cd ..

sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $UBUNTU_DISTRO main" > /etc/apt/sources.list.d/ros-latest.list'
wget http://packages.ros.org/ros.key -O - | sudo apt-key add -
sudo apt-get update

curl -s https://raw.github.com/willowgarage/catkin/master/test/test.rosinstall > test.rosinstall
rosinstall -n --delete-changed-uris src test.rosinstall

cd src
rm -f CMakeLists.txt
ln -s catkin/toplevel.cmake CMakeLists.txt
cd ..
#rm -rf build
mkdir -p build
cd build
DESTDIR=$WORKSPACE/install
rm -rf $DESTDIR
cmake -DCMAKE_INSTALL_PREFIX=$DESTDIR ../src
#export ROS_TEST_RESULTS_DIR=$WORKSPACE/build/test_results
make
#make -i test
#$WORKSPACE/build/env.sh $WORKSPACE/src/ros/tools/rosunit/scripts/clean_junit_xml.py
make install

mkdir -p $WORKSPACE/dry_land
curl -s https://raw.github.com/willowgarage/catkin/master/test/unstable/desktop-overlay.rosinstall > $WORKSPACE/dry_land/desktop-overlay.rosinstall
curl -s https://raw.github.com/willowgarage/catkin/master/test/unstable/extras.rosinstall > $WORKSPACE/dry_land/extras.rosinstall
# temporary: protect against kforge auth errors
rosinstall -n --delete-changed-uris $WORKSPACE/dry_land $DESTDIR $WORKSPACE/dry_land/desktop-overlay.rosinstall $WORKSPACE/dry_land/extras.rosinstall
. $WORKSPACE/dry_land/setup.sh
. $DESTDIR/setup.sh
rosdep install -y -a
rosmake -a -k


/bin/echo "^^^^^^^^^^^^^^^^^^  catkin-workspace-all.sh ^^^^^^^^^^^^^^^^^^^^"

cd $WORKSPACE
$WORKSPACE/buildfarm/sanity_check.sh
