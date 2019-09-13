#!/usr/bin/env python
# coding: utf-8

# # Generate Graphviz DOT Format Graph for Mercurial Repository
# 
# For a big project, it soon becomes very tedious if not impossible to draw detailed diagram of the Mercurial repository graph depicting the branching, merges, tags, and release.
# 
# TortoiseHg Workbench is a good tool for it. But sometimes, we do need to share the similar information with other teams. As an old saying, one picture equals a thousand words. So a graph of the branches will be much more effective for communication, not saying that project managers, business analysts, etc might not always be able to run HG Workbench.
# 
# This is a small tool to do just that.
# 
# *See [README.md](https://github.com/wy8162/hggraph/blob/master/README.md) for more details.*

# In[61]:


import re
import yaml
import collections
import datetime
import bisect
import os
import glob
import subprocess
from stat import *
import json
from collections import namedtuple
from itertools import groupby


# In[62]:


# Global HG Constants
HG_NO_PARENT_REV = "-1"


# In[63]:


class CSet(object):
    def __init__(self, branch="",children="",user="",date="",message="",tags="",rev="", node="", p1node="", p1rev="", p2node="", p2rev=""):
        self.branch   = branch
        self.children = children
        self.user     = user
        self.date     = date
        self.message  = message
        self.tags     = tags
        self.rev      = rev
        self.node     = node
        self.p1node   = p1node
        self.p1rev    = p1rev
        self.p2node   = p2node
        self.p2rev    = p2rev
        
    def __lt__(self, other):
        return self.rev < other.rev
    
    def __gt__(self, other):
        return self.rev > other.rev
    
    def __str__(self):
        return """{} {} p1={} p2={} c={} {}""".format(self.rev, self.branch, self.p1rev, self.p2rev, self.children, self.tags)
    
    def __repr__(self):
        return """{} {} p1={} p2={} c={} {}""".format(self.rev, self.branch, self.p1rev, self.p2rev, self.children, self.tags)


# In[64]:


class CSetCache(object):
    """
    Servves as a global variable and cache
    """
    allCsets = dict()
    
    @staticmethod
    def hasRev(rev):
        try:
            r = CSetCache.allCsets.get(rev)
            if r != None:
                return True
        except KeyError:
            pass
        return False
    
    @staticmethod
    def add(cset):
        if CSetCache.hasRev(set):
            pass
        else:
            CSetCache.allCsets[cset.rev] = cset
        
    @staticmethod
    def searchCSet(value, attr="rev"):
        """
        By default, it searches for a CSet by revision number. Otherwise, attr parameter is needed to search by
        other parameters like branch
        """
        if attr == "rev":
            return CSetCache.allCsets.get(value)
        for k, v in CSetCache.allCsets.items:
            if getattr(v, attr) == value:
                return v
        return None


# In[65]:


