import configparser
import functools
import pathlib


class Repository(object):
    """A Git Repository"""

    @classmethod
    def create(cls, path):
        repo = cls(path, force=True)
        if repo.worktree.exists():
            if not repo.worktree.is_dir():
                raise Exception("Not a directory (file exists): %s" % repo.worktree)
            if list(repo.worktree.glob('*')):
                raise Exception("Not a empty directory: %s" % repo.worktree)
        else:
            repo.worktree.mkdir(parents=True)

        assert repo.dir("branches", mkdir=True)
        assert repo.dir("objects", mkdir=True)
        assert repo.dir("refs", "tags", mkdir=True)
        assert repo.dir("refs", "heads", mkdir=True)

        repo.file("description").write_text("Unnamed repository; edit this file 'description' to name the repository.\n")
        repo.file("HEAD").write_text("ref: refs/heads/master\n")
        with repo.file("config").open("w") as f:
            res = configparser.ConfigParser()
            res.add_section("core")
            res.set("core", "repositoryformatversion", "0")
            res.set("core", "filemode", "false")
            res.set("core", "bare", "false")
            res.write(f)

    def __init__(self, path, force=False):
        self.worktree = pathlib.Path(path)
        self.gitdir = self.worktree / ".git"
        if not self.gitdir.is_dir() and not force:
            raise Exception("Not a Git repository: %s" % path)

        self.conf = configparser.ConfigParser()
        cf = self.file("config")
        if cf and cf.exists():
            self.conf.read(cf)
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            ver = int(self.conf.get("core", "repositoryformatversion"))
            if ver != 0 and not force:
                raise Exception("Unsupported repositoryformatversion: %s" % ver)

    def __path(self, *path):
        return functools.reduce(lambda parent, child: parent / child, path, self.gitdir)

    def file(self, *path, mkdir=False):
        if self.dir(*path[:-1], mkdir=mkdir):
            return self.__path(*path)
        else:
            return None

    def dir(self, *path, mkdir=False):
        path = self.__path(*path)
        if path.exists():
            if path.is_dir():
                return path
            else:
                raise Exception("Not a directory (file exists): %s" % path)
        else:
            if mkdir:
                path.mkdir(parents=True)
                return path
            else:
                return None
