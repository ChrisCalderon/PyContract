from setuptools import setup


def is_http(req):
    """Checks if a requirement is a link."""
    return req.startswith('http://') or req.startswith('https://')


def dep_sorter(rs, r):
    """Appends the requirement r to the proper list."""
    print rs, r
    if is_http(r):
        rs[1].append(r)
    else:
        rs[0].append(r)
    return rs

with open('requirements.txt') as reqs:
    requirements, links = reduce(dep_sorter,
                                 filter(None,
                                        [r.strip() for r in reqs]),
                                 [[],[]])

setup(name='contract',
      version='1.0dev1',
      description='Classes for interacting with Ethereum smart contracts.',
      author='ChrisCalderon',
      author_email='pythonwiz@protonmail.com',
      packages=['contract'],
      install_requires=requirements,
      dependency_links=links)
