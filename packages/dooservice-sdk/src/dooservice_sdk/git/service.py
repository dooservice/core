from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import shutil
import subprocess

import pygit2

from ..errors import CommitNotFoundError, SubmoduleMissingKeyError


class GitService:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    def env_dir(self, project_name: str, env_name: str) -> Path:
        return self.projects_dir / project_name / env_name

    def addons_dir(self, project_name: str, env_name: str) -> Path:
        return self.env_dir(project_name, env_name) / "addons"

    def project_key_path(self, project_name: str) -> Path:
        return self.projects_dir / project_name / "deploy_key" / "id_ed25519"

    def submodule_key_dir(self, project_name: str, repo_url: str) -> Path:
        url_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:16]
        return self.projects_dir / project_name / "submodule_keys" / url_hash

    def generate_key(self, key_dir: Path, comment: str) -> dict[str, str]:
        private_key = key_dir / "id_ed25519"
        public_key  = key_dir / "id_ed25519.pub"
        key_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not private_key.exists():
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-C", comment, "-f", str(private_key), "-N", ""],
                check=True, capture_output=True, text=True,
            )
            private_key.chmod(0o600)
            public_key.chmod(0o644)
        return {"public_key": public_key.read_text().strip(), "key_path": str(private_key)}

    def setup_project_key(self, project_name: str) -> dict[str, str]:
        return self.generate_key(
            self.projects_dir / project_name / "deploy_key",
            f"dooservice-{project_name}",
        )

    def setup_submodule_key(self, project_name: str, repo_url: str) -> dict[str, str]:
        key_dir = self.submodule_key_dir(project_name, repo_url)
        result  = self.generate_key(key_dir, "dooservice-submodule")
        (key_dir / "url.txt").write_text(repo_url)
        return result

    def delete_submodule_key(self, project_name: str, repo_url: str) -> None:
        key_dir = self.submodule_key_dir(project_name, repo_url)
        if key_dir.exists():
            shutil.rmtree(key_dir)

    def load_submodule_keys(self, project_name: str) -> dict[str, Path]:
        keys_dir = self.projects_dir / project_name / "submodule_keys"
        if not keys_dir.exists():
            return {}
        return {
            (entry / "url.txt").read_text().strip(): entry / "id_ed25519"
            for entry in keys_dir.iterdir()
            if (entry / "url.txt").exists() and (entry / "id_ed25519").exists()
        }

    def callbacks(self, project_name: str) -> pygit2.RemoteCallbacks:
        submodule_keys = self.load_submodule_keys(project_name)
        project_key    = self.project_key_path(project_name)

        def resolve_credentials(url: str, username: str, allowed_types: int) -> pygit2.Keypair:
            key_path = submodule_keys.get(url, project_key)
            return pygit2.Keypair("git", str(key_path) + ".pub", str(key_path), "")

        return pygit2.RemoteCallbacks(
            credentials=resolve_credentials,
            certificate_check=lambda *ignored: True,
        )

    async def clone(self, project_name: str, env_name: str, repo_url: str, branch: str) -> str:
        repo = await asyncio.to_thread(
            pygit2.clone_repository,
            repo_url,
            str(self.addons_dir(project_name, env_name)),
            checkout_branch=branch or None,
            callbacks=self.callbacks(project_name),
        )
        await self.update_submodules(repo, project_name)
        return str(repo.head.target)

    async def pull(self, project_name: str, env_name: str, branch: str = "") -> str:
        repo   = pygit2.Repository(str(self.addons_dir(project_name, env_name)))
        branch = branch or repo.head.shorthand

        await asyncio.to_thread(
            repo.remotes["origin"].fetch, [branch],
            callbacks=self.callbacks(project_name),
        )

        remote_commit = repo.references[f"refs/remotes/origin/{branch}"].peel(pygit2.Commit)
        repo.reset(remote_commit.id, pygit2.GIT_RESET_HARD)
        await self.update_submodules(repo, project_name)
        return str(remote_commit.id)

    async def checkout(self, project_name: str, env_name: str, commit_sha: str) -> None:
        repo   = pygit2.Repository(str(self.addons_dir(project_name, env_name)))
        target = repo.get(commit_sha)
        if target is None:
            raise CommitNotFoundError(commit_sha)
        repo.reset(target.id, pygit2.GIT_RESET_HARD)
        await self.update_submodules(repo, project_name)

    async def update_submodules(self, repo: pygit2.Repository, project_name: str) -> None:
        submodule_keys = self.load_submodule_keys(project_name)
        missing = [
            sub.url
            for sub in repo.submodules
            if sub.url and sub.url not in submodule_keys
        ]
        if missing:
            raise SubmoduleMissingKeyError(missing)

        cbs = self.callbacks(project_name)

        def update() -> None:
            repo.submodules.update(init=True, callbacks=cbs, depth=1)

        await asyncio.to_thread(update)
