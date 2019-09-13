# hggraph
## A Python tool to generate Graphviz graph for Mercurial branches.

This is a tool written in Python used to generate a Graphviz DOT file for the Mercurial repository branches. It can run under Jupyter or IPython or command line.

To render the DOT file, [Graphviz](http://www.graphviz.org/) tool is needed.

## Generate Graphviz DOT Format Graph for Mercurial Repository

For a big project, it soon becomes very tedious if not impossible to draw detailed diagram of the Mercurial repository graph depicting the branching, merges, tags, and release.

TortoiseHg Workbench is a good tool for it. But sometimes, we do need to share the similar information with other teams. As an old saying, one picture equals a thousand words. So a graph of the branches will be much more effective for communication, not saying that project managers, business analysts, etc might not always be able to run HG Workbench.

This is a small tool to do just that.

## Assumptions

Typically, we assume the branching has the following scheme:

1. It has one main branch.
2. It has one release branch which branches from the main branch
3. There are various feature branches and integration branches.
4. All the other branches should branch based off the main branch directly or indirectly

So, the first change set of all these change sets must belong to the main branch. Typically, as below
<pre>
          /------release branch--------------[tip]
         /        /merge
        /        /
[tail]---------main_branch---------------------------------[tip]
            \
             \-----feature branch----[tip]
</pre>

## Specifications

* Dashed lines are used to represent branching and merging. For merge, it'll be labeled "M". For branching, it is "BR".
* Solid lines are the branches. Different branches will use different colors. But the color will be repeated if there are more than 18 branches. Branch links will be labeled with the "meaningful" branch name. By meaningful branch name, it means part of the full branch name.
* Tagged change sets will be displayed as white text with green background. These are usually the actual release, based my practice.
* Label "H" means it is the head and tip.

But all these parameters can be changed in a configuration file hggraph.yaml. It should be easy to change because the vraiable names are self-descriptive.

## How to Use

### What Are Needed

You need to make sure TortoiseHg is installed and can be used. To display the Graphviz DOT file, you also need to install the Graphviz application. You can use dot or gvedit to display or export SVG, JPG, PNG files. See graphviz.org for more details.

### How to Use

There are two ways to run:

* Run it as a Python from command line
* Run it from iPython Notebook

When it runs the first, it'll check if there is a file called "hggraph.yaml" in the current directory. If not, it will generate one and save it in the current directory, expecting you to change at least the repository location.

You must specify the correct repos in order for hggraph to run correctly.

A sample hggraph.yam is as below.

```yaml
---
# hggraph configuraions

# The output DOT Graphviz file
graphviz: "./graphviz.gv"

# Specify if hggraph needs to retrieve the change set information from the repository directory.
# Yes - needs to read repository directly. The variable "repo" must be specified.
# No  - hggraph will read change sets from a file specified by variable "csetFile".

retrieveChangeSets: Yes
# The location of the local Mercurial repository directory
# This must be replaced with a correct full directory path of the local Mercurial repository.
repo: "please_replace_repo"

# The Change Set (CSET) file must be produced by the following command:
# hg log -r "branch('re:J.+') or branch('re:J.+') or branch('re:J.+')" \
# --template '"branch":"{branch}","children":"{children}",\
# "user":"{author}","date":"{date|isodate}","message":"{firstline(desc)}",\
# "tags":"{tags}","rev":"{rev}","node":"{node}","p1node":"{p1node}",\
# "p1rev":"{p1rev}", "p2node":"{p2node}", "p2rev":"{p2rev}"\n'
csetFile: "./repocsets.txt"

# The query used by hg command, like hg log -r "branch('re:<hgquery>')"
hgquery: ".+15R3.*"

# Regular expression. For long branch name, we should extract part of the branch name so that the graph will be compact.
# The regular expression must be divided into three groups. The second group will be extracted as the tag name.
branchNamePattern:  '(\w+_)(\d+.+)(_[a-zA-Z]+)'

# Regular expression. Usually, a branch will be tagged if it is a release. This is to extract part of the tag name.
# The regular expression must be divided into three groups. The second group will be extracted as the tag name.
tagNamePattern:  '(\w+_)(\d+.+)(_[a-zA-Z]+)'

# The following are the attributes of various change sets. See graphviz.org for more details.
subgraphCluster: Yes
arrange: Yes
rank: Yes

tipShape :  "diamond"
tipStyle :  "rounded,filled"
tipFillColor:  "gray"
tipFontColor:  "black"

tailShape:  "box"
tailStyle:  "rounded,filled"
tailFillColor:  "gray"
tailFontColor:  "black"

csetShape:  "box"
csetStyle:  "rounded,filled"
csetFillColor:  "lightcyan"
csetFontColor:  "black"

tagFillColor :  "limegreen"
tagFontColor :  "white"

mbShape:  "box"
mbStyle:  "rounded,filled"
mbFillColor:  "white"
mbFontColor:  "black"

# Color pool for the branch lines.
colors:  ["deepskyblue2", "aquamarine", "chartreuse", "crimson", "darkgreen", "cyan", "greenyellow", "green3", "brown1", "green4", "magenta3", "magenta4", "maroon", "olivedrab3", "olivedrab4", "orange", "yellow4", "aqua"]
...
```

## Utility for Debug

Frquently, you might want to figure out what could go wrong and need to examine some change sets and the relationship.

The utility class CSetDebug is used to display the parent and children change set details. This can help developer to visually examine the relationship of various change sets.

dbg = CSetDebug(hgCmd)
dbg.showByRev("30223")

Sample output:

```
children:

	br=15R3.x_RELEASE_BRANCH rev=30230 p1=30223 p2=-1 c=30231:339797ac3ff6
me:
	br=15R3.x_RELEASE_BRANCH rev=30223 p1=30218 p2=-1 c=30230:ce89185fe1fd
parents:

	br=15R3.x_RELEASE_BRANCH rev=30218 p1=30215 p2=-1 c=30223:333a3b67d734 30224:31ffb6a79538 30225:4c34d82f961b 30227:cd65a634087e 30246:887d1d99f428 30248:46fc584ac2ae
```

## Sample graphs are as below.

![Sample 1](https://github.com/wy8162/hggraph/blob/master/Sample.PNG)
![Sample 2](https://github.com/wy8162/hggraph/blob/master/Sample_15R3x.png)
![Sample 3](https://github.com/wy8162/hggraph/blob/master/Sample_15R3y.png)
