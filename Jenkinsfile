pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    parameters {
        string(
            name: 'FAULT_MODE',
            defaultValue: '',
            description: 'Optional runtime fault mode for controlled evaluation (for example: 500).'
        )
    }

    environment {
        APP_NAME = 'healdeploy'
        AZURE_CREDENTIALS_ID = 'azure-healdeploy-sp'
        AZURE_TENANT_ID = 'cb5094c4-bbe4-4bfe-bfae-de5cc816dc02'
        AZURE_SUBSCRIPTION_ID = '12a10260-24c6-4c16-a86e-b77fbfef0438'
        AZURE_RESOURCE_GROUP = 'rg-healdeploy-eastasia'
        AZURE_VM_NAME = 'vm-healdeploy-prod'
        ARTIFACT_STORAGE_ACCOUNT = 'hdeployart120381'
        ARTIFACT_CONTAINER = 'releases'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHA = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
                    env.GIT_COMMIT = sh(returnStdout: true, script: 'git rev-parse HEAD').trim()
                    env.GIT_BRANCH = sh(returnStdout: true, script: 'git rev-parse --abbrev-ref HEAD').trim()
                    env.RELEASE_ID = "jenkins-${env.BUILD_NUMBER}-${env.GIT_SHA}"
                    env.APP_VERSION = "v1.0.${env.BUILD_NUMBER}"
                    echo "Deploying branch=$env.GIT_BRANCH commit=$env.GIT_COMMIT release=$env.RELEASE_ID version=$env.APP_VERSION"
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
                        app requirements.txt \
                        deploy/deploy.sh deploy/rollback.sh \
                        deploy/health_check.py deploy/health_policy.json
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
                        usernamePassword(
                            credentialsId: env.AZURE_CREDENTIALS_ID,
                            usernameVariable: 'AZURE_CLIENT_ID',
                            passwordVariable: 'AZURE_CLIENT_SECRET'
                        )
                    ]) {
                        sh '''
                            set -eu
                            FAULT_MODE="${FAULT_MODE:-}"
                            ARCHIVE="$(cat build/archive-path.txt)"
                            BLOB_NAME="${APP_NAME}/${RELEASE_ID}.tar.gz"
                            SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
                            rm -rf artifacts
                            mkdir -p artifacts

                            az login --service-principal \
                                --username "$AZURE_CLIENT_ID" \
                                --password "$AZURE_CLIENT_SECRET" \
                                --tenant "$AZURE_TENANT_ID" \
                                --output none
                            az account set --subscription "$AZURE_SUBSCRIPTION_ID"
                            az vm show \
                                --resource-group "$AZURE_RESOURCE_GROUP" \
                                --name "$AZURE_VM_NAME" \
                                --query name --output tsv >/dev/null

                            az storage blob upload \
                                --account-name "$ARTIFACT_STORAGE_ACCOUNT" \
                                --container-name "$ARTIFACT_CONTAINER" \
                                --name "$BLOB_NAME" \
                                --file "$ARCHIVE" \
                                --auth-mode login \
                                --overwrite \
                                --only-show-errors \
                                --output none

                            set +x
                            SAS_EXPIRY="$(date -u -d '+15 minutes' '+%Y-%m-%dT%H:%MZ')"
                            SAS_TOKEN="$(az storage blob generate-sas \
                                --account-name "$ARTIFACT_STORAGE_ACCOUNT" \
                                --container-name "$ARTIFACT_CONTAINER" \
                                --name "$BLOB_NAME" \
                                --permissions r \
                                --expiry "$SAS_EXPIRY" \
                                --https-only \
                                --auth-mode login \
                                --as-user \
                                --output tsv)"
                            ARTIFACT_URL="https://${ARTIFACT_STORAGE_ACCOUNT}.blob.core.windows.net/${ARTIFACT_CONTAINER}/${BLOB_NAME}?${SAS_TOKEN}"
                            ARTIFACT_URL_B64="$(printf '%s' "$ARTIFACT_URL" | base64 | tr -d '\n')"
                            RUN_SCRIPT="$(mktemp)"
                            cat > "$RUN_SCRIPT" <<'REMOTE_SCRIPT'
set -eu
BASE_DIR="/opt/healdeploy"
REMOTE_DIR="/tmp/healdeploy-${releaseId}"
ARCHIVE="$REMOTE_DIR/${releaseId}.tar.gz"
mkdir -p "$REMOTE_DIR"
ARTIFACT_URL="$(printf '%s' "$artifactUrlB64" | base64 -d)"
curl --fail --location --retry 3 --connect-timeout 15 --max-time 120 \
    "$ARTIFACT_URL" --output "$ARCHIVE"
printf '%s  %s\n' "$sha256" "$ARCHIVE" | sha256sum --check --status
tar -tzf "$ARCHIVE" app/app.py app/dashboard.py app/templates/index.html \
    app/static/css/dashboard.css app/static/js/dashboard.js requirements.txt \
    deploy/deploy.sh deploy/rollback.sh deploy/health_check.py deploy/health_policy.json >/dev/null
install -d -o healdeploy -g healdeploy "$BASE_DIR/deploy"
tar -xzf "$ARCHIVE" -C "$REMOTE_DIR"
install -m 755 "$REMOTE_DIR/deploy/deploy.sh" "$REMOTE_DIR/deploy/rollback.sh" "$BASE_DIR/deploy/"
install -m 644 "$REMOTE_DIR/deploy/health_check.py" "$REMOTE_DIR/deploy/health_policy.json" "$BASE_DIR/deploy/"
sudo "$BASE_DIR/deploy/deploy.sh" "$releaseId" "$appVersion" "$ARCHIVE" "$faultMode" "$gitBranch" "$gitCommit"
printf 'HEALDEPLOY_RUN_COMMAND_RESULT=success\n'
REMOTE_SCRIPT
                            RUN_OUTPUT="$(az vm run-command invoke \
                                --resource-group "$AZURE_RESOURCE_GROUP" \
                                --name "$AZURE_VM_NAME" \
                                --command-id RunShellScript \
                                --scripts @"$RUN_SCRIPT" \
                                --parameters \
                                    "artifactUrlB64=$ARTIFACT_URL_B64" \
                                    "sha256=$SHA256" \
                                    "releaseId=$RELEASE_ID" \
                                    "appVersion=$APP_VERSION" \
                                    "faultMode=$FAULT_MODE" \
                                    "gitBranch=$GIT_BRANCH" \
                                    "gitCommit=$GIT_COMMIT" \
                                --query 'value[].message' \
                                --output tsv)"
                            rm -f "$RUN_SCRIPT"
                            printf '%s\n' "$RUN_OUTPUT" > artifacts/run-command.log
                            printf '%s\n' "$RUN_OUTPUT" | grep -F 'HEALDEPLOY_RUN_COMMAND_RESULT=success'
                            az vm run-command invoke \
                                --resource-group "$AZURE_RESOURCE_GROUP" \
                                --name "$AZURE_VM_NAME" \
                                --command-id RunShellScript \
                                --scripts "cat /opt/healdeploy/shared/health-${RELEASE_ID}.json" \
                                --query 'value[].message' \
                                --output tsv > artifacts/health-"$RELEASE_ID".json
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
