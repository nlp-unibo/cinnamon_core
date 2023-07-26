.. cinnamon-core documentation master file, created by
   sphinx-quickstart on Sun May 21 18:00:41 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to cinnamon-core's documentation!
===============================================
Cinnamon is a simple framework for general-purpose configuration and code logic de-coupling.
It was developed to offer two main functionalities:

1. De-coupling a code logic from its regulating parameters
2. Quick re-use of code logic

Features
===============================================
- General-purpose: ``cinnamon`` is meant to simplify your code organization and re-use.
- Simple: ``cinnamon`` is a small library that acts as a high-level wrapper for your projects.
- Modular: ``cinnamon`` is shipped in several small packages to meet different requirements
- Community-based: the ``Component`` and ``Configuration`` you define can be imported/exported from/to other users!
- Flexible: ``cinnamon`` imposes minimal APIs meant to simplify code organization. You are still free to code as you like!


Logic and Configuration de-coupling
===============================================
Consider a classic machine-learning.
Your first task is to load some data.
A skeleton of your data loader may be as follows:

```
class DataLoader:

   def load(...):
       pass

   def parse(data):
       pass

   def build_splits(data):
       pass
```

Your data loader can ``load`` some data (e.g., from filesystem),
``parse`` it to a convenient format and (optionally) defining train/val/test ``splits``.

Each of the above functionalities may be regulated by some parameters:

- ``load``: we may specify whether to load from JSON, from an online repository or from something else.
- ``parse``: we may specify if some input fields have to be considered or if some parsing functions have to be carried out.
- ``build_splits``: we may specify whether to build some splits if they don't exist or the maximum amount of samples to pick (e.g., for testing)

Well, these parameters define a ``Configuration`` in ``cinnamon``,
while the above ``DataLoader`` logic is a ``Component`` that uses a suitable ``Configuration`` for its execution.

Quick re-use
===============================================
In many cases, we use and re-use a code logic (or some variants of it) for different purposes.
Recall the data loader example of previous section:
we may use it for evaluating different machine-learning models (in different projects)
or testing distinct data pre-processing steps.

For this reason, it may be convenient to quickly access to the data loader logic we want to re-use.
In ``cinnamon``, a ``Configuration`` is used to define an instance of a ``Component``.
Each ``Configuration`` can be registered in a ``Registry`` via a ``key`` for quick re-use:

1. Define your code logic: ``Component``
2. Define a suitable ``Configuration`` for your ``Component``
3. Bind the ``Configuration`` to your ``Component`` to build multiple ``Component`` instances
4. Register the ``Configuration`` via a key.
5. Use the ``key`` to build re-use and build your Component.

Install
=======
Three methods are supported:

- ``setup.py``: ``pip install .``
- *pip* package: ``pip install cinnamon-core``

Getting started
=======
TODO


.. toctree::
   :maxdepth: 4
   :caption: Contents:

   intro
   overview

Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
