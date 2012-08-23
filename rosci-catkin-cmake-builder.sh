set -ex
tmpdir=`mktemp -d`

APT_GET_DEPS="python-setuptools python-yaml python-pip libgtest-dev mercurial subversion git-core cmake build-essential python-rospkg python-rosdep pbuilder"
# Stuff that doesn't change much
PIP_STATIC_DEPS="nose mock coverage"
# Stuff that changes a lot (install with -U)
PIP_DEPS=""
MANUAL_PY_DEP_GIT_URIS="" #https://github.com/willowgarage/catkin-debs"

# Add the ROS repo
#sudo sh -c "echo \"deb http://packages.ros.org/ros-shadow-fixed/ubuntu $UBUNTU_DISTRO main\" > /etc/apt/sources.list.d/ros-latest.list"
sudo sh -c "echo \"deb http://50.28.27.175/repos/building $UBUNTU_DISTRO main\" > /etc/apt/sources.list.d/ros-latest.list"
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

for u in $MANUAL_PY_DEP_GIT_URIS; do
  cd $tmpdir
  git clone --depth 1 $u `basename $u`
  cd `basename $u`
  sudo python setup.py install
done

# Ignore error on init; it might have already happened.
sudo rosdep init || true
rosdep update

u="https://github.com/willowgarage/catkin-debs"
cd $tmpdir && git clone --depth 1 $u `basename $u` && cd `basename $u` && . setup.sh


# install the stack.xml Depends
APT_DEPENDENCIES=`rosci-catkin-depends $ROSDISTRO_NAME $OS_NAME $OS_PLATFORM $STACK_BUILD_DEPENDS`
sudo apt-get install -y $APT_DEPENDENCIES

## bootstrap env, but only the file is present (it won't be there if we're
## building catkin itself.)
SETUP_FILE=/opt/ros/$ROSDISTRO_NAME/setup.sh
if [[ -f $SETUP_FILE ]]; then
  . $SETUP_FILE
fi
export ROS_HOME=$WORKSPACE/build/ros_home
export ROS_TEST_RESULTS_DIR=$WORKSPACE/build/test_results
# HACK: shouldn't need to do this
export ROS_PACKAGE_PATH=$WORKSPACE/$STACK_NAME:$ROS_PACKAGE_PATH

# catkin-specific stuff
#
rm -rf $WORKSPACE/build
mkdir -p $WORKSPACE/build
cd $WORKSPACE/build && cmake $WORKSPACE/$STACK_NAME
fail=0
cd $WORKSPACE/build
if ! make; then
  fail=1
fi
if cd $WORKSPACE/build && make -k test; then echo "tests passed"; fi

CLEANED_TEST_DIR=$ROS_TEST_RESULTS_DIR/_hudson
if [[ ! -d $CLEANED_TEST_DIR ]]; then
  mkdir -p $CLEANED_TEST_DIR
fi
rosci-clean-junit-xml

# In case there are no test results, make one up, to keep Jenkins from declaring
# the build a failure
cat > $WORKSPACE/build/test_results/_hudson/jenkins_dummy.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<testsuite tests="1" failures="0" time="1" errors="0" name="dummy">
  <testcase name="dummy" status="run" time="1" classname="Results"/>
</testsuite>
EOF

sudo rm -rf $tmpdir

if [[ $fail -eq 1 ]]; then
  echo "Build failed"
  exit 1
fi
