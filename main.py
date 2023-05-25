import os
import requests as request_client
import json
import subprocess
from threading import Thread

from flask import Flask, request, render_template
from flask_cors import CORS

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

OVERRIDES = {
    'project-anemone': '/',
    'project-bluedaboudidaboudadaboudidabouda': '/',
    'project-crocodiles': '/',
    'project-dtf': '/www/',
    'project-e_tsuki': '/',
    'project-fennec': '/',
    'project-g-unit': '/template_django_vue/',
    'project-helloworld': '/',
    'project-ilicoptere': '/django-vue/',
    'project-jungle': '/',
    'project-komanodragons': '/django-vue/',
    'project-lima': '/',
    'project-maverick': '/',
    'project-nova': '/template-django-vue-main/',
    'project-omega': '/Omega/',
    'project-pepperoni': '/Project-Pepperoni/',
    'project-qarbon': '/'
}
app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.json["repository"]["name"].startswith("project") and request.json["ref"] == "refs/heads/main":
        commit_id = None
        if request.json["head_commit"]:
            commit_id = request.json["head_commit"]["id"]
        repo = request.json["repository"]["name"]
        org = request.json["repository"]["organization"]
        override = OVERRIDES.get(repo, "")
        Thread(target=build, kwargs={
               "org": org, "repo": repo, "override": override, "commit_id": commit_id}).start()

    return 'OK'


@app.route('/build', methods=['GET'])
def build_sync():
    build(**request.args.to_dict())
    return f'OK {request.args.to_dict()}'


def build(org, repo, override='', commit_id=None):
    repo_lower = repo.lower().replace('project-', '').replace('_', '-')

    image_name = repo
    workdir = f'/app/data/{repo}{override[:-1]}'

    subprocess.run(['docker', 'rm', '-f', repo])
    subprocess.run(['docker', 'rmi', '-f', image_name])

    app.logger.info(f'DOWNLOAD {repo} STARTED')
    # Get code
    subprocess.run(['sh', '-c', f'cd data && \
    rm -rf {repo} && \
    mkdir {repo} && \
    cd {repo} && \
    curl -SsL -H "Accept: application/vnd.github+json" -H \'Authorization: Bearer {GITHUB_TOKEN}\' \
        -H \'Cache-Control: no-cache\' https://api.github.com/repos/{org}/{repo}/tarball | tar xz --strip-components=1'])

    # Copy the Dockerfile into the repository
    subprocess.run(['cp', '/app/build_templates/Build.Dockerfile',
                   f'./Dockerfile'], cwd=workdir)
    subprocess.run(['cp', '/app/build_templates/dockerignore',
                   f'./.dockerignore'], cwd=workdir)
    subprocess.run(['cp', '/app/build_templates/prod.py',
                   f'./prod.py'], cwd=workdir)

    # Build the Docker image and save the logs to a file
    app.logger.info(f'BUILD {repo} STARTED')
    result = subprocess.run(
        ['docker', 'build', '-t', image_name, '.'], capture_output=True, cwd=workdir)
    with open(f'./data/{repo}{override}/build.log', 'wb') as f:
        f.write(result.stdout)
        f.write(result.stderr)

    def labels(repo_lower, port):
        return [
            "-l", "traefik.enable=true",
            "-l", "traefik.docker.network=web",
            "-l", "traefik.http.middlewares.https_redirect.redirectscheme.scheme=https",
            "-l", "traefik.http.middlewares.https_redirect.redirectscheme.permanent=true",
            "-l", f"traefik.http.services.{repo_lower}.loadbalancer.server.port={port}",
            "-l", f"traefik.http.routers.{repo_lower}.rule=Host(`{repo_lower}.rxq.ch`)",
            "-l", f"traefik.http.routers.{repo_lower}.entrypoints=web",
            "-l", f"traefik.http.routers.{repo_lower}.middlewares=https_redirect",
            "-l", f"traefik.http.routers.{repo_lower}_secured.rule=Host(`{repo_lower}.rxq.ch`)",
            "-l", f"traefik.http.routers.{repo_lower}_secured.entrypoints=websecure",
            "-l", f"traefik.http.routers.{repo_lower}_secured.tls=true",
            "-l", f"traefik.http.routers.{repo_lower}_secured.tls.certresolver=myresolver",
            "--network", "web"
        ]
    state = 'failure'
    if result.returncode == 0:
        app.logger.info(f'BUILD {repo} SUCCESS')
        result = subprocess.run(['docker', 'run', '-d', '--rm', '--name', repo, '-e',
                                 f'DJANGO_ALLOWED_HOST=https://{repo_lower}.rxq.ch']
                                + labels(repo_lower, 8000) + [image_name])
        state = 'success'
    else:
        app.logger.info(f'BUILD {repo} FAILED')
        # serve logs with Nginx
        subprocess.run(
            ['sh', '-c', 'cp /app/build_templates/Nginx.Dockerfile ./Dockerfile && cp /app/build_templates/index.html ./index.html'], cwd=workdir)
        subprocess.run(['docker', 'build', '-t', image_name,
                       '.'], capture_output=True, cwd=workdir)
        subprocess.run(['docker', 'run', '-d', '--rm', '--name',
                       repo]
                       + labels(repo_lower, 80) + [image_name])
    app.logger.info(f'CONTAINER {repo} STARTED')
    if commit_id:
        update_status(org, repo, repo_lower, commit_id, state)


def update_status(org, repo, repo_lower, commit_id, state):

    url = f'https://api.github.com/repos/{org}/{repo}/statuses/{commit_id}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json'
    }
    data = {
        'state': state,
        'target_url': f'https://{repo_lower}.rxq.ch/',
        'description': 'Builder status',
        'context': 'continuous-integration/interschool'
    }
    request_client.post(url, headers=headers,
                        data=json.dumps(data), timeout=10)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