class Utils(object):
    """
    CSet will be used in the following code. It should have the following variables:
        branch
        children
        user
        date
        message
        tags
        rev
        node
        p1node
        p1rev
        p2node
        p2rev
    """

    def __init__(self):
        pass

    @staticmethod
    def hasParents(cset):
        return cset.p1rev != HG_NO_PARENT_REV or cset.p2rev != HG_NO_PARENT_REV

    @staticmethod
    def hasChildren(cset):
        return cset.children
    
    @staticmethod
    def createGraphVizLink(fromCSet, toCSet, label):
        return ['''{}->{}'''.format(fromCSet.rev, toCSet.rev),
                '''r{} -> r{} [label="{}"];'''.format(fromCSet.rev, toCSet.rev, label) ]

    @staticmethod
    def createGraphVizNodeName(cset):
        return "r" + cset.rev
    
    @staticmethod
    def getBranchChildren(cset, branch):
        cl = []
        for c in cset.children.split(" "):
            d = CSetCache.searchCSet(c.split(":")[0])

            # We don't want the child in the same branch
            if d.branch != branch:
                cl.append(d)
        return cl 

    @staticmethod
    def getBranchParent(cset, branch):
        p = CSetCache.searchCSet(cset.p2rev)

        # We don't want the parent in the same branch
        if p.branch != branch:
            return p
        
        p = CSetCache.searchCSet(cset.p1rev)

        # We don't want the parent in the same branch
        if p.branch != branch:
            return p
        return None 
    
    @staticmethod
    def getChildrenRevs(cset):
        if cset.children == "":
            return []

        l = []
        for c in cset.children.split(" "):
            l.append(c.split(":")[0])
        return l
    
    @staticmethod
    def getParentRevs(cset):
        l = []
        if cset.p1rev != HG_NO_PARENT_REV:
            l.append(cset.p1rev)
        if cset.p2rev != HG_NO_PARENT_REV:
            l.append(cset.p2rev)
        return l
    
    @staticmethod
    def createGraphVizNode(type, cset, tagName, shape, style, fillcolor, fontcolor):
        tagTemp = '''{name} [label="{label}" fontcolor={fontcolor} style="{style}" fillcolor={fillcolor} shape={shape}];'''

        name = "r" + cset.rev
        dt   = cset.date.split(" ")[0]

        s = ""
        if cset.tags or type == "LEAF":
            label= """{}\\n{}\\n{}""".format(tagName, dt, cset.rev)
        elif type == "TIP":
            label = "tip"
        elif type == "TAIL":
            label = """{}\\n{}""".format(tagName, cset.rev)
        else:
            label = """{}\\n{}""".format(dt, cset.rev)
        return tagTemp.format(name=name, label=label, fontcolor=fontcolor, style=style, fillcolor=fillcolor, shape=shape)


# In[66]:


class CSetDebug(object):
    """Used to display more details about a change set"""
    def __init__(self, hgCmd):
        self.hgCmd = hgCmd
    
    def retrieveCSet(self, rev):
        me = CSetCache.searchCSet(rev)
        if me == None:
            me = self.hgCmd.getCSetFromRepo(rev)
            if me == None:
                return None
        return me
    
    def formatCSet(self, c):
        if c == None:
            return "None"
        return "br={} rev={} p1={} p2={} c={}".format(c.branch, c.rev, c.p1rev, c.p2rev, c.children)
    
    def showByRev(self, rev):
        me = self.retrieveCSet(rev)
        if me == None:
            print("Wrong revision number: {}".format(rev))
            return
        
        print("children:\n")
        for p in Utils.getChildrenRevs(me):
            print("\t{}".format(self.formatCSet(self.retrieveCSet(p))))
        print("me:\n\t{}".format(self.formatCSet(me)))
        print("parents:\n")
        for p in Utils.getParentRevs(me):
            print("\t{}".format(self.formatCSet(self.retrieveCSet(p))))


# In[67]:


class HgCommand(object):
    def __init__(self, repositoryDir, queryStr):
        self.repo = repositoryDir
        self.query = "branch('re:{}')".format(queryStr) # for HG command
        self.queryStr = queryStr
        self.current = 0
        self.lines = []
        
        # Hg template. Not be changeable by user
        self.template = '"branch":"{branch}","children":"{children}","user":"{author}","date":"{date|isodate}","message":"{firstline(desc)}","tags":"{tags}","rev":"{rev}", "node":"{node}", "p1node":"{p1node}", "p1rev":"{p1rev}", "p2node":"{p2node}", "p2rev":"{p2rev}"\n'

    def run(self):
        """Run hg command to return a tuple of the standard output and standard error output
        Return: True - successfully loaded data
                False - no data loaded
        """
        
        proc = subprocess.Popen(["hg", "log", '-r', self.query, "--template", self.template],
                                cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ)
        (stdoutId, stderrId) = proc.communicate()
        
        if stderrId:
            print("\nThere are errors: {}".format(stderrId))
            return False
        
        self.lines = stdoutId.decode("utf-8").strip().split("\n")
        
        return True if self.lines else False
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current >= len(self.lines):
            raise StopIteration
        else:
            self.current += 1
            while self.current >= 1 and self.current <= len(self.lines):
                m = re.search(self.queryStr, self.lines[self.current - 1])
                if m:
                    return self.lines[self.current - 1]
                self.current += 1
            
            raise StopIteration
    
    def getCSetFromRepo(self, hgrev):
        proc = subprocess.Popen(["hg", "log", '-r', hgrev, "--template", self.template], cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ)
        (stdoutId, stderrId) = proc.communicate()

        if stderrId:
            return None

        res = stdoutId.decode("utf-8").strip()
        x = json.loads("{" + res + "}", object_hook=lambda d: namedtuple('CSet', d.keys())(*d.values()))
        
        CSetCache.add(x)
        
        return x


