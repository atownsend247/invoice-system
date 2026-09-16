// Build, test, and deploy invoice-system to a Proxmox LXC container.
//
// Assumes a Multibranch Pipeline job (so env.BRANCH_NAME is populated by
// the `when { branch 'main' }` guard below) and a NodeJS tool installation
// in Jenkins named exactly "NodeJS 24.21.0" (Manage Jenkins > Tools),
// pinned to the same version as web/.node-version - see CLAUDE.md's Node
// version gotcha for why that pin matters. Python/uv are bootstrapped
// inline (see the Backend stage) rather than assumed pre-installed on the
// agent. The Deploy stage authenticates with a username/password (via
// `sshpass`, not the SSH Agent plugin - see deploy/deploy.sh), so the
// Jenkins agent itself needs `sshpass` installed (a one-time, manual,
// sudo-requiring step - see docs/deployment.md). See docs/deployment.md
// for the one-time Jenkins/container setup this pipeline assumes, and
// what each DEPLOY_* variable below means.

pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        PATH = "${env.HOME}/.nodenv/bin:${env.HOME}/.nodenv/shims:${env.HOME}/.local/bin:${env.PATH}"

        // -- Proxmox LXC deploy target - fill in for your environment,
        // see docs/deployment.md --
        DEPLOY_HOST        = '192.168.71.25'
        DEPLOY_USER        = 'root'
        // A Jenkins "Secret text" credential holding just the deploy
        // password (DEPLOY_USER above supplies the username) - see the
        // Deploy stage below and docs/deployment.md.
        DEPLOY_CRED_ID     = 'invoices-lxc-password'
        BACKEND_DIR        = '/opt/invoice-system'
        FRONTEND_DIR       = '/var/www/invoice-system'
        BACKEND_SERVICE    = 'invoice-system-api'
        // Baked into the frontend build (VITE_API_BASE_URL) - a relative
        // path, not a full domain, so it works behind the example nginx
        // reverse proxy (deploy/nginx-invoice-system.conf) unchanged
        // regardless of hostname. Same-origin, so no CORS wrinkle either.
        API_PUBLIC_URL     = '/api'
    }

    stages {
        stage('Prereq') {
            steps {
                sh 'eval "$(nodenv init -)" && nodenv versions'
            }
        }

        stage('Checkout') {
            steps {
                script {
                    def scmVars = checkout scm 
                    echo "Branch: ${scmVars.GIT_BRANCH}"
                    env.GIT_LOCAL_BRANCH = scmVars.GIT_BRANCH.replaceFirst('^origin/', '')
                }
            }
        }

        stage('Install uv') {
            steps {
                sh 'curl -LsSf https://astral.sh/uv/install.sh | sh'
            }
        }

        stage('Test') {
            parallel {
                stage('Backend') {
                    steps {
                        sh '''
                            uv sync --dev
                            uv run ruff check .
                            uv run ruff format --check .
                            uv run pytest \
                                --cov=src/invoice_system --cov-report=term-missing \
                                --junitxml=reports/junit-backend.xml
                        '''
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'reports/junit-backend.xml'
                        }
                    }
                }

                stage('Frontend') {
                    steps {
                        dir('web') {
                            sh '''
                                npm ci
                                npm run lint
                                npm test -- --reporter=junit --outputFile=../reports/junit-frontend.xml
                                npm run build
                            '''
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: 'reports/junit-frontend.xml'
                        }
                    }
                }
            }
        }

        stage('End-to-end') {
            // Deliberately after Test, not parallel with it - real
            // Chromium + two real servers is the slow part, only worth it
            // once the fast unit suites are known-good (see
            // docs/testing-and-ci.md).
            steps {
                dir('web') {
                    sh '''
                        npm run test:e2e
                    '''
                }
            }
            post {
                failure {
                    archiveArtifacts artifacts: 'web/playwright-report/**', allowEmptyArchive: true
                }
            }
        }

        stage('Rebuild frontend for deploy') {
            // The Test stage's frontend build used the default (dev-ish)
            // API base URL - rebuild with the production one baked in
            // before shipping it. Only runs when a deploy is actually
            // about to happen, so PRs/other branches don't pay for it.
            when {
                expression { "${env.GIT_LOCAL_BRANCH}" == 'main' }
            }
            environment {
                VITE_API_BASE_URL = "${env.API_PUBLIC_URL}"
            }
            steps {
                dir('web') {
                    sh 'npm run build'
                }
            }
        }

        stage('Deploy') {
            when {
                expression { "${env.GIT_LOCAL_BRANCH}" == 'main' }
            }
            steps {
                // Binds straight to $SSHPASS, not a differently-named
                // variable - `sshpass -e` (used throughout deploy.sh)
                // reads the password from that exact env var name by
                // convention, so no renaming step is needed in between.
                withCredentials([string(credentialsId: env.DEPLOY_CRED_ID, variable: 'SSHPASS')]) {
                    sh 'chmod +x deploy/deploy.sh && ./deploy/deploy.sh'
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
