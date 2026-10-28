import com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.domains.Domain
import jenkins.model.Jenkins

def keyFile = new File('/run/secrets/healdeploy_rsa')
if (!keyFile.exists()) {
    println 'HealDeploy: SSH key secret not mounted; skipping credential creation.'
    return
}

def store = Jenkins.get().getExtensionList(SystemCredentialsProvider).get(0).getStore()
def domain = Domain.global()
def existing = store.getCredentials(domain).find { it.id == 'healdeploy-ssh-key' }
if (existing != null) {
    println 'HealDeploy: SSH credential already exists.'
    return
}

def privateKey = new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource(keyFile.getText('UTF-8'))
def credential = new BasicSSHUserPrivateKey(
    CredentialsScope.GLOBAL,
    'healdeploy-ssh-key',
    'azureuser',
    privateKey,
    '',
    'HealDeploy Azure VM SSH key'
)

store.addCredentials(domain, credential)
println 'HealDeploy: SSH credential created.'