# In[68]:


class CSetSource(object):
    def __init__(self, fileName, queryStr):
        self.fileName = fileName
        self.queryStr = queryStr
        self.current  = 0
        
        # Each line of Change Set file must follow the following format as defined in the hggraph.yaml file.

    def run(self):
        """
        Return: True - successfully loaded data
                False - no data loaded
        """
        
        with open(self.fileName, 'r') as f:
            data = f.read()
        
        if not data:
            print("\nThere are errors opening file {}".format(self.fileName))
            return False
        
        self.lines = data.strip().split("\n")
        self.current = 0

        return True
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current >= len(self.lines):
            raise StopIteration
        else:
            self.current += 1
            while self.current >= 1 and self.current <= len(self.lines):
                m = re.search(self.queryStr, self.lines[self.current - 1])
                if m:
                    return self.lines[self.current - 1]
                self.current += 1
            
            raise StopIteration
    
    def getCSetFromRepo(self, hgrev):
        s = None
        for l in self.lines:
            if '''"rev":"{}"'''.format(hgrev) in l:
                s = l
                break
                
        if s == None:
            return None
        
        res = s.strip()
        x = json.loads("{" + res + "}", object_hook=lambda d: namedtuple('CSet', d.keys())(*d.values()))
        
        CSetCache.add(x)
        
        return x


# In[69]:


