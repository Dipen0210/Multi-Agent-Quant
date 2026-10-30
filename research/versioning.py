"""Capture actual served application and dependency identities, including dirty worktrees."""
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import hashlib


def code_version():
    root=Path(__file__).parents[1]
    hash_=hashlib.sha256()
    for folder in ('research','api','evaluation'):
        for file in sorted((root/folder).rglob('*')):
            if file.suffix not in {'.py','.sql'}: continue
            hash_.update(str(file.relative_to(root)).encode());hash_.update(file.read_bytes())
    return hash_.hexdigest()


def dependency_versions():
    result={}
    for package in ('langgraph','pydantic','transformers','torch','exchange-calendars','fastapi'):
        try: result[package]=version(package)
        except PackageNotFoundError: result[package]=None
    return result
