import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.security.HudsonPrivateSecurityRealm
import jenkins.install.InstallState
import jenkins.model.Jenkins
import jenkins.model.JenkinsLocationConfiguration

def instance = Jenkins.get()
def env = System.getenv()

def location = JenkinsLocationConfiguration.get()
location.setUrl(env['JENKINS_URL'] ?: 'http://localhost:8080/')
location.save()

def adminPassword = env['JENKINS_ADMIN_PASSWORD']
if (adminPassword) {
    def realm = instance.getSecurityRealm()
    if (!(realm instanceof HudsonPrivateSecurityRealm)) {
        realm = new HudsonPrivateSecurityRealm(false)
        instance.setSecurityRealm(realm)
    }
    if (realm.getUser('admin') == null) {
        realm.createAccount('admin', adminPassword)
        println 'HealDeploy: created admin user.'
    }
    def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
    strategy.setAllowAnonymousRead(false)
    instance.setAuthorizationStrategy(strategy)
} else {
    println 'HealDeploy: JENKINS_ADMIN_PASSWORD not set; admin user was not created.'
}

if (!instance.getInstallState().isSetupComplete()) {
    instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)
}

instance.save()
