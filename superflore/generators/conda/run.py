from rosinstall_generator.distro import get_distro
from superflore.generate_installers import generate_installers
from superflore.generators.ebuild.gen_packages import regenerate_pkg
from superflore.generators.ebuild.overlay_instance import RosOverlay
from superflore.parser import get_parser
from superflore.repo_instance import RepoInstance
from superflore.TempfileManager import TempfileManager
from superflore.utils import active_distros
from superflore.utils import clean_up
from superflore.utils import err
from superflore.utils import file_pr
from superflore.utils import gen_delta_msg
from superflore.utils import gen_missing_deps_msg
from superflore.utils import info
from superflore.utils import load_pr
from superflore.utils import ok
from superflore.utils import ros2_distros
from superflore.utils import save_pr
from superflore.utils import url_to_repo_org
from superflore.utils import warn

from rosdistro.dependency_walker import DependencyWalker
from rosdistro.manifest_provider import get_release_tag
from rosdistro.rosdistro import RosPackage
from rosinstall_generator.distro import _generate_rosinstall
from rosinstall_generator.distro import get_package_names
from superflore.exceptions import UnresolvedDependency
from superflore.generators.ebuild.ebuild import Ebuild
from superflore.generators.ebuild.metadata_xml import metadata_xml
from superflore.PackageMetadata import PackageMetadata
from superflore.utils import err
from superflore.utils import get_pkg_version
from superflore.utils import make_dir
from superflore.utils import ok
from superflore.utils import ros2_distros
from superflore.utils import warn

import superflore
print("Imported from " , superflore.__file__)
print("Imported from " , superflore.generate_installers.__file__)

from pprint import pprint
from glob import glob
import os
import shutil
import requests
import subprocess
import json
from jinja2 import Template

# TODO(allenh1): This is a blacklist of things that
# do not yet support Python 3. This will be updated
# on an as-needed basis until a better solution is
# found (CI?).

no_python3 = ['tf']

org = "Open Source Robotics Foundation"
org_license = "BSD"


class CondaPackage():
    pass

recipe_template = ""

with open("recipe.tmpl") as tmpin:
    conda_template = Template(tmpin.read())


['cmake'
'python'
'catkin_pkg'
'boost-cpp'
'console_bridge'
'pyyaml'
'apr'
'log4cxx'
'rospkg'
'pillow'
'python-gnupg'
'pycrypto'
'qt_gui_py_common'
'qt_gui'
'gtest'
'tinyxml2'
'pkg-config'
'rosdep'
'python-cairo'
'urdfdom_headers'
'paramiko'
'netifaces'
'numpy'
'urdfdom'
'tinyxml'
'wxpython'
'qt'
'pyqt'
'poco'
'python-matplotlib'
'qwt_dependency'
'empy'
'gmock'
'nose'
'graphviz'
'curl'
'lz4'
'gl_dependency'
'cv_bridge'
'python-opengl'
'bzip2'
'openssl'
'gpgme'
'eigen'
'sbcl'
'defusedxml'
'opengl'
'libqt5-opengl-dev'
'assimp'
'ogre3d'
'yaml-cpp'
'libqt5-widgets'
'qt_gui_cpp'
'nodelet']