class HgGraph(object):
    """
    Typically, we assume the branching has the following scheme:
    1. It has one main branch.
    2. It has one release branch which branches from the main branch
    3. There are various feature branches and integration branches.
    4. All the other branches should branch based off the main branch directly or indirectly
    
    So, the first change set of all these change sets must belong to the main branch. Typically, as below
    
              /------release branch--------------<tip>
             /        /merge
            /        /
    <o tail>---------main_branch---------------------------------<tip>
                \
                 \-----feature branch----<tip>
    """
    def __init__(self, hgCommand):
        self.hgCommand = hgCommand
        
        # Store tuples of CSet relationship (from_cset, to_cset). There could be more than when we
        # scan different branches. So need to eliminate the dupes as well.
        self.brLinks = dict()
        
        # Stores the tail and tip change sets.
        self.tailCsets = dict()
        self.tipCsets = dict()
        
        # stores CSet from other branch merged to this branch and branched to other branch
        self.leafCsets= []
        
    def _addBrLinkIfNotExist(self, start, end, type):
        key = start.rev + end.rev
        try:
            r = self.brLinks.get(key)
            if r != None:
                return  # Exists. Just return
        except KeyError:
            pass
        self.brLinks[key] = (start, end, type)
    
    def _searchOrGetCSet(self, rev):
        if rev == HG_NO_PARENT_REV:
            return None
        c = CSetCache.searchCSet(rev)
        if c == None:
            c = self.hgCommand.getCSetFromRepo(rev)
        return c
    
    def _addSourceParentBranch(self, b, l, type):
        p1 = self._searchOrGetCSet(l.p1rev)
        p2 = self._searchOrGetCSet(l.p2rev)
        
        if p1 != None and p1.branch != b:
            self._addBrLinkIfNotExist(p1, l, type)
            self.tailCsets[p1.rev] = p1
            
        if p2 != None and p2.branch != b:
            self._addBrLinkIfNotExist(p2, l, type)
            self.tailCsets[p2.rev] = p2

    def _addParentBranch(self, b, l, type):
        p1 = self._searchOrGetCSet(l.p1rev)
        p2 = self._searchOrGetCSet(l.p2rev)
        
        if p1 != None and p1.branch != b:
            self._addBrLinkIfNotExist(p1, l, type)
            self.leafCsets.append(p1)
            
        if p2 != None and p2.branch != b:
            self._addBrLinkIfNotExist(p2, l, type)
            self.leafCsets.append(p2)
            
    def _addBranchTip(self, b, l, type):
        if not self._isTip(l): # Return, this is not the last change set in this branch.
            return
        tip = CSet(rev=l.rev + "Tip", branch="Tip")
        self._addBrLinkIfNotExist(l, tip, type)
        self.tipCsets[tip.rev] = tip
   
    def _addBranchingLinks(self, b, l, type):
        cs = [x.split(":")[0] for x in l.children.split(" ")]
        children = []
        
        for e in cs:
            c = self._searchOrGetCSet(e)
            if c and c.branch != l.branch:
                children.append(c)
        
        if len(children) == 0:
            return
        for c in children:
            self._addBrLinkIfNotExist(l, c, type)
            self.leafCsets.append(c)

    def _isMerge(self, cset):
        if cset.p1rev != HG_NO_PARENT_REV and cset.p2rev != HG_NO_PARENT_REV:
            return True
        if cset.p1rev == HG_NO_PARENT_REV and cset.p2rev == HG_NO_PARENT_REV:
            return False
        p = cset.p1rev if cset.p1rev != HG_NO_PARENT_REV else cset.p2rev
        c = self._searchOrGetCSet(p)
        if c.branch != cset.branch:
            return True
        return False
    
    def _isBranch(self, cset):
        if cset.children == "":
            return False
        
        cs = [x.split(":")[0] for x in cset.children.split(" ")]
        for e in cs:
            c = self._searchOrGetCSet(e)
            if c and c.branch != cset.branch:
                return True

    def _isTip(self, cset):
        if cset.children == "":
            return True
        
        cs = [x.split(":")[0] for x in cset.children.split(" ")]
        for e in cs:
            c = self._searchOrGetCSet(e)
            if c and c.branch == cset.branch:
                return False
        return True
    
    def buildChangeSets(self):
        """
        Takes in the standard out of the HgCommand.run() and build Mercurial change sets
        """

        # Stores unique branch names
        self.branches = set()
        
        # Stores list of CSets keyed by branch names
        self.brs = dict()
        
        csets = []
        
        for cs in self.hgCommand:
            x = json.loads("{" + cs + "}", object_hook=lambda d: namedtuple('CSet', d.keys())(*d.values()))
            self.branches.add(x.branch)
            csets.append(x)
            # Add it to the cache as well
            CSetCache.add(x)

        data = sorted(csets, key=lambda x: x.branch)
        for key, items in groupby(data, lambda x: x.branch):
            l = []
            for e in items:
                if self._isMerge(e) or self._isBranch(e) or self._isTip(e) or e.tags != "":
                    l.append(e)
            self.brs[key] = sorted(l, key=lambda x: x.rev)
        
        # We need to find out the main branch. It must be the one which has the first CSet in the list.
        self.mainBranch = csets[0].branch
        #self.brs[self.mainBranch].insert(0, csets[0])

        # For the first CSet of each branch, we add it's parent branches
        for b, l in self.brs.items():
            self._addSourceParentBranch(b, l[0], "BR")

        # For the last CSet of each branch, we add a tip CSet
        for b, l in self.brs.items():
            self._addBranchTip(b, l[-1], "H")
        
        # Now, we scan all the branches and add the branching or merge links
        for b, l in self.brs.items():
            for i in range(1, len(l)): # Not need to do that for the first CSet
                self._addParentBranch(b, l[i], "M")
 
        for b, l in self.brs.items():
            for i in range(0, len(l)):
                self._addBranchingLinks(b, l[i], "BR")


# In[70]:


