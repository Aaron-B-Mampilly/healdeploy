pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    parameters {
        string(
            name: 'FAULT_MODE',
            defaultValue: '',
            description: 'Optional runtime fault mode for controlled evaluation (for example: 500).'
        )
    }

    environment {
        VM_HOST = '20.205.103.245'
        APP_NAME = 'healdeploy'
        SSH_CREDENTIALS_ID = 'healdeploy-ssh-key'
        KNOWN_HOSTS = '/var/jenkins_home/.ssh/known_hosts'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHA = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    env.RELEASE_ID = "jenkins-${env.BUILD_NUMBER}-${env.GIT_SHA}"
                    env.APP_VERSION = "v1.0.${env.BUILD_NUMBER}"
                }
            }
        }

        stage('Test') {
            steps {
                sh '''
                    set -e
                    mkdir -p build
                    python3 -m venv .venv-ci
                    .venv-ci/bin/python -m pip install --upgrade pip
                    .venv-ci/bin/pip install -r requirements.txt
                    .venv-ci/bin/python -m pytest -v --junitxml=build/test-results.xml
                '''
            }
            post {
                always {
                    junit testResults: 'build/test-results.xml', allowEmptyResults: true
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                sh '''
                    set -e
                    if command -v terraform >/dev/null 2>&1; then
                        terraform -chdir=terraform fmt -check -recursive
                        terraform -chdir=terraform init -backend=false -input=false
                        terraform -chdir=terraform validate
                    else
                        echo "Terraform is not installed in this Jenkins image; skipping validation."
                    fi
                '''
            }
        }

        stage('Package') {
            steps {
                sh '''
                    set -e
                    mkdir -p build
                    rm -f build/*.tar.gz
                    ARCHIVE="build/${APP_NAME}-${RELEASE_ID}.tar.gz"
                    tar -czf "$ARCHIVE" \
                        --exclude='app/__pycache__' \
                        --exclude='*.pyc' \
                        app requirements.txt
                    echo "$ARCHIVE" > build/archive-path.txt
                    ls -lh "$ARCHIVE"
                '''
                archiveArtifacts artifacts: 'build/*.tar.gz', fingerprint: true
            }
        }

        stage('Deploy and Verify') {
            steps {
                script {
                    withCredentials([
                        sshUserPrivateKey(
                            credentialsId: env.SSH_CREDENTIALS_ID,
                            keyFileVariable: 'SSH_KEY',
                            usernameVariable: 'SSH_USER'
                        )
                    ]) {
                        sh '''
                            set -u
                            FAULT_MODE="${FAULT_MODE:-}"
                            ARCHIVE="$(cat build/archive-path.txt)"
                            REMOTE_DIR="/tmp/healdeploy-${BUILD_NUMBER}"
                            SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS -o ConnectTimeout=20"

                            rm -rf artifacts
                            mkdir -p artifacts

                            ssh $SSH_OPTS "$SSH_USER@$VM_HOST" "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR"
                            scp $SSH_OPTS "$ARCHIVE" deploy/deploy.sh deploy/rollback.sh deploy/health_check.py deploy/health_policy.json "$SSH_USER@$VM_HOST:$REMOTE_DIR/"

                            set +e
                            ssh $SSH_OPTS "$SSH_USER@$VM_HOST" "sudo -n install -d -o healdeploy -g healdeploy /opt/healdeploy/deploy && sudo -n install -m 755 $REMOTE_DIR/deploy.sh $REMOTE_DIR/rollback.sh /opt/healdeploy/deploy/ && sudo -n install -m 644 $REMOTE_DIR/health_check.py $REMOTE_DIR/health_policy.json /opt/healdeploy/deploy/ && sudo -n /opt/healdeploy/deploy/deploy.sh '$RELEASE_ID' '$APP_VERSION' '$REMOTE_DIR/$(basename "$ARCHIVE")' '$FAULT_MODE'"
                            DEPLOY_RC=$?
                            set -e

                            scp $SSH_OPTS "$SSH_USER@$VM_HOST:/opt/healdeploy/shared/health-$RELEASE_ID.json" artifacts/ 2>/dev/null || true
                            if [ "$DEPLOY_RC" -ne 0 ]; then
                                scp $SSH_OPTS "$SSH_USER@$VM_HOST:/opt/healdeploy/shared/incident_report.json" artifacts/incident_report.json 2>/dev/null || true
                                scp $SSH_OPTS "$SSH_USER@$VM_HOST:/opt/healdeploy/shared/health-rollback-$RELEASE_ID.json" artifacts/ 2>/dev/null || true
                            fi
                            exit $DEPLOY_RC
                        '''
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/**', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        success {
            echo "HealDeploy release ${env.RELEASE_ID} (${env.APP_VERSION}) deployed and verified."
        }
        failure {
            echo "HealDeploy release ${env.RELEASE_ID} failed. Check the incident report artifact for recovery details."
        }
        always {
            archiveArtifacts artifacts: 'build/test-results.xml', allowEmptyArchive: true
        }
    }
}