dependency_name_matcher_base = {
    # "python-catkin-pkg": "catkin_pkg",
    "python-catkin-pkg": "", # remove, already in host
    "python-empy": "empy",
    "python": "",
    "python-defusedxml": "defusedxml",
    "python-rosdep": "rosdep",
    "python-rosdistro": "rosdistro",
    "python-numpy": "numpy",
    "python-netifaces": "netifaces",
    "python-rospkg": "rospkg",
    "google-mock": "gmock",
    "python-argparse": "",
    "python-nose": "nose",
    "python-yaml": "pyyaml",
    "libconsole-bridge-dev": "console_bridge",
    "python-imaging": "pillow",
    "python-matplotlib": "matplotlib",
    "python-opengl": "pyopengl",
    "python-cairo": "pycairo",
    "python-pydot": "pydot",
    "libopencv-dev": "opencv",
    "python-opencv": "", # included in opencv
    "python-qt5-bindings-gl": "pyqt",
    # todo fix (prefix all ros packages with ros-?)
    "python-paramiko": "paramiko",
    "libssl-dev": "openssl",
    "python-crypto": "pycrypto",
    "python-gnupg": "python-gnupg",
    "libpoco-dev": "poco",
    # TODO!!!
    "libgpgme-dev": "gpgme",
    "python-wxtools": "wxpython",
    "liburdfdom-dev": "urdfdom",
    "liburdfdom-headers-dev": "urdfdom_headers",
    "libogre-dev": "ogre3d",
    "assimp-dev": "assimp",
    "libqt5-gui": "qt5",
    "libqt5-gui": "",
    "libqt5-core": "",
    "libqt5-opengl": "",
    "libqt5-opengl-dev": "",
    "libqt5-widgets": "",
    "qt5-qmake": "",
    "tango-icon-theme": "",
    "uuid": "libuuid",
    # find out how to add pyside...
    "python-qt5-bindings": "pyqt",
    "qtbase5-dev": "qt"
}

dependency_name_matcher_kinetic = dict(dependency_name_matcher_base)
dependency_name_matcher_kinetic.update({"boost": "boost-cpp"})

dependency_name_matcher_melodic = dict(dependency_name_matcher_base)
dependency_name_matcher_melodic.update({"boost": "boost-cpp"})

dependency_name_matcher = {
    'kinetic': dependency_name_matcher_kinetic,
    'melodic': dependency_name_matcher_melodic
}

def replace_from_dict(pkgs, dist):
    new_pkgs = []
    for p in pkgs:
        if p in dependency_name_matcher[dist.name]:
            new_name = dependency_name_matcher[dist.name][p]
            if len(new_name):
                new_pkgs.append(new_name)
        else:
            if p in get_package_names(dist)[0]:
                p = 'ros-' + p
                p = p.replace('_', '-')
            new_pkgs.append(p)

    return new_pkgs

patches = [os.path.basename(os.path.normpath(p)) for p in glob("./patches/*")]
print(patches)

def find_patches(pkg):
    global patches
    print(pkg)
    print("FINDING PATCHES: ")
    if pkg in patches:
        patch_files = glob("./patches/{}/*.patch".format(pkg))
        patch_names = [os.path.split(p)[1] for p in patch_files]
        print(patch_files, patch_names)
        return (patch_files, patch_names)
    return ([], [])

import hashlib
import shutil
SRC_CACHE = '/home/wolfv/Programs/superflore/superflore/generators/conda/src_cache/'

def get_hash(filename):
    # Python program to find SHA256 hexadecimal hash string of a file

    with open(filename,"rb") as f:
        bytes = f.read() # read entire file as bytes
        readable_hash = hashlib.sha256(bytes).hexdigest();
    return readable_hash

def splitext_tar(name):
    if name.endswith('.tar.gz'):
        return name[:-7], '.tar.gz'
    if name.endswith('.tar.bz2'):
        return name[:-8], '.tar.bz2'
    return os.path.splitext(name)

def get_sha256sum_for_src(url, pkg_name):
    print("Getting URL: ", url)
    ofname = os.path.basename(url)
    name, ext = splitext_tar(ofname)
    final_name = pkg_name + '_' + name
    files = glob(os.path.join(SRC_CACHE, final_name + '_*'))
    if len(files) == 1:
        f = files[0]
        hx = get_hash(f)
        return hx, f

    r = requests.get(url, allow_redirects=True)
    outname = os.path.expanduser(os.path.join(SRC_CACHE, os.path.basename(url)))
    print("WRITING TO ", outname)
    with open(outname, 'wb') as fo:
        fo.write(r.content)

    hx = get_hash(outname)
    mvto = os.path.join(SRC_CACHE, final_name + '_' + hx[:10] + ext)
    shutil.move(outname, mvto)
    return hx, mvto


