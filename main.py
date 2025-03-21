import os
import requests as request_client
import json
import subprocess
import time
import logging
import datetime
from threading import Thread, Lock
from datetime import timezone, timedelta


from flask import Flask, request, render_template, jsonify
from flask_cors import CORS

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

CHECK_PREFIX = 'g-'

OVERRIDES = {}
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
CORS(app)

# Build status tracking
build_threads = {}
build_history = []
build_lock = Lock()
MAX_HISTORY = 50  # Maximum number of builds to keep in history

# Set timezone (UTC+1)
SERVER_TZ = timezone(timedelta(hours=1))

# Function to update build status
def update_build_status(org, repo, status, start_time=None, end_time=None, state=None, commit_id=None):
    with build_lock:
        build_id = f"{org}/{repo}"
        
        if status == "started":
            build_threads[build_id] = {
                "org": org,
                "repo": repo,
                "status": "building",
                "start_time": start_time or datetime.datetime.now(SERVER_TZ),
                "state": "running",
                "commit_id": commit_id
            }
        elif status == "finished":
            if build_id in build_threads:
                build_info = build_threads[build_id]
                build_info["status"] = "completed"
                build_info["end_time"] = end_time or datetime.datetime.now(SERVER_TZ)
                build_info["duration"] = (build_info["end_time"] - build_info["start_time"]).total_seconds()
                build_info["state"] = state or "unknown"
                
                # Add to history and remove from active builds
                build_history.insert(0, build_info.copy())
                del build_threads[build_id]
                
                # Limit history size
                if len(build_history) > MAX_HISTORY:
                    build_history.pop()

# Function to inject build information into build.html
def inject_build_info(workdir, commit_id, org=None, repo=None):
    build_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_id = commit_id or "unknown-commit"
    
    # Read the template file
    template_path = '/app/build_templates/build.html'
    output_path = f'{workdir}/build.html'
    
    try:
        with open(template_path, "r") as f:
            content = f.read()
    
        content = content.replace("%%COMMIT_ID%%", commit_id)
        content = content.replace("%%BUILD_DATE%%", build_date)
        
        # Add GitHub repo information if available
        if org and repo and commit_id and commit_id != "unknown-commit":
            github_url = f"https://github.com/{org}/{repo}/commit/{commit_id}"
            content = content.replace("%%GITHUB_URL%%", github_url)
            content = content.replace("%%GITHUB_REPO%%", f"{org}/{repo}")
        else:
            content = content.replace("%%GITHUB_URL%%", "#")
            content = content.replace("%%GITHUB_REPO%%", "Unknown repository")
        
        with open(output_path, "w") as f:
            f.write(content)
        
        app.logger.info(f'Build information injected. Commit ID: {commit_id}, Build Date: {build_date}')
        return True
    except Exception as e:
        app.logger.error(f'Error injecting build information: {str(e)}')
        return False

@app.route('/', methods=['GET'])
def index():
    path = "/app/data"
    projects = [name for name in sorted(os.listdir(path)) if os.path.isdir(os.path.join(path, name))]
    return render_template('index.html', projects=projects, now=time.time(), prefix=CHECK_PREFIX)


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.json["repository"]["name"].startswith(CHECK_PREFIX) and request.json["ref"] == "refs/heads/main":
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

@app.route('/status', methods=['GET'])
def status_page():
    with build_lock:
        active_builds = list(build_threads.values())
        history = build_history.copy()
    
    return render_template('status.html', 
                          active_builds=active_builds, 
                          build_history=history, 
                          now=datetime.datetime.now(SERVER_TZ))


def build(org, repo, override='', commit_id=None):
    repo_lower = repo.lower().replace(CHECK_PREFIX, '')
    start_time = datetime.datetime.now(SERVER_TZ)
    update_build_status(org, repo, "started", start_time, commit_id=commit_id)

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

    inject_build_info(workdir, commit_id, org, repo)
    # Copy the Dockerfile into the repository
    subprocess.run(['cp', '/app/build_templates/dockerignore',
                   f'./.dockerignore'], cwd=workdir)
    subprocess.run(['cp', '/app/build_templates/prod.py',
                   f'./prod.py'], cwd=workdir)
    subprocess.run(['cp', '/app/build_templates/smtp.py',
                   f'./backend/settings/smtp.py'], cwd=workdir)

    def run_build_cmd(image_type):
        # Build the Docker image and save the logs to a file
        subprocess.run(['cp', f'/app/build_templates/Build.{image_type}.Dockerfile',
                    f'./Dockerfile'], cwd=workdir)
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
                "-e", f"PROJECT_NAME={repo_lower}",
                "--network", "web"
            ]
        state = 'failure'
        if result.returncode == 0:
            app.logger.info(f'BUILD {repo} SUCCESS')
            result = subprocess.run(['docker', 'run', '-d', '--restart=always', '--name', repo, '-e',
                                    f'DJANGO_ALLOWED_HOST=https://{repo_lower}.rxq.ch']
                                    + labels(repo_lower, 8000) + [image_name])
            state = 'success'
        else:
            app.logger.info(f'BUILD {repo} FAILED')
            if image_type == "Alpine":
                return run_build_cmd("Debian")
            # serve logs with Nginx
            subprocess.run(
                ['sh', '-c', 'cp /app/build_templates/Nginx.Dockerfile ./Dockerfile && cp /app/build_templates/index.html ./index.html'], cwd=workdir)
            subprocess.run(['docker', 'build', '-t', image_name,
                        '.'], capture_output=True, cwd=workdir)
            subprocess.run(['docker', 'run', '-d', '--restart=always', '--name',
                        repo]
                        + labels(repo_lower, 80) + [image_name])
        return state
    
    state = run_build_cmd("Alpine")
    app.logger.info(f'CONTAINER {repo} STARTED')
    
    end_time = datetime.datetime.now(SERVER_TZ)
    update_build_status(org, repo, "finished", start_time, end_time, state, commit_id)
    
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
