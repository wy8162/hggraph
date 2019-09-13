#!/usr/bin/env python
# coding: utf-8

# # Jenkins - Monitoring, Building and Running Regressions
# 
# This tool was written to ease my daily job because I need to check the regression tests regularly which totally have around 7000 regression tests. It's really such a hassle to do it manually and frequently.
# 
# This tool will do the following:
# 
# - Run jobs periodically based on cron style configurations
# - Start Jenkins build job to build the jobs
# - Run regressions test jobs
# - Monitor the jobs and re-run those jobs which fail completely or partially
# - Produce reports if requested through
# - Monitor your local Outlook email for commands to start, stop jobs and send reports
# 
# Jenkins will be organized the following hierarchical way
# 
# - Top View: List of Projects
#     - Project View
#         - Tab Views - each view represents a branch, i.e., release branch, main branch, feature branch. In the code below, this is called branch view
#             - List of Jobs for each tab view
#                 - Job details consisting of build status, builds, etc
#                     - There is ONE job for building the application
#                     - There is ONE job for scheduling the regression job runs
# 
# ## Jenkins COLOR DEFINITIONS
# 
# Each Jenkins job can have varous color representing the status of the job. Here is a list of them.
# 
# - RED("red",Messages._BallColor_Failed(), ColorPalette.RED)
# - RED_ANIME("red_anime",Messages._BallColor_InProgress(), ColorPalette.RED)
# - YELLOW("yellow",Messages._BallColor_Unstable(), ColorPalette.YELLOW)
# - YELLOW_ANIME("yellow_anime",Messages._BallColor_InProgress(), ColorPalette.YELLOW)
# - BLUE("blue",Messages._BallColor_Success(), ColorPalette.BLUE)
# - BLUE_ANIME("blue_anime",Messages._BallColor_InProgress(), ColorPalette.BLUE)
# - GREY("grey",Messages._BallColor_Pending(), ColorPalette.GREY)
# - GREY_ANIME("grey_anime",Messages._BallColor_InProgress(), ColorPalette.GREY)
# 
# - DISABLED("disabled",Messages._BallColor_Disabled(), ColorPalette.GREY)
# - DISABLED_ANIME("disabled_anime",Messages._BallColor_InProgress(), ColorPalette.GREY)
# - ABORTED("aborted",Messages._BallColor_Aborted(), ColorPalette.GREY)
# - ABORTED_ANIME("aborted_anime",Messages._BallColor_InProgress(), ColorPalette.GREY)
# - NOTBUILT("nobuilt",Messages._BallColor_NotBuilt(), ColorPalette.GREY)
# - NOTBUILT_ANIME("nobuilt_anime",Messages._BallColor_InProgress(), ColorPalette.GREY)
# 
# # How To Use It
# 
# The tool will generate a YAML configuration file "jenkins.yaml". Refer to the file for more details.
# 
# The jenkins.yaml will have "needChange: Yes". So the first thing to do is:
# 
# - Edit jenkins.yaml file to create profiles. Each profile must have the following parameters:
#     - jenkinServerUrl: "<master URL of Jenkins server>"
#     - userName: "<user name used to login to Jenkins>"
#     - password: "<password used to login to Jenkins>"
#     - buildJob: "<i.e., .*-Build a regular expression to define the pattern of names of build jobs>"
#     - schedulerJob: "<i.e., .*-Scheduler a regular expression to define the pattern of names of scheduler jobs>"
#     - regressionJobFilter: "<i.e., (.*Build$|.*Scheduler$) a regular expression defining non-regression jobs>"
#     - projectName: "<project name - this is bascially Jenkins top level view name>"
#     - branchName: "<tab name or branch name if Jenkins regressions are grouped by branches>"
# 
#     All the parameters can be defined at the top level or defined at the profile level. For example
# 
# ```yaml
#     jenkinServerUrl: "http://jenkins.com/"
#     userName: "myname"
#     password: "mypassword"
# 
#     buildJob: ".*-Build"            # The regular expression patterns, separated by comma, of build jobs
#     schedulerJob: ".*-Scheduler"    # The regular expression patterns, separated by comma,  of scheduler jobs
#     skipJob: ".*-MOD"               # The regular expression patterns, separated by comma, of jobs to be skipped when rerun
# 
#     # The false filter for regressions jobs. Any job whose name does not satisfy the regular expression
#     # is considered as regression jobs.
#     # The patterns, separated by comma.
#     regressionJobFilter: ".*Build$,.*Scheduler$"
# 
#     profiles:
#         ReleaseA:
#             projectName: "projectA"
#             branchName: "Release"
# 
#         BranchA:
#             projectName: "projectA"
#             branchName: "Branch"
# 
#         ReleaseB:
#             projectName: "projectB"
#             branchName: "Release"
#             regressionJobFilter: ".*Build$,.*Scheduler$,.*Others"
# ```
# - Change "needChange: Yes" to "needChange: No"
# - Run the tool as "jenkins_tool.py -p profile_name"
# - If you want to run it from IPython, you can provide the values by changing *argvIPython*. See the Main Program section for details.

