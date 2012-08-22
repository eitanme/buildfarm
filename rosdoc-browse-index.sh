set -o errexit
set -x

# bzr 2.1 is broken, have to add ppa
sudo apt-get install -y python-software-properties
sudo add-apt-repository ppa:bzr/ppa
sudo apt-get update

sudo apt-get install python-setuptools mercurial bzr git-core doxygen python-epydoc python-svn python-vcstools python-rospkg python-rosinstall -y 
sudo easy_install -U sphinx

export ROS_LANG_DISABLE=roseus:rosoct:rosjava

# use ros-fuerte for indexer
sudo apt-get install ros-fuerte-documentation -y

# create repos.rosinstall
wget -O /tmp/generate_index.py https://code.ros.org/svn/ros/stacks/rosorg/trunk/rosdoc_rosorg/scripts/generate_fuerte_index.py
chmod +x /tmp/generate_index.py
/tmp/generate_index.py /tmp/repos.rosinstall --rosdistro fuerte
cat /tmp/repos.rosinstall

rosinstall -j8 $WORKSPACE/rosdoc_checkout /tmp/repos.rosinstall -n --continue-on-error --delete-changed-uris
. $WORKSPACE/rosdoc_checkout/setup.sh

env

rosmake rosdoc_rosorg --rosdep-install --rosdep-yes --status-rate=0

echo "running rosdoc_rosorg on index"
cd `rospack find rosdoc_rosorg` && rosrun rosdoc_rosorg rosdoc_rosorg.py -o /tmp/doc --upload=wgs32:/var/www/www.ros.org/html/browse --checkout=$WORKSPACE/rosdoc_checkout --rosbrowse  --repos /tmp/repos.rosinstall
