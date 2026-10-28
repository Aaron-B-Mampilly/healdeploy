import hudson.plugins.git.BranchSpec
import hudson.plugins.git.GitSCM
import jenkins.model.Jenkins
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import org.jenkinsci.plugins.workflow.job.WorkflowJob

def instance = Jenkins.get()
def jobName = 'healdeploy'

if (instance.getItem(jobName) != null) {
    println "HealDeploy: job ${jobName} already exists."
    return
}

def repoUrl = System.getenv('HEALDEPLOY_REPO_URL') ?: 'https://github.com/Aaron-B-Mampilly/healdeploy.git'
def branch = System.getenv('HEALDEPLOY_BRANCH') ?: '*/main'
def scriptPath = System.getenv('HEALDEPLOY_JENKINSFILE') ?: 'Jenkinsfile'

def job = instance.createProject(WorkflowJob, jobName)
def scm = new GitSCM(
    GitSCM.createRepoList(repoUrl, null),
    [new BranchSpec(branch)],
    false,
    [],
    null,
    null,
    []
)
def definition = new CpsScmFlowDefinition(scm, scriptPath)
definition.setLightweight(true)
job.setDefinition(definition)
job.save()

println "HealDeploy: created job ${jobName} from ${repoUrl} (${branch})."
