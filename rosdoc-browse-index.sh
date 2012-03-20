set -x
# bzr 2.1 is broken, have to add ppa
sudo apt-get install -y python-software-properties
sudo add-apt-repository ppa:bzr/ppa
sudo apt-get update

sudo apt-get install python-setuptools mercurial bzr git-core -y 

echo "installing vcstools"
sudo easy_install -U vcstools
echo "installing index via rosinstall"
sudo easy_install -U rosinstall rospkg
export ROS_LANG_DISABLE=roseus:rosoct:rosjava

# use ros-unstable for indexer
sudo apt-get install ros-unstable-ros -y

# create repos.rosinstall
wget -O generate_index.py https://code.ros.org/svn/ros/stacks/rosorg/trunk/rosdoc_rosorg/scripts/generate_index.py
chmod +x generate_index.py
./generate_index.py /tmp/repos.rosinstall
cat /tmp/repos.rosinstall

rosinstall $WORKSPACE/rosdoc_checkout /tmp/repos.rosinstall -n --continue-on-error --delete-changed-uris
echo "completed rosinstall, now sourcing environment"
. $WORKSPACE/rosdoc_checkout/setup.sh
echo "completed sourcing environment"

echo "ROS_PACKAGE_PATH" $ROS_PACKAGE_PATH
echo "building rosdoc_rosorg"
rosmake rosdoc_rosorg --rosdep-install --rosdep-yes

echo "running rosdoc_rosorg on index"
cd `rospack find rosdoc_rosorg` && rosrun rosdoc_rosorg rosdoc_rosorg.py -o /tmp/doc --upload=wgs32:/var/www/www.ros.org/html/browse --checkout=$WORKSPACE/rosdoc_checkout --rosbrowse  --repos /tmp/repos.rosinstall
