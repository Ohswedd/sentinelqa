// SentinelQA — Jenkins shared-library step (v1.5.0).
//
// Usage (in a Jenkinsfile):
//
//   @Library('sentinelqa') _
//   pipeline {
//     agent any
//     stages {
//       stage('SentinelQA audit') {
//         steps {
//           sentinelAudit url: 'https://preview-${env.BUILD_TAG}.example.com',
//                         mode: 'standard',
//                         failUnder: '80'
//         }
//       }
//     }
//   }
//
// Required env vars:
//   SENTINELQA_URL     (optional fallback for the `url` parameter)
//   SENTINELQA_VERSION (optional pin)
//
// The shared library is registered via Manage Jenkins → Configure System
// → Global Pipeline Libraries, pointing at this repo.

def call(Map params = [:]) {
    def url        = params.url        ?: env.SENTINELQA_URL
    def mode       = params.mode       ?: 'standard'
    def diff       = params.diff       ?: ''
    def failUnder  = params.failUnder  ?: ''
    def version    = params.version    ?: env.SENTINELQA_VERSION ?: ''
    def pythonVer  = params.pythonVersion ?: '3.12'
    def nodeVer    = params.nodeVersion   ?: '20'

    if (!url?.trim()) {
        error 'sentinelAudit: `url` (or env SENTINELQA_URL) is required.'
    }

    withEnv(["SENTINELQA_CI=1"]) {
        sh """
            set -euo pipefail
            python --version || true
            node --version || true
            if [ -n "${version}" ]; then
                python -m pip install --upgrade pip
                python -m pip install "sentinelqa==${version}"
            fi
            npx --yes playwright install --with-deps chromium
            args="--config sentinel.config.yaml --ci --mode ${mode} --url ${url}"
            if [ -n "${diff}" ]; then args="\${args} --diff ${diff}"; fi
            if [ -n "${failUnder}" ]; then args="\${args} --fail-under ${failUnder}"; fi
            sentinel ci \${args}
        """
    }

    archiveArtifacts allowEmptyArchive: true,
                     artifacts: '.sentinel/runs/**',
                     fingerprint: false
    junit allowEmptyResults: true,
          testResults: '.sentinel/runs/*/junit.xml'
}
