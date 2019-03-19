import configparser
import functools
import hashlib
import pathlib
import zlib


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

    @classmethod
    def find(cls, path=pathlib.Path("."), required=True):
        path = pathlib.Path(path)
        if (path / ".git").is_dir():
            return cls(path)

        parent = path.resolve().parent
        if parent == path: # filesystem root
            if required:
                raise Exception("Not a Git reposiory: %s" % path)
            else:
                return None
        else:
            return cls.find(parent)

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

    def object(self, sha, mkdir=False):
        return self.file("objects", sha[:2], sha[2:], mkdir=mkdir)

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


class BaseObject(object):
    fmt = "base"

    @staticmethod
    def read(repo, sha):
        path = repo.object(sha)
        raw = zlib.decompress(path.read_bytes())

        delim_20 = raw.find(b"\x20")
        delim_00 = raw.find(b"\x00")
        fmt = raw[:delim_20].decode("ascii")
        size= int(raw[delim_20:delim_00].decode("ascii"))
        if size != len(raw) - (delim_00 + 1):
            raise Exception("Malformed object %s: bad length" % sha)

        cls = BaseObject.__get_cls(fmt)
        return cls(repo, raw[delim_00+1:])

    @staticmethod
    def __get_cls(fmt):
        if fmt == "blob": return Blob
        else: raise Exception("Unknown object type %s (sha: %s)" % (fmt, sha))

    @staticmethod
    def create_from_file(repo, fmt, path):
        data = pathlib.Path(path).read_bytes()
        cls = BaseObject.__get_cls(fmt)
        return cls(repo, data).write(dry_run=(repo is None))

    def __init__(self, repo, data=None):
        self.repo = repo
        if not data is None:
            self.deserialize(data)

    def serialize(self):
        raise NotImplementedError

    def deserialize(self, data):
        raise NotImplementedError

    def write(self, dry_run=False):
        if self.fmt == "base":
            raise NotImplementedError

        data = self.serialize()
        data = (self.fmt + " " + str(len(data)) + "\x00").encode() + data
        sha = hashlib.sha1(data).hexdigest()

        if not dry_run:
            path = self.repo.object(sha, mkdir=True)
            path.write_bytes(zlib.compress(data))

        return sha


class Blob(BaseObject):
    fmt = "blob"

    def serialize(self):
        return self.data

    def deserialize(self, data):
        self.data = data
