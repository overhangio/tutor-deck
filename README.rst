dash plugin for `Tutor <https://docs.tutor.edly.io>`__
######################################################

Awesome administration dashboard and plugin marketplace for Tutor


Installation
************

.. code-block:: bash

    pip install git+https://github.com/overhangio/tutor-dash

.. TODO how to package css files?

Usage
*****

.. code-block:: bash

    tutor plugins enable dash

Development
***********

Install locally::

    pip install -e .[dev]

Install npm requirements::

    npm clean-install

Compile SCSS files::

    make scss       # compile once
    make scss-watch # compile and watch for changes

Run a development server::

    make runserver

License
*******

This software is licensed under the terms of the AGPLv3.
