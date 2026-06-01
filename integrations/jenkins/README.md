# SentinelQA Jenkins shared library

This directory ships the SentinelQA Jenkins shared library. Add it to
Jenkins under **Manage Jenkins → Configure System → Global Pipeline
Libraries**:

| Field                  | Value                  |
| ---------------------- | ---------------------- |
| Name                   | `sentinelqa`           |
| Default version        | `v1.5.0`               |
| Source Code Management | Git → this repo        |
| Library Path           | `integrations/jenkins` |

Then import in a Jenkinsfile:

```groovy
@Library('sentinelqa') _

pipeline {
    agent any
    stages {
        stage('SentinelQA audit') {
            steps {
                sentinelAudit(
                    url: 'https://preview-${env.BUILD_TAG}.example.com',
                    mode: 'standard',
                    failUnder: '80'
                )
            }
        }
    }
}
```

The shared library exposes a single step, `sentinelAudit`, that
installs SentinelQA + Playwright, runs `sentinel ci`, archives the
run artifacts, and publishes the JUnit report. Refer to
[`integrations/github/action.yml`](../github/action.yml) for the
canonical input set — the Jenkins step accepts the same parameter
names (camel-cased) plus the optional `pythonVersion` /
`nodeVersion` overrides.