# In[1]:


import re
import os
import sys
import getopt
import yaml
import collections
import datetime
import bisect
import os
import glob
import json
import jenkinsapi
import itertools
from tabulate import tabulate
from jenkinsapi.jenkins import Jenkins

from collections import abc

class FrozenJSON:
    """A read-only façade for navigating a JSON-like object
       using attribute notation.
       
       Credit: "O'Reilly Fluent Python", Luciano Ramalho
       http://www.amazon.com/Fluent-Python-Luciano-Ramalho/dp/1491946008
    """
    def __init__(self, mapping):
        self.__data = dict(mapping)

    def __getattr__(self, name):
        if hasattr(self.__data, name):
            return getattr(self.__data, name)
        else:
            return FrozenJSON.build(self.__data[name])

    @classmethod
    def build(cls, obj):
        if isinstance(obj, abc.Mapping):
            return cls(obj)
        elif isinstance(obj, abc.MutableSequence):
            return [cls.build(item) for item in obj]
        else:
            return obj


# In[2]:


class JenkinsServer(object):
    """
    Class representing the Jenkins Server for Branch View
    """

    actionTable = {
        "red" :            { "status" : "Failed"},
        "red_anime" :      { "status" : "InProgress"},
        "yellow" :         { "status" : "Unstable"},
        "yellow_anime" :   { "status" : "InProgress"},
        "blue" :           { "status" : "Success"},
        "blue_anime" :     { "status" : "InProgress"},
        "grey" :           { "status" : "Pending"},
        "grey_anime" :     { "status" : "InProgress"},
        "disabled" :       { "status" : "Disabled"},
        "disabled_anime" : { "status" : "InProgress"},
        "aborted" :        { "status" : "Aborted"},
        "aborted_anime" :  { "status" : "InProgress"},
        "nobuilt" :        { "status" : "NotBuilt"},
        "nobuilt_anime" :  { "status" : "InProgress"}    
    }
    
    commandActor = {
        "build"    : "build",
        "schedule" : "schedule",
        "rerun"    : "runFailedUnstableJobs",
        "failed"   : "failedJobReport",
        "report"   : "jobReport"
    }

    def __init__(self, jkCfg, profile):
        self.jkCfg = jkCfg
        self.profile = profile

        self._jserver = Jenkins(jkCfg.getValue(profile, "jenkinServerUrl"),
                                jkCfg.getValue(profile, "userName"),
                                jkCfg.getValue(profile, "password"))
        self._projectView = self._jserver.views[self.jkCfg.getValue(self.profile, "projectName")]
        self._branchView  = self._projectView.views[self.jkCfg.getValue(self.profile, "branchName")]
    
    def _testConditions(self, rexps, value):
        """
        Test the value against a list of regular expressions.
        Returns True if any of them matches
        """
        if not rexps:
            return True

        tests = [ re.match(m, value) for m in rexps]
        return any(tests)
    
    @property
    def jenkinsServer(self):
        return self._jserver
    
    @property
    def projectView(self):
        return self._projectView
    
    @property
    def branchView(self):
        return self._branchView
    
    def getJobs(self):
        """
        Generator returns all types jobs
        """
        jlist = self._branchView.get_data(self._branchView.python_api_url(self._branchView.baseurl))["jobs"]
        for j in jlist:
            job = FrozenJSON(j)
            yield job
    
    def getRegressionJobs(self, exclude=None):
        """
        Generator returns regressions jobs whose name usually not ends with "Build" or "Scheduler"
        exclude is a list of conditions separated by comma. Specify it to override the value from jenkins.yaml
        """
        if not exclude:
            exclude = self.jkCfg.getValue(self.profile, "regressionJobFilter")

        rexps = exclude.split(",")
        for j in itertools.filterfalse(self._testConditions(rexps, x.name), self.getJobs()):
            yield j
            
    def jobDetails(self, job):
        return (
                job.name, 
                JenkinsServer.actionTable[job.color]["status"], 
                job.lastBuild.number if job.lastBuild is not None else "",
                job.lastStableBuild.number if job.lastStableBuild is not None else "",
                job.healthReport[0].description
               )
    
    def isQueuedOrRunning(self, job):
        j = self._jserver.get_job(job.name)
        return j.is_queued_or_running()
    
    def isFailedOrUnstable(self, job):
        return "red" in job.color or "yellow" in job.color or "notbuilt" in job.color
    
    def isSuccessful(self, job):
        return not self.isFailedOrUnstable(job)
    
    def findJob(self, namePattern):
        """
        Find the first job based on the name pattern in regular expression.
        namePattern is a list of regular expressions separated by comma.
        """
        return next(self.findJobs(namePattern))

    def findJobs(self, namePattern):
        """
        A generator
        Find all the jobs based on the name pattern in regular expression.
        namePattern is a list of regular expressions separated by comma.
        Specify it to override the value from jenkins.yaml
        """
        rexps = namePattern.split(",")
        return (x for x in self.getJobs() if self._testConditions(rexps, x.name))
    
    def getBuildJobs(self, namePattern=None):
        """
        This is to get the job for the Building Job which builds the application.
        de=Nonede=None
        namePattern is a list of regular expressions separated by comma. By default, the build job should
        have a name like ".*-Build", exclude=None, exclude=None
        """
        if not namePattern:
            namePattern = self.jkCfg.getValue(self.profile, "buildJob")
        return self.findJobs(namePattern)
    
    def getSchedulerJobs(self, namePattern=None):
        """
        This is to get the job for the Building Job which builds the application.
        
        namePattern is a list of regular expressions separated by comma. By default, the build job should
        have a name like ".*-Scheduler"
        """
        if not namePattern:
            namePattern = self.jkCfg.getValue(self.profile, "schedulerJob")
        return self.findJobs(namePattern)
    
    def getJobsReportShort(self, onlyFailedJobs=False):
        """
        THIS IS FAST.

        Generator returns list of details of jobs. It consists the folloowing data:
            "Name", "Status", "HealthReport"
            
        If parameter onlyFailedJobs=True is specified, only failed jobs will be reported.
        
        Failed jobs are those with color RED (FAILED) or YELLOW (UNSTABLE)
            
        Use the following to print a pretty-formated report:
            print(tabulate(jserver.getJobsReport(), headers=["Name", "Status", "HealthReport"]))
        """
        jobs = self.getJobs()

        for job in jobs:
            healthReport = "-"
            statusValue = None
            if self.isFailedOrUnstable(job):
                j = self.branchView.get_data(self.branchView.python_api_url(job.url))
                if len(j["healthReport"]) > 0:
                    healthReport = j["healthReport"][0]["description"]
                    statusValue = JenkinsServer.actionTable[job.color]["status"]
            if not onlyFailedJobs:
                yield (job.name, statusValue, healthReport)
            elif self.isFailedOrUnstable(job):
                yield (job.name, statusValue, healthReport)
            else:
                continue

    def jobReport(self):
        print(tabulate(self.getJobsReportShort(), headers=["Name", "Status", "HealthReport"]))
        
    def failedJobReport(self):
        print(tabulate(self.getJobsReportShort(onlyFailedJobs=True), headers=["Name", "Status", "HealthReport"]))

    def anyFailedUnstable(self, skipJob=None):
        """
        True if there is any failed or unstable job
        """
        rexps = None
        if not skipJob:
            skipJob = self.jkCfg.getValue(self.profile, "skipJob")
        
        if skipJob:
            rexps = skipJob.split(",")
        
        jobs = self.getJobs()

        for job in jobs:
            if self.isFailedOrUnstable(job):
                if not self._testConditions(rexps, job.name):
                    return True

        return False
    
    def anyFailedUnstableNotRunningOrQueued(self, skipJob=None):
        """
        True if there is any failed or unstable job which is not queued or running
        """
        rexps = None
        if not skipJob:
            skipJob = self.jkCfg.getValue(self.profile, "skipJob")
        
        if skipJob:
            rexps = skipJob.split(",")
        
        jobs = self.getJobs()

        for job in jobs:
            if self.isFailedOrUnstable(job):
                if not self._testConditions(rexps, job.name):
                    if not self.isQueuedOrRunning(job):
                        return True

        return False
        
    def getJobsSlow(self):
        """
        Generator returns jobs
        """
        for j, url in self._branchView.get_job_dict().items():
            job = FrozenJSON(self._branchView.get_data(self._branchView.python_api_url(url)))
            yield job

    def getJobsReportDetailed(self, onlyFailedJobs=False):
        """
        THIS IS SLOW BECUASE IT CHECKS BUILDS OF EACH JOB

        Generator returns list of details of jobs. It consists the folloowing data:
            "Name", "Status", "Last Build", "Last Stable Build", "Report"
            
        If parameter onlyFailedJobs=True is specified, only failed jobs will be reported.
        
        Failed jobs are those with color RED (FAILED) or YELLOW (UNSTABLE)
            
        Use the following to print a pretty-formated report:
            print(tabulate(jserver.getJobsReport(), headers=["Name", "Status", "Last Build", "Last Stable Build", "Report"]))
        """
        jobs = self.getJobsSlow()

        for job in jobs:
            if not onlyFailedJobs:
                yield self.jobDetails(job)
            elif self.isFailedOrUnstable(job):
                yield self.jobDetails(job)
            else:
                continue

    def startJob(self, job):
        if not self.isQueuedOrRunning(job):
            jobBuild = self.jenkinsServer.get_job(job.name)
            jobBuild.invoke()

    def build(self, verbose=True, namePattern=None):
        """
        Start the building jobs to build the applications.
        verbose=True will print the status.
        """
        for job in self.getBuildJobs(namePattern):
            if verbose:
                print("Starting building job: {}".format(job.name))
            self.startJob(job)

    def isBuilding(self, namePattern=None):
        """
        Return True if any build job is running
        """
        for job in self.getBuildJobs(namePattern):
            if self.isQueuedOrRunning(job):
                return True
        return False
            
    def schedule(self, verbose=True, namePattern=None):
        """
        Start the scheduling jobs to run the regressions jobs.
        verbose=True will print the status.
        """
        for job in self.getSchedulerJobs(namePattern):
            if verbose:
                print("Starting schedule job: {}".format(job.name))
            self.startJob(job)

    def isScheduling(self, namePattern=None):
        """
        Return True if any scheduling job is running
        """
        for job in self.getSchedulerJobs(namePattern):
            if self.isQueuedOrRunning(job):
                return True
        return False
            
    def runFailedUnstableJobs(self, verbose=True, skipJob=None):
        """
        Start failed or unstable jobs. Provide regular expressions to exclude any job from being started
        skipJob, regular expressions separated by comma define the jobs to be skipped
        """
        if not skipJob:
            skipJob = self.jkCfg.getValue(self.profile, "skipJob")
        rexps = skipJob.split(",")
        jobs = self.getJobsReportShort(onlyFailedJobs=True)
        for job in jobs:
            j = collections.namedtuple("JobTemp", ("name", "status", "healthReport"))(*job)
            if not self._testConditions(rexps, j.name):
                if verbose:
                    print("Starting job: {}".format(j.name))
                self.startJob(j)
                
    def runIt(self, func):
        f = getattr(self, JenkinsServer.commandActor[func], None)
        if f is not None:
            f()
        else:
            raise ValueError("ERROR: Bad function name '{} = {}'".format(func, JenkinsServer.commandActor[func]))


