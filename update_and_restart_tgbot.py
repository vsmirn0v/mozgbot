import os
import subprocess
import time
from git import Repo

# Configuration
repository_url = "https://github.com/vsmirn0v/mozgbot.git"
local_repository_path = "/path/to/your/local/repo"
tgbot_script = "tgbot.py"
restart_delay = 5

# Function to check if the repository has been updated
def check_for_updates(local_repo):
    origin = local_repo.remotes.origin
    origin.fetch()
    local_commit = local_repo.head.commit.hexsha
    remote_commit = origin.refs.master.commit.hexsha
    return local_commit != remote_commit

# Function to update the local copy of the repository
def update_local_repository(local_repo):
    local_repo.git.reset("--hard")
    local_repo.remotes.origin.pull()

# Function to restart the tgbot.py program
def restart_tgbot():
    # Terminate existing tgbot.py process
    subprocess.run(["pkill", "-f", tgbot_script])

    # Wait for a few seconds before starting a new instance
    time.sleep(restart_delay)

    # Start a new tgbot.py instance in the background
    subprocess.Popen(["python", tgbot_script], cwd=local_repository_path)

def main():
    # Initialize the local repository
    local_repo = Repo(local_repository_path)

    # Check for updates
    if check_for_updates(local_repo):
        print("Repository has been updated. Pulling changes and restarting tgbot.py...")
        update_local_repository(local_repo)
        restart_tgbot()
    else:
        print("No updates found.")

if __name__ == "__main__":
    main()
