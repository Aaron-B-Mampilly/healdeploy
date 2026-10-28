import jenkins.model.Jenkins

def source = new File('/usr/share/jenkins/ref/healdeploy-known_hosts')
def targetDir = new File(Jenkins.get().getRootDir(), '.ssh')
def target = new File(targetDir, 'known_hosts')

if (source.exists()) {
    targetDir.mkdirs()
    target.text = source.getText('UTF-8')
    target.setReadable(false, false)
    target.setReadable(true, true)
    target.setWritable(false, false)
    target.setWritable(true, true)
    println "HealDeploy: installed known_hosts at ${target}"
} else {
    println 'HealDeploy: known_hosts source not found.'
}
