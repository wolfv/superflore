from pathlib import Path
import jinja2
import yaml
from conda.models.match_spec import MatchSpec
import networkx as nx

import matplotlib.pyplot as plt
import os, random, time, json
import workerpool

NO_BUILD_LOCAL_PKGS = True

LOGDIR = './fastbuild_logs'

conda_prefix = os.environ['CONDA_PREFIX']
repodata_file = os.path.join(conda_prefix, 'conda-bld', 'linux-64', 'repodata.json')
try:
  with open(repodata_file, 'r') as fin:
    local_repodata = json.load(fin)
except:
  print("Could not find any local packages.")
  NO_BUILD_LOCAL_PKGS = False

def nil_func(*args, **kwargs):
  return "nil"

context = {
  'compiler': nil_func
}

print("Reading all recipes in recipes subfolder.")

all_packages = set()
graph = nx.DiGraph()

class Pkg:
  requirements = set()
  name = ""

  def __init__(self, name, reqs):
    self.name = name
    self.requirements = reqs

  def __repr__(self):
    return f"<{self.name}>"

packages = {}

for filename in Path('ros-melodic').glob('**/meta.yaml'):
  print(filename)

  tpl = jinja2.Template(filename.open().read())
  # print(tpl.render(context))
  # print(f)

  tpl_r = tpl.render(context)
  f = yaml.load(tpl_r)

  name = f['package']['name']
  all_packages.add(name)
  reqs = set()
  print("Name: ", name)
  for section in f['requirements']:
    # if section == 'run':
    #   # need to take care of run as well actually...
    #   pass
    if not f['requirements'][section]:
      continue
    for req in f['requirements'][section]:
      print(req)
      if req == 'nil':
        pass
      else:
        ms = MatchSpec(req)
        # print(ms.name)
        graph.add_edge(name, ms.name)
        reqs.add(ms.name)
  # print(reqs)
  packages[name] = Pkg(name, reqs)

to_remove = []
for node in graph.nodes:
  if node not in all_packages:
    to_remove.append(node)

print("Packages that are not found in generated recipes:\n")
print(to_remove)
print("\n\n")

to_remove = set(to_remove)

if NO_BUILD_LOCAL_PKGS:
  print("Removing previously build packages: ", )
  local_packages = local_repodata.get('packages')
  if local_packages:
    for idx, pkg in local_repodata['packages'].items():
      to_remove.add(pkg['name'])
      print(pkg['name'], end=', ')

    print("\n")

for n in to_remove:
  try:
    graph.remove_node(n)
  except:
    print(n, "not found in graph")

print("Done.")

for p in packages:
  packages[p].requirements -= to_remove

from networkx.drawing.nx_agraph import write_dot, graphviz_layout

write_dot(graph, 'graph.dot')

pos = graphviz_layout(graph, prog='dot')
nx.draw(graph, pos, with_labels=False)
nx.draw_networkx_labels(graph, pos, font_color='#FF0000', font_size=16)
plt.show()

remaining_pkgs = list(nx.topological_sort(graph))[::-1]
print("Topo sorted packages: ", remaining_pkgs)

can_be_built_queue = set()

finished_pkgs, failed_pkgs = set(), set()

def update_can_be_built_queue():
  to_remove = []
  for pkg in remaining_pkgs:
    handle = packages[pkg]

    if len(handle.requirements.difference(set(finished_pkgs))) == 0:
      print(handle, handle.requirements, set(finished_pkgs))
      can_be_built_queue.add(pkg)
      to_remove.append(pkg)

  for rm in to_remove:
    remaining_pkgs.remove(rm)

import time, random, subprocess, os
try:
  os.mkdir(LOGDIR)
except:
  # print("log folder already exists")
  pass

class CondaBuildJob(workerpool.Job):
    def __init__(self, pkg):
        self.pkg = pkg

    def run(self):
      print("Building ... ", self.pkg)
      with open(LOGDIR + '/' + self.pkg + '.txt', 'w') as log_file:
        try:
          subprocess.run('conda build -c conda-forge ./ros-melodic/' + self.pkg,
                         shell=True, check=True, stdout=log_file, stderr=log_file)
        except:
          print("PACKAGE ", self.pkg, "FAILED TO BUILD!")
          failed_pkgs.add(self.pkg)
          return
      finished_pkgs.add(self.pkg)

update_can_be_built_queue()
pool = workerpool.WorkerPool(size=10)

while True:

  for x in can_be_built_queue:
    print("To queue: ", x)
    job = CondaBuildJob(x)
    pool.put(job)

  time.sleep(1)

  print('.', end='')
  can_be_built_queue = set()
  update_can_be_built_queue()
  if len(remaining_pkgs) == 0:
    print("All packages in queue ... waiting now until completion")
    break

  # if len(can_be_built_queue) == 0 and len(remaining_pkgs) != 0 and pool.qsize() == 0:
    # print("WARNING WARNING WARNING\n\ncan not build any further packages")
    # break

pool.shutdown()
pool.wait()

if remaining_pkgs or failed_pkgs:
  print("Failed packages: ", failed_pkgs)
  print("Remaining packages: ", remaining_pkgs)
