import collections
import configparser
import functools
import hashlib
import pathlib
import re
import zlib


class Repository(object):
    """A Git Repository"""

    @classmethod
    def create(cls, path):
        repo = cls(path, force=True)
        if repo.worktree.exists():
            if not repo.worktree.is_dir():
                raise Exception("Not a directory (file exists): %s" % repo.worktree)
            if list(repo.worktree.glob("*")):
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

    def object_find(self, name, fmt=None):
        name = name.strip()
        sha = None

        if name == "HEAD":
            sha = Ref.resolve(self, "HEAD")

        if re.match(r"^[0-9A-Fa-f]{4,40}$", name):
            if len(name) == 40:
                sha = name.lower()
            else:
                prefix = name[:2].lower()
                body = name[2:].lower()
                candidates = [
                    prefix + p.name
                    for p in self.dir("objects", prefix).glob("*")
                    if p.name.startswith(body)
                    ]
                if len(candidates) == 0:
                    raise Exception("Short hash doesn't match any object: %s" % name)
                elif len(candidates) == 1:
                    sha = candidates[0]
                else:
                    raise Exception("Ambiguous short hash: %s" % name)

        def inner(refs):
            res = None
            for k, v in refs.items():
                if k == name and type(v) == str:
                    res = v
                elif type(v) == collections.OrderedDict:
                    res = res or inner(v)
            return res
        sha = inner(Ref.find_all(self))

        if sha is None:
            raise Exception("name `%s` doesn't match any object." % name)

        if fmt is None:
            return sha
        else:
            def inner(sha):
                obj = BaseObject.read(self, sha)
                if obj.fmt == fmt:
                    return obj.sha
                elif obj.fmt == "tag":
                    return inner(obj.object_sha)
                elif obj.fmt == "commit" and fmt == "tree":
                    return inner(obj.tree_sha)
                else:
                    raise Exception("No matched object with type %s: %s" % (fmt, name))
            return inner(sha)

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
    def read(repo, name):
        sha = repo.object_find(name)
        path = repo.object(sha)
        raw = zlib.decompress(path.read_bytes())

        delim_20 = raw.find(b"\x20")
        delim_00 = raw.find(b"\x00")
        fmt = raw[:delim_20].decode("ascii")
        size= int(raw[delim_20:delim_00].decode("ascii"))
        if size != len(raw) - (delim_00 + 1):
            raise Exception("Malformed object %s: bad length" % sha)

        cls = BaseObject.__get_cls(fmt)
        return cls(repo, sha, raw[delim_00+1:])

    @staticmethod
    def __get_cls(fmt):
        if   fmt == "blob"   : return Blob
        elif fmt == "commit" : return Commit
        elif fmt == "tag"    : return Tag
        elif fmt == "tree"   : return Tree
        else: raise Exception("Unknown object type %s (sha: %s)" % (fmt, sha))

    @staticmethod
    def create_from_file(repo, fmt, path):
        data = pathlib.Path(path).read_bytes()
        cls = BaseObject.__get_cls(fmt)
        return cls(repo, data).write(dry_run=(repo is None))

    def __init__(self, repo, sha, data=None):
        self.repo = repo
        self.sha = sha
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


class Commit(BaseObject):
    fmt = "commit"

    @property
    def headline(self):
        return self.dct[""][:self.dct[""].find("\x0a")]

    @property
    def tree_sha(self):
        return self.dct["tree"]

    @property
    def parents(self):
        if not "parent" in self.dct.keys():
            return []

        parents = self.dct["parent"]
        if type(parents) != list:
            parents = [parents]

        return [BaseObject.read(self.repo, p) for p in parents]


    def serialize(self):
        res = ""

        for k, v in self.dct.items():
            if k == "":
                continue
            if type(v) != list:
                v = [v]

            for e in v:
                res += k + "\x20" + (e.replace("\x0a", "\x0a\x20")) + "\x0a"

        res += "\x0a" + self.dct[""]
        return res.encode()

    def deserialize(self, raw):
        def inner(start=0, dct=None):
            if dct is None:
                dct = collections.OrderedDict()

            delim_20 = raw.find(b"\x20", start)
            delim_0a = raw.find(b"\x0a", start)
            if start == delim_0a:
                dct[""] = raw[start+1:].decode("ascii")
                return dct

            key = raw[start : delim_20].decode("ascii")
            end = delim_0a
            while end < len(raw) - 1 and raw[end+1] == b" ":
                end = raw.find(b"\x0a", end + 1)
            value = raw[delim_20+1 : end].replace(b"\x0a\x20", b"\x0a").decode("ascii")

            if key in dct:
                if type(dct[key]) == list:
                    dct[key].append(value)
                else:
                    dct[key] = [dc[key], value]
            else:
                dct[key] = value

            return inner(start=end+1, dct=dct)

        self.dct = inner()


class Tag(Commit):
    fmt = "tag"

    @classmethod
    def create_object(repo, name, sha):
        raise NotImplementedError

    @classmethod
    def create_ref(repo, name, sha):
        repo.file("refs", "tags", "name").write_text("%s\n" % sha)

    @property
    def object_sha(self):
        return self.dct["object"]


class TreeEntry(object):
    @classmethod
    def read(cls, raw):
        delim_20 = raw.find(b"\x20")
        delim_00 = raw.find(b"\x00")

        mode = raw[:delim_20].decode("ascii")
        path = raw[delim_20+1 : delim_00].decode("ascii")
        sha = hex(int.from_bytes(raw[delim_00+1 : delim_00+21], "big"))[2:] # [2:] drops `0x`

        return delim_00 + 21, cls(mode, path, sha)

    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


class Tree(BaseObject):
    fmt = "tree"

    def serialize(self):
        res = b""
        for e in self.entries:
            res += (e.mode + "\x20" + e.path + "\x00").encode()
            res += int(e.sha, 16).to_bytes(20, byteorder="big")
        return res

    def deserialize(self, raw):
        self.entries = []
        pos = 0
        while pos < len(raw):
            length, entry = TreeEntry.read(raw[pos:])
            pos += length
            self.entries.append(entry)


class Ref(object):
    @staticmethod
    def resolve(repo, path):
        ref = repo.file(path).read_text().strip()
        if ref.startswith("ref:"):
            return Ref.resolve(repo, ref[5:])
        else:
            return ref

    @staticmethod
    def find_all(repo, path=None):
        if path is None:
            path = repo.dir("refs")

        res = collections.OrderedDict()
        for p in sorted(path.glob("*")):
            if p.is_dir():
                res[p.name] = Ref.find_all(repo, p)
            else:
                res[p.name] = Ref.resolve(repo, p)

        return res