def find_license(pkg, pkg_name, cache_source):
    src_uri = pkg['tar']['uri']
    if os.path.exists('licencescans/cache.json'):
        with open('licencescans/cache.json', 'r+') as cache:
            try:
                cache = json.load(cache)
                if cache[src_uri]:
                    license = cache[src_uri]['spdx_license_key']
                    license_file = cache[src_uri]['path']
                    return license, license_file
            except:
                pass
    # otherwise...
    subprocess.call(['./find_license.sh', cache_source])
    ofname = os.path.basename(src_uri)
    name, ext = splitext_tar(ofname)
    name = pkg_name + '_' + name
    fs = glob('licencescans/' + name + '*.json')

    def cache_result(license, path):
        if os.path.exists('licencescans/cache.json'):
            with open('licencescans/cache.json', 'r') as cache:
                try:
                    c = json.load(cache)
                except:
                    c = {}
                c[src_uri] = {
                    'spdx_license_key': license,
                    'path': path
                }
        else:
            c = {}
        with open('licencescans/cache.json', 'w+') as cache:
            json.dump(c, cache, indent=4, sort_keys=True)
        return license, path

    with open(fs[0], 'r') as fi:
        license = ''
        J = json.load(fi)
        for f in J['files']:
            if len(f['licenses']) != 1 or f['type'] != 'file':
                continue
            if 'license' in f['path'].lower() and f['licenses'][0]['score'] > 95:
                return cache_result(f['licenses'][0]['spdx_license_key'], '/'.join(f['path'].split('/')[2:]))
            if f['licenses'][0]['score'] > 95:
                return cache_result(f['licenses'][0]['spdx_license_key'], '/'.join(f['path'].split('/')[2:]))
    return cache_result('BSD-3-Clause', 'package.xml')
    # raise RuntimeError('no license discovered')

def _gen_ebuild_for_package(
    distro, pkg_name, pkg, repo, ros_pkg, pkg_rosinstall
):
    # pkg_ebuild = CondaPackage()
    pkg_ebuild = {}

    pkg_ebuild['distro'] = distro.name
    pkg_ebuild['src_uri'] = pkg_rosinstall[0]['tar']['uri']
    print(pkg_rosinstall)

    sha256, cache_file = get_sha256sum_for_src(pkg_ebuild['src_uri'], pkg_name)
    pkg_ebuild['sha256'] = sha256
    pkg_names = get_package_names(distro)
    # print(pkg_names)
    pkg_dep_walker = DependencyWalker(distro)

    pkg_buildtool_deps = pkg_dep_walker.get_depends(pkg_name, "buildtool")
    pkg_build_deps = pkg_dep_walker.get_depends(pkg_name, "build")
    pkg_run_deps = pkg_dep_walker.get_depends(pkg_name, "run")
    pkg_test_deps = pkg_dep_walker.get_depends(pkg_name, "test")

    # add run dependencies\
    pkg_ebuild['run_depend'] = []
    pkg_ebuild['run_depend_withinfo'] = []
    print(distro, pkg_name, pkg, repo, ros_pkg, pkg_rosinstall)
    for rdep in replace_from_dict(pkg_run_deps, distro):
        pkg_ebuild['run_depend_withinfo'].append((rdep, rdep in pkg_names[0]))
        pkg_ebuild['run_depend'].append(rdep)

    # add build dependencies
    pkg_ebuild['build_depend_withinfo'] = []
    pkg_ebuild['build_depend'] = []
    for bdep in replace_from_dict(pkg_build_deps, distro):
        pkg_ebuild['build_depend_withinfo'].append((bdep, bdep in pkg_names[0]))
        pkg_ebuild['build_depend'].append(bdep)

    # add build tool dependencies
    for tdep in replace_from_dict(pkg_buildtool_deps, distro):
        pkg_ebuild['build_depend_withinfo'].append((tdep, tdep in pkg_names[0]))
        pkg_ebuild['build_depend'].append(tdep)

    # add test dependencies
    pkg_ebuild['test_depend'] = []
    for test_dep in replace_from_dict(pkg_test_deps, distro):
        pkg_ebuild['test_depend'].append((test_dep, test_dep in pkg_names[0]))

    patch_files, patch_names = find_patches(pkg_name)

    pkg_ebuild['patches'] = patch_names
    pkg_ebuild['patch_files'] = patch_files

    print("PATCHES: ", pkg_ebuild['patches'])
    print("PATCHES: ", pkg_ebuild['patch_files'])

    # parse throught package xml
    try:
        pkg_xml = ros_pkg.get_package_xml(distro.name)
    except Exception:
        warn("fetch metadata for package {}".format(pkg_name))
        return pkg_ebuild

    pkg = PackageMetadata(pkg_xml)
    pkg_ebuild['upstream_license'] = pkg.upstream_license

    pkg_ebuild['license'], pkg_ebuild['license_file'] = find_license(pkg_rosinstall[0], pkg_name, cache_file)
    pkg_ebuild['description'] = pkg.description
    pkg_ebuild['homepage'] = pkg.homepage
    pkg_ebuild['build_type'] = pkg.build_type
    return pkg_ebuild

