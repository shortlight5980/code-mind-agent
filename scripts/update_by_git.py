"""
根据 Git 变更记录增量更新 Chroma 和 BM25 索引。
"""
import argparse
import os
import subprocess
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.add_by_file_path import add_documents_by_source
from scripts.delete_by_file_path import delete_documents_by_source
from utils.config import Config
from utils.logger import get_logger

logger = get_logger("index_update_by_git")


def get_repo_root() -> str:
    """返回当前 Git 仓库根目录。"""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _build_git_diff_command(mode: str, commits: int = 1, revision: str | None = None) -> list[str]:
    """根据更新模式构造 Git diff 命令。"""
    if mode == "working":
        return ["git", "diff", "--name-only"]
    if mode == "staged":
        return ["git", "diff", "--cached", "--name-only"]
    if mode == "commits":
        if commits < 1:
            raise ValueError("commits 必须大于等于 1")
        return ["git", "diff", f"HEAD~{commits}", "HEAD", "--name-only"]
    if mode == "revision":
        if not revision:
            raise ValueError("mode=revision 时必须提供 revision")
        return ["git", "diff", f"{revision}~1", revision, "--name-only"]
    raise ValueError(f"未知模式: {mode}")


def get_git_changed_files(
    mode: str = "commits",
    commits: int = 1,
    revision: str | None = None,
) -> list[str]:
    """获取 Git 变更文件绝对路径列表。"""
    repo_root = get_repo_root()
    cmd = _build_git_diff_command(mode, commits=commits, revision=revision)
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [os.path.abspath(os.path.join(repo_root, path)).replace("\\", "/") for path in files]


def update_index_by_git(
    mode: str = "commits",
    commits: int = 1,
    revision: str | None = None,
    persist_dir: str | None = None,
) -> dict[str, int | str]:
    """根据 Git 变更文件执行删除后重建的增量索引更新。"""
    Config.load()
    changed_files = get_git_changed_files(mode=mode, commits=commits, revision=revision)
    logger.info(f"开始 Git 索引更新，模式: {mode}，变更文件数: {len(changed_files)}")

    deleted_count = 0
    added_chunks = 0
    skipped_files = 0

    for file_path in changed_files:
        try:
            delete_documents_by_source(file_path, persist_dir=persist_dir)
            deleted_count += 1
        except Exception as exc:
            logger.warning(f"删除旧索引失败 {file_path}: {exc}")

        if os.path.isfile(file_path):
            try:
                added_chunks += add_documents_by_source(file_path, persist_dir=persist_dir)
            except Exception as exc:
                logger.error(f"重新添加索引失败 {file_path}: {exc}")
        else:
            skipped_files += 1
            logger.info(f"文件已删除或不存在，跳过添加: {file_path}")

    return {
        "mode": mode,
        "changed_files": len(changed_files),
        "deleted": deleted_count,
        "added_chunks": added_chunks,
        "skipped": skipped_files,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据 Git 变更增量更新 Chroma 和 BM25 索引")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--commits", type=int, help="使用最近 n 次提交，默认 1")
    mode_group.add_argument("--revision", type=str, help="使用指定提交修订号")
    mode_group.add_argument("--staged", action="store_true", help="使用暂存区变更")
    mode_group.add_argument("--working", action="store_true", help="使用工作区变更")
    parser.add_argument("--persist-dir", help="Chroma 持久化目录；默认读取 config.yml")
    return parser.parse_args()


def _resolve_mode(args: argparse.Namespace) -> tuple[str, int, str | None]:
    mode = "commits"
    commits = 1
    revision = None

    if args.commits is not None:
        commits = args.commits
    elif args.revision is not None:
        mode = "revision"
        revision = args.revision
    elif args.staged:
        mode = "staged"
    elif args.working:
        mode = "working"

    return mode, commits, revision


if __name__ == "__main__":
    arguments = _parse_args()
    mode, commits, revision = _resolve_mode(arguments)

    try:
        stats = update_index_by_git(
            mode=mode,
            commits=commits,
            revision=revision,
            persist_dir=arguments.persist_dir,
        )
        print("\n索引更新完成:")
        print(f"  模式: {stats['mode']}")
        print(f"  变更文件数: {stats['changed_files']}")
        print(f"  删除文件数: {stats['deleted']}")
        print(f"  新增分块数: {stats['added_chunks']}")
        print(f"  跳过文件数: {stats['skipped']}")
    except Exception as exc:
        logger.error(f"更新失败: {exc}", exc_info=True)
        print(f"\n更新失败: {exc}")
        sys.exit(1)
