set -o errexit
set -x

sudo apt-get install python-setuptools mercurial -y 
sudo easy_install -U vcstools rospkg rosinstall rosdep

DISTRO=fuerte

# base will now contain common_msgs, actionlib for simplicity
# create fuerte-ros_base.rosinstall, fuerte-ros_full.rosinstall
wget -O /tmp/generate_wet_rosinstall.py https://raw.github.com/willowgarage/buildfarm/generate_wet_rosinstall.py
chmod +x /tmp/generate_wet_rosinstall.py
/tmp/generate_wet_rosinstall.py $DISTRO

echo "ros-base"
cat /tmp/$DISTRO-ros_base.rosinstall
echo "ros-full"
cat /tmp/$DISTRO-ros_full.rosinstall

# scp back to wgs32
#cd `rospack find rosdoc_rosorg` && rosrun rosdoc_rosorg rosdoc_rosorg.py -o /tmp/doc --upload=wgs32:/var/www/www.ros.org/html/browse --checkout=$WORKSPACE/rosdoc_checkout --rosbrowse  --repos /tmp/repos.rosinstall