def patch_recipe(recipe, patch):
    print("Patching recipe!")
    current_insert = -1
    recipe_lines = recipe.splitlines()

    for line in patch.splitlines():
        if line.startswith('#%'):
            print("Found insertion (", line)
            start_line = line[2:]
            print("looking for ", start_line
                )
            for idx, rl in enumerate(recipe_lines):
                if rl.startswith(start_line):
                    current_insert = idx + 1
                    break
            else:
                raise RuntimeError("Did not find insertion point for ", start_line)
        elif line.startswith('#>'):
            start_line = line[3:]
            if start_line == 'end':
                current_insert = len(recipe_lines)
        else:
            if current_insert != -1:
                recipe_lines.insert(current_insert, line)
                current_insert += 1

    return '\n'.join(recipe_lines)

    return recipe

def conda_recipe(d_entries, patch):
    res = conda_template.render(**d_entries)
    if patch:
        res = patch_recipe(res, patch)
    return res

version_patches = {
    'actionlib': {
        'version': '1.11.15',
        'src_uri': 'https://github.com/ros/actionlib/archive/1.11.15.tar.gz'
    }
}

class conda_installer(object):
    def __init__(self, distro, pkg_name, version, has_patches=False):
        pkg = distro.release_packages[pkg_name]
        repo = distro.repositories[pkg.repository_name].release_repository
        ros_pkg = RosPackage(pkg_name, repo)
        # import IPython; IPython.embed()
        pkg_rosinstall =\
            _generate_rosinstall(pkg_name, repo.url,
                                 get_release_tag(repo, pkg_name), True)

        self.ebuild =\
            _gen_ebuild_for_package(distro, pkg_name,
                                    pkg, repo, ros_pkg, pkg_rosinstall)

        self.patch_ebuild(pkg_name, version)
        self.ebuild['package_name'] = 'ros-' + pkg_name
        self.ebuild['name'] = pkg_name

        # if pkg_name in no_python3:
        #     self.ebuild.python_3 = False

    def patch_ebuild(self, pkg_name, version):
        self.ebuild['version'] = version.replace('-', '.')

        if pkg_name in version_patches:
            patch_dict = version_patches[pkg_name]
            self.ebuild.update(patch_dict)

    def metadata_text(self):
        return self.metadata_xml.get_metadata_text()

    def ebuild_text(self):
        return self.ebuild.get_ebuild_text(org, org_license)