# In[3]:


"""
The main program
"""

jenkins_yaml = """---
# Jenkins configuraions

# If this value is Yes, this application will not run.
# So change the values below and then change needChange to "No"
needChange: Yes

#------------------------------------------------------
# Values for variables not defined at the profile level
#------------------------------------------------------
# Jenkins' master URL
jenkinServerUrl: "http://jenkinsmasterprod.dovetail.net/jenkins/"

# User name and password to login to Jenkins master server
userName: "<username>"
password: "<password>"

buildJob: ".*-Build"            # The regular expression patterns, separated by comma, of build jobs
schedulerJob: ".*-Scheduler"    # The regular expression patterns, separated by comma,  of scheduler jobs
skipJob: ".*-MOD"               # The regular expression patterns, separated by comma, of jobs to be skipped when rerun

# The false filter for regressions jobs. Any job whose name does not satisfy the regular expression
# is considered as regression jobs.
# The patterns, separated by comma.
regressionJobFilter: ".*Build$,.*Scheduler$"

#------------------------------------------------------
# Values defined at the top level will be overridden by
# the values defined in profile level
#------------------------------------------------------
profiles:
    Release:
        projectName: "<project>"        # Main Jenkins' main view, mostly one per project
        branchName: "Release"           # Jenkins sub-views, mostly one per mercurial branch

    Branch:
        projectName: "<project>"        # Main Jenkins' main view, mostly one per project
        branchName: "Branch"            # Jenkins sub-views, mostly one per mercurial branch
..."""

