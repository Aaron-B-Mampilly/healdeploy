FROM jenkins/jenkins:lts-jdk17

USER root

ARG TERRAFORM_VERSION=1.16.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openssh-client \
        python3 \
        python3-pip \
        python3-venv \
        rsync \
        tar \
        unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin \
    && rm -f /tmp/terraform.zip \
    && chmod 0755 /usr/local/bin/terraform \
    && terraform version

USER jenkins

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY init.groovy.d/ /usr/share/jenkins/ref/init.groovy.d/
COPY known_hosts /usr/share/jenkins/ref/healdeploy-known_hosts