def regenerate_pkg(overlay, pkg, distro, preserve_existing=False):
    pkg_name = 'ros-' + pkg
    version = get_pkg_version(distro, pkg)

    ebuild_name =\
        '/ros-{0}/{1}/meta.yaml'.format(distro.name, pkg_name, version)

    cinst = conda_installer(distro, pkg, version, False)
    cinst.ebuild['ros_distro'] = distro.name
    # find meta.yml patch...
    patch_file = None
    recipe_patch_file = './patches/{}/patch_meta.yaml'.format(pkg)
    if os.path.isfile(recipe_patch_file):
        patch_file = open(recipe_patch_file).read()

    # replace underscores with - in name
    cinst.ebuild['final_package_name'] = cinst.ebuild['package_name'].replace('_', '-')

    rec = conda_recipe(cinst.ebuild, patch_file)

    directory = "./recipes/ros-{}/{}".format(distro.name, pkg)
    make_dir(directory)

    with open(directory + '/meta.yaml', 'w') as fo:
        fo.write(rec)
    with open(directory + '/build.sh', 'w') as fso:
        alternative_build_file = './patches/{pkg}/build.sh'.format(pkg=pkg)
        if os.path.isfile(alternative_build_file):
            build_script = open(alternative_build_file, 'r').read()
        else:
            build_script = open('build_script.tmpl', 'r').read()
        fso.write(build_script)

    if cinst.ebuild['patches']:
        for p in cinst.ebuild['patch_files']:
            shutil.copy(p, directory)
    # try:
    #     current = gentoo_installer(distro, pkg, has_patches)
    #     current.ebuild.name = pkg
    #     current.ebuild.patches = patches
    #     current.ebuild.is_ros2 = is_ros2
    # except Exception as e:
    #     err('Failed to generate installer for package {}!'.format(pkg))
    #     raise e
    # try:
    #     ebuild_text = current.ebuild_text()
    #     metadata_text = current.metadata_text()
    # except UnresolvedDependency:
    #     dep_err = 'Failed to resolve required dependencies for'
    #     err("{0} package {1}!".format(dep_err, pkg))
    #     unresolved = current.ebuild.get_unresolved()
    #     for dep in unresolved:
    #         err(" unresolved: \"{}\"".format(dep))
    #     return None, current.ebuild.get_unresolved()
    # except KeyError as ke:
    #     err("Failed to parse data for package {}!".format(pkg))
    #     raise ke
    # make_dir(
    #     "{}/ros-{}/{}".format(overlay.repo.repo_dir, distro.name, pkg)
    # )
    # success_msg = 'Successfully generated installer for package'
    # ok('{0} \'{1}\'.'.format(success_msg, pkg))

    # try:
    #     ebuild_file = '{0}/ros-{1}/{2}/{2}-{3}.ebuild'.format(
    #         overlay.repo.repo_dir,
    #         distro.name, pkg, version
    #     )
    #     ebuild_file = open(ebuild_file, "w")
    #     metadata_file = '{0}/ros-{1}/{2}/metadata.xml'.format(
    #         overlay.repo.repo_dir,
    #         distro.name, pkg
    #     )
    #     metadata_file = open(metadata_file, "w")
    #     ebuild_file.write(ebuild_text)
    #     metadata_file.write(metadata_text)
    # except Exception as e:
    #     err("Failed to write ebuild/metadata to disk!")
    #     raise e
    return None, None


# def generate_installers(
#     distro_name,             # ros distro name
#     overlay,                 # repo instance
#     gen_pkg_func,            # function to call for generating
#     preserve_existing=True,  # don't regenerate if installer exists
#     *args                    # any aditional args for gen_pkg_func
# ):



