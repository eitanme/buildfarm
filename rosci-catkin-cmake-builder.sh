set -ex
tmpdir=`mktemp -d`

APT_GET_DEPS="python-setuptools python-yaml python-pip libgtest-dev mercurial subversion git-core cmake build-essential"
# Stuff that doesn't change much
PIP_STATIC_DEPS="nose mock coverage"
# Stuff that changes a lot (install with -U)
PIP_DEPS="rospkg rosdep"
MANUAL_PY_DEP_HG_URIS="https://kforge.ros.org/rosrelease/rosci"

# Add the ROS repo
sudo sh -c "echo \"deb http://packages.ros.org/ros-shadow-fixed/ubuntu $UBUNTU_DISTRO main\" > /etc/apt/sources.list.d/ros-latest.list"
wget http://packages.ros.org/ros.key -O - | sudo apt-key add -
sudo apt-get update

for p in $APT_GET_DEPS; do
  sudo apt-get install -y $p > /dev/null
done

for p in $PIP_STATIC_DEPS; do
  sudo pip install $p > /dev/null
done

for p in $PIP_DEPS; do
  sudo pip install -U $p > /dev/null
done

for u in $MANUAL_PY_DEP_HG_URIS; do
  cd $tmpdir
  hg clone $u `basename $u`
  cd `basename $u`
  sudo python setup.py install
done

# Ignore error on init; it might have already happened.
sudo rosdep init || true
rosdep update

# install the stack.yaml Depends
wget $STACK_YAML_URL -O $tmpdir/stack.yaml
APT_DEPENDENCIES=`rosci-catkin-depends $tmpdir/stack.yaml $ROSDISTRO_NAME $OS_NAME $OS_PLATFORM`
sudo apt-get install -y $APT_DEPENDENCIES

## bootstrap env, but only the file is present (it won't be there if we're
## building catkin itself.)
SETUP_FILE=/opt/ros/$ROSDISTRO_NAME/setup.sh
if [[ -f $SETUP_FILE ]]; then
  . $SETUP_FILE
fi
export ROS_HOME=$WORKSPACE/build/ros_home
export ROS_TEST_RESULTS_DIR=$WORKSPACE/build/test_results

# catkin-specific stuff
#
rm -rf $WORKSPACE/build
mkdir -p $WORKSPACE/build
cd $WORKSPACE/build && cmake $WORKSPACE/$STACK_NAME
cd $WORKSPACE/build && make
if cd $WORKSPACE/build && make test; then echo "tests passed"; fi

if [[ -n `rospack find rosunit` ]]; then
  $WORKSPACE/build/env.sh `rospack find rosunit`/scripts/clean_junit_xml.py
fi

sudo rm -rf $tmpdir
