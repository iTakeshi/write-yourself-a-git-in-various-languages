Write Yourself A Git (in various languages)
============================================

[Original article by Thibault Polge](https://wyag.thb.lt/)

### DISCLAIMER
This is an experimental and educational project WHICH IS NOT MEANT TO BE USED IN PRODUCTION.
THE AUTHOR SHALL NOT BE RESPONSIBLE for any damages that may occur through the use of the contents of this repository.

### IMPORTANT: unpack packfiles
After you clone this repository, what you have to do first is execute the unpacker script:
```
./unpack.sh
```

Object files cloned from GitHub is [packed](https://git-scm.com/book/en/v2/Git-Internals-Packfiles) for an efficient transmission,
but (for the moment) my WYAG cannot deal with packfiles.
The unpacker script just unpacks the packfiles and create loose objects which WYAG can understand.

### MOTIVATION
Git is one of the most commonly used softwares in the world of software engineers.
Despite of its strong ability, the core architecture of Git is surprisingly simple and easy to understand/implement.
Therefore Git can be a perfect "first shot" in learning new programming languages.

I recently found [a great article](https://wyag.thb.lt) implementing Git in Python.
Although it does not affect the benefits of the original article, the article is still imperfect, for example it lacks some important commands such as `commit`.
In this project, I extend the original implementation in python and add implementations in other languages.[

### TARGET LANGUAGES
- [x] Python3
- [ ] Scala (next up)

### LICENSE
The [original project](https://github.com/thblt/write-yourself-a-git) was authored by @thblt under GNU General Public License v3.0.
I really appreciate his educational contribution and inherit the license terms in this project.
See the `LICENSE` file for detail.

### CONTRIBUTION
Bug reports and pull requests would always be welcomed.