info = """
==============================================================================================
A new Jenkins configuration file ./jenkins.yaml has been generated.

Before you continue, modify the file accordingly first.

Check the jenkins.yaml for details.
==============================================================================================
"""

class JKCfg(object):
    commandActor = {
        "list"    : "listProfiles"
    }

    def __init__(self, jkCfg):
        self._jkCfg = jkCfg
        
    def getValue(self, profile, name):
        if not profile:
            return self._jkCfg.get(name, None)

        pd = self._jkCfg["profiles"][profile]
        defaultValue = self._jkCfg[name] if name in self._jkCfg else None
        return pd.get(name, defaultValue)
    
    def listProfiles(self, printList=True):
        """
        if printList = True, the list will be printed out to standard output.
        Return a list of tuples (profile name, project name, branch name)
        """
        ls = []
        for k in self._jkCfg["profiles"].keys():
            ls.append((k, self.getValue(k, "projectName"), self.getValue(k, "branchName")))
            
        if printList:
            print(tabulate(sorted(ls), headers=["profile", "project name", "branch name"]))
        return ls
    
    def runIt(self, func):
        f = getattr(self, JKCfg.commandActor[func], None)
        if f is not None:
            f()
        else:
            raise ValueError("ERROR: Bad function name '{} = {}'".format(func, JKCfg.commandActor[func]))
        

