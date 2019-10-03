# if [ -f "$PREFIX/setup.sh" ]; then source $PREFIX/setup.sh; fi

mkdir build
cd build

# turn this into a catkin workspace by adding the catkin token if it doesn't
# exist already
if [ ! -f $PREFIX/.catkin ]; then
    touch $PREFIX/.catkin
fi

# NOTE: there might be undefined references occurring
# in the Boost.system library, depending on the C++ versions
# used to compile Boost and/or the piranha examples. We
# can avoid them by forcing the use of the header-only
# version of the library.
export CXXFLAGS="$CXXFLAGS -DBOOST_ERROR_CODE_HEADER_ONLY"

cmake .. -DCMAKE_INSTALL_PREFIX=$PREFIX \
         -DCMAKE_PREFIX_PATH=$PREFIX \
         -DCMAKE_INSTALL_LIBDIR=lib \
         -DCMAKE_BUILD_TYPE=Release \
         -DSETUPTOOLS_DEB_LAYOUT=OFF
         # remove the following line for catkin so `setup.sh` scripts are installed!
         # -DCATKIN_BUILD_BINARY_PACKAGE="1" \

make VERBOSE=1 -j${CPU_COUNT}
make install
mkdir -p $PREFIX/etc/conda/activate.d/

cat > /tmp/add_to_ros_setup.sh << 'EOT'
if [ -n "`$SHELL -c 'echo $ZSH_VERSION'`" ]; then
  CATKIN_SHELL=zsh
elif [ -n "`$SHELL -c 'echo $BASH_VERSION'`" ]; then
  CATKIN_SHELL=bash
else
  echo "could not detect your shell"
fi
EOT

sed -i'.bak' -e '14c: ${_CATKIN_SETUP_DIR:=$CONDA_PREFIX/etc/conda/activate.d/}' $PREFIX/setup.sh
sed -i'.bak' -e '13r /tmp/add_to_ros_setup.sh' $PREFIX/setup.sh
sed -i'.bak' -e 's/setup.sh/etc\/conda\/activate.d\/setup.sh/g' $PREFIX/.rosinstall

# remove adding the "base path" (path of location of activation script) to CMAKE_PREFIX_PATH
sed -i'.bak' -e '/        if base_path not in CMAKE_PREFIX_PATH:/s/^/#/' $PREFIX/_setup_util.py
sed -i'.bak' -e '/            CMAKE_PREFIX_PATH.insert(0, base_path)/s/^/#/' $PREFIX/_setup_util.py

mv $PREFIX/setup.sh $PREFIX/etc/conda/activate.d/ros_setup.sh
mv $PREFIX/_setup_util.py $PREFIX/etc/conda/activate.d/_setup_util.py

# handled by conda activate
rm $PREFIX/setup.*
rm $PREFIX/local_setup.*
rm $PREFIX/env.sh