class GraphViz(object):
    """
    Generate Graphviz DOT format file.
    
    graphvizTemplate defines Graphviz file format. We use Python string format function to generate the final
    Graphviz DOT file.
    """
    graphvizTemplate = """digraph mecurial {{
    ratio=compress
    rankdir=LR
    bgcolor="#ffffff"
    nodesep=0.1 // increases the separation between nodes
    ranksep=0.1
    node [color=red,fontname=Courier,fontsize=8,width=0.3,height=0.3,shape=circle]
    {nodes}
    {subgraphs}
}}"""
    
    def __init__(self, hgGraph, *initial_data, **kwargs):
        self.hg = hgGraph
        self.brLines = []
        self.branchAndMerges = dict()
        
        self.currentColor = 0
        
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def _getNextColor(self):
        """
        Return a color from the list of self.colors. It will start from 0 and return color sequentially. It will wind back
        to 0 if it reaches the end of the list.
        """
        try:
            color = self.colors[self.currentColor]
        except IndexError:
            self.currentColor = 0
            color = self.colors[self.currentColor]
        
        self.currentColor += 1
        return color

    def _extractReValue(self, rexpr, value):
        """
        Branch names and tags can be very long. To save space and generate a more compact Graphviz graph,
        we need to use a shorter but meaningful name.
        
        We use regular expression to retrieve part of the branch name and tag names.
        """
        try:
            m = re.search(rexpr, value)
            return m.group(2)
        except IndexError:
            pass
        except AttributeError:
            pass
        return value
             
    def dumpGraph(self):
        """
        Generate the Graphviz graph and returns it as a string.
        """
        return GraphViz.graphvizTemplate.format(nodes     = self._generateNodes(),
                                                subgraphs = self._generateSubgraphs()
                                               )
    
    def _generateNodes(self):
        """
        Generate node definitions for 1) all the change sets in the branches; 2) all the tip nodes; 3) all the merge and
        branching change sets; 4) all the change sets from "other" branches.
        """
        nodes = dict() # We need to avoid duplicate nodes

        for k, c in self.hg.tailCsets.items():
            tagName = self._extractReValue(self.branchNamePattern, c.branch)
            nodes[c.rev] = "\t{}\n".format(Utils.createGraphVizNode("TAIL", c, tagName,
                                        self.tailShape,
                                        self.tailStyle,
                                        self.tailFillColor,
                                        self.tailFontColor))

        for k, c in self.hg.tipCsets.items():
            nodes[c.rev] = "\t{}\n".format(Utils.createGraphVizNode("TIP", c, "",
                                        self.tipShape,
                                        self.tipStyle,
                                        self.tipFillColor,
                                        self.tipFontColor))
            
        for b, l in self.hg.brs.items():
            for c in l:
                tagName = self._extractReValue(self.tagNamePattern, c.tags) if c.tags else ""
                fillColor = self.csetFillColor
                fontColor = self.csetFontColor
                if c.tags:
                    fillColor = self.tagFillColor
                    fontColor = self.tagFontColor
                nodes[c.rev] = "\t{}\n".format(Utils.createGraphVizNode("", c, tagName,
                                                                      self.csetShape,
                                                                      self.csetStyle,
                                                                      fillColor,
                                                                      fontColor))
                
        for c in self.hg.leafCsets:
            tagName = self._extractReValue(self.branchNamePattern, c.branch)
            nodes[c.rev] = "\t{}\n".format(Utils.createGraphVizNode("LEAF", c, tagName,
                                                                      self.mbShape,
                                                                      self.mbStyle,
                                                                      self.mbFillColor,
                                                                      self.mbFontColor))

        s = "\n"
        for v in nodes.values():
            s += v

        return s
            
    def _generateSubgraphs(self):
        """
        Generate one subgraph per branch.
        """
        s = ""
        
        brKeys = self._arrangeBranches()
        
        for b in brKeys:
            l = self.hg.brs[b]
            
            subgName  = "cluster_" if self.subgraphCluster else ""
            subgName += b.replace(".", "_").replace("-", "_")
            
            sg  = """edge [color="{color}",fontsize=7,width=0.4,height=0.4, style="{style}"]\n""".format(color=self._getNextColor(), style="bold")
            sg += '''\tsubgraph {name} {{\n\t\tlabel="{label}"\n\t\t'''.format(name=subgName, label= b)
            sg += "style=invis\n\t\t" if self.subgraphCluster else ""
            for c in l:
                sg += "{}; ".format(Utils.createGraphVizNodeName(c))
            sg += "\n"
            
            # Build the graph for each branch first - a straight line. We will only care about the CSet which has multiple parents

            bname = self._extractReValue(self.branchNamePattern, b)
            for i in range(0, len(self.hg.brs[b]) - 1):
                gnodes = Utils.createGraphVizLink(l[i], l[i+1], bname)
                sg += "\t\t{}\n".format(gnodes[1])
                
            s += "{}\n\t}}\n\t".format(sg)
                
        # Go through the merges and branches and create the links.
        s += "edge [color=blue, style=dashed]\n"
        for k, v in self.hg.brLinks.items():
            bname = self._extractReValue(self.branchNamePattern, v[0].branch)
            gnodes = Utils.createGraphVizLink(v[0], v[1], v[2])
            s += "\t{}\n".format(gnodes[1])
            
        return s
    
    def _arrangeBranches(self):
        # Check to see if we need to arrange the branches
        if not self.arrange:
            return self.hg.brs.keys()
        
        l = [(k, v) for k, v in self.hg.brs.items()]
        l = sorted(l, reverse=True, key=lambda x: len(x[1]))

        return [ x[0] for x in l]
        
        #if len(l) > 2:
        #    e0 = l[0]
        #    e1 = l[1]

        #    l[0] = e1
        #    l[1] = e0

        #return [ x[0] for x in l]
        


