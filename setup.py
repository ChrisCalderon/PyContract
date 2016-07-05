from setuptools import setup

with open('requirements.txt') as reqs:
    requirements = filter(None, [r.strip() for r in reqs])

setup(name='PyContract',
      version='1.0dev1',
      description='Classes for interacting with Ethereum smart contracts.',
      author='ChrisCalderon',
      author_email='pythonwiz@protonmail.com',
      packages=['contract'],
      install_requires=requirements)