def runIt(jkCfg, profile, options, cfgOptions):
    for cmd in cfgOptions:
        jkCfg.runIt(cmd)

    if profile is None:
        return

    for p in profile.split(","):
        jserver = JenkinsServer(jkCfg, p)
        for cmd in options:
            jserver.runIt(cmd)

def main(profile, options, cfgOptions):

    generatedNewYaml = False
    if not os.path.exists("./jenkins.yaml"):
        generatedNewYaml = True
        with open("./jenkins.yaml", 'w', encoding='utf-8') as f:
             f.write(jenkins_yaml)

    with open("./jenkins.yaml", 'r') as f:
        jkCfg = JKCfg(yaml.load(f))

    if generatedNewYaml:
        print(info)
        
    if jkCfg.getValue(None, "needChange"):
        print("It seems that you've not change the Jenkins configuration jenkins.yaml yet.\nPlease do so and try it again.")
    else:
        runIt(jkCfg, profile, options, cfgOptions)


# # Main Program

# In[4]:


def run_from_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False

def displayHelpAndExit():
    print(
'''
Usage:

    python jenkins_tool.py -p profile_name
    Options:
        -p --profile    profile names separated by comma
        -r --run        re-run all failed and unstable jobs
        -b --build      build the application
        -s --schedule   schedule all regressions to run
        -f --failed     list failed jobs
        -t --report     list all the jobs
        -l --list       list all the profiles available
'''
)

#argvIPython = ["-lfr", "-p", "16R1.16R1_PE.1805.1806"]
argvIPython = ["-lfr", "-p", "17R1.7.Branch"]
    
if __name__ == '__main__':
    profile = None
    options = []
    cfgOptions = []

    args = argvIPython if run_from_ipython() else sys.argv[1:]
    
    try:
        opts, args = getopt.getopt(args,"hbsrftlp:",["help", "build", "schedule", "rerun", "failed", "report", "list", "profile="])
    except getopt.GetoptError:
        displayHelpAndExit()
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            profile = None
        elif opt in ("-p", "--profile"):
            profile = arg
        elif opt in ("-b", "--build"):
            options.append("build")
        elif opt in ("-s", "--schedule"):
            options.append("schedule")
        elif opt in ("-r", "--rerun"):
            options.append("rerun")
        elif opt in ("-f", "--failed"):
            options.append("failed")
        elif opt in ("-t", "--report"):
            options.append("report")
        elif opt in ("-l", "--list"):
            cfgOptions.append("list")
            
    if not profile and not cfgOptions:
        displayHelpAndExit()
    else:
        main(profile, options, cfgOptions)
        print("\nDone")


# # Test Areas - Remove the below if export it to python

# In[5]:


ipythonTest = False


# In[6]:


if ipythonTest:
    with open("./jenkins.yaml", 'r') as f:
        jkCfg_ = JKCfg(yaml.load(f))

    jserver_ = JenkinsServer(jkCfg_, "16R1.Branch")