# In[71]:


"""
The main program
"""

hggraph_yaml = """---
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
# hg log -r "branch('re:JPMC_15R2.+') or branch('re:JPMC_15R3.+') or branch('re:JPMC_15R6.+')" \
--template '"branch":"{branch}","children":"{children}",\
"user":"{author}","date":"{date|isodate}","message":"{firstline(desc)}",\
"tags":"{tags}","rev":"{rev}","node":"{node}","p1node":"{p1node}",\
"p1rev":"{p1rev}","p2node":"{p2node}","p2rev":"{p2rev}"\\n'
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
..."""

info = """
==============================================================================================
A new hggraph configuration file ./hggraph.yaml has been generated.

Before you continue, do the following

Check retrieveChangeSets: "{}"

If it is Yes / True, then you need to provide a file as defined in csetFile: "{}" with all
change sets generated in advanced. The file has to be of change sets with one line per change
set.

If it is No / False, then you need to provide the full path of the local repository in "repo"
variable. Currently, it's value is "{}".

Check the hggraph.yaml for details.
==============================================================================================
"""

def runIt(hgProps):
    if hgProps["retrieveChangeSets"]:
        # Retrieve change sets from a file
        hgCmd = CSetSource(hgProps["csetFile"], hgProps["hgquery"])
    else:
        # Runs Mercurial / TortoiseHg command to get all the changes sets based a the query condition.
        hgCmd = HgCommand(
            hgProps["repo"], # The location of the local Mercurial repository
            hgProps["hgquery"]) # The branch query / filter

    results = hgCmd.run()
    if not results: # Check if there is any error in the standard error output
        exit(1)

    # Now, we build the change sets
    hg = HgGraph(hgCmd)
    hg.buildChangeSets()

    # Now we build the graph and dump it as a string
    gv = GraphViz(hg, hgProps)
    dot = gv.dumpGraph()
    with open(hgProps["graphviz"], 'w', encoding='utf-8') as f:
             f.write(dot)
            
    print("The DOT file has been generated as {}. You can now run Graphviz dot or gvedit or any Graphviz viewer to see the graph.".format(hgProps["graphviz"]))

def main():
    generatedNewHggraphYaml = False
    if not os.path.exists("./hggraph.yaml"):
        generatedNewHggraphYaml = True
        with open("./hggraph.yaml", 'w', encoding='utf-8') as f:
             f.write(hggraph_yaml)

    with open("./hggraph.yaml", 'r') as f:
        hgCfg = yaml.load(f)

    if generatedNewHggraphYaml:
        print(info.format(hgCfg["retrieveChangeSets"], hgCfg["csetFile"], hgCfg["repo"]))

    if not hgCfg["retrieveChangeSets"] and hgCfg["repo"] == "please_replace_repo":
        print("Please make sure you change 'repo' to the correct location of local Mercurial repository and run the application again.")
    else:
        pass
        runIt(hgCfg)


# In[72]:


if __name__ == "__main__":
    main()