if __name__ == '__main__':
    print("Runnign this ")
    to_gen = [
        "rosdep",
        "std_msgs",
        "rospkg",
        "roslz4",
        "rospack",
        "ros_environment",
        "roscpp_core",
        "ros_core",
        "rosunit",
        "ros_comm_msgs",
        "ros_comm",
        "message_runtime",
        "message_generation",
        "genpy",
        "gennodejs",
        "genmsg",
        "genlisp",
        "geneus",
        "gencpp",
        "rosbag_storage",
        "rosconsole_bridge",
        "cmake_modules",
        "catkin_pkg",
        # "catkin",
        "roslib",
        "roslisp",
        "rosclean",
        "common_msgs",
        "rosgraph",
        "rosgraph_msgs",
        "std_srvs",
        "rosbag_migration_rule",
        "rosconsole",
        "rosout",
        "rosmaster",
        "rosmake",
        "rosboost_cfg",
        "rosbash",
        "mk",
        "rosbuild",
        "roslang",
        "roscreate",
        "rosmsg",
        "roslaunch",
        "roswtf",
        "message_filters",
        "topic_tools",
        "xmlrpcpp",
        "ros",
        "rospy",
        "rosbag",
        "rosservice",
        "rosparam",
        "rosnode",
        "rostopic",
        "rostest",
        "rostime",
        "roscpp_traits",
        "cpp_common",
        "roscpp_serialization",
        "roscpp",
        "pluginlib",
        "dynamic_reconfigure",
        "actionlib",
        "actionlib_msgs",
        # new with melodic?
        'nav_msgs',
        'stereo_msgs',
        'diagnostic_msgs',
        'sensor_msgs',
        'shape_msgs',
        'trajectory_msgs',
        'visualization_msgs',
        'geometry_msgs',
        'class_loader',
        # rviz
        # 'media_export',
        # 'resource_retriever',
        # 'python_qt_binding',
        # 'interactive_markers',
        # 'rviz',
        # 'image_transport',
        # 'laser_geometry',
        # 'tf',
        # 'map_msgs',
        # 'tf2_ros',
        # 'angles',
        # 'tf2',
        # 'tf2_py',
        # 'tf2_msgs',
        # 'urdf',
        # nodelet stuff
        # 'nodelet',
        # 'bond',
        # 'bondcpp',
        # 'bondpy',
        # 'smclib',
        # rqt stuff
        # 'gl_dependency',
        # 'qwt_dependency',
        # 'cv_bridge',
        # rqt stuff
        # "qt_dotgraph",
        # "qt_gui",
        # "qt_gui_cpp",
        # "qt_gui_py_common",
        # 'rqt_topic',
        # "rqt_bag",
        # "rqt_bag_plugins",
        # "rqt_console",
        # "rqt_gui",
        # "rqt_gui_cpp",
        # "rqt_gui_py",
        # "rqt_image_view",
        # "rqt_launch",
        # "rqt_logger_level",
        # "rqt_moveit",
        # "rqt_msg",
        # "rqt_nav_view",
        # "rqt_plot",
        # "rqt_pose_view",
        # "rqt_publisher",
        # "rqt_py_common",
        # "rqt_py_console",
        # "rqt_reconfigure",
        # "rqt_dep",
        # "rqt_graph",
        # "rqt_robot_dashboard",
        # "rqt_robot_monitor",
        # "rqt_robot_steering",
        # "rqt_runtime_monitor",
        # "rqt_rviz",
        # "rqt_service_caller",
        # "rqt_shell",
        # "rqt_srv",
        # "rqt_tf_tree",
        # "rqt_top",
        # "rqt_topic",
        # "rqt_web"
        # "rqt_action",

    ]

    # to_gen = ['actionlib', 'catkin']
    # to_gen = ['urdf_parser_plugin']
    # to_gen = ['catkin', 'rospack']
    # to_gen = ['rosdep', 'std_msgs']

    repo_inst = RepoInstance('xtensorgistbucket', 'droneme', repo_dir='../testrepo', do_clone=False)
    generate_installers('melodic', repo_inst, regenerate_pkg, to_gen)
