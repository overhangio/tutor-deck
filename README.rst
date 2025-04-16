`Tutor <https://docs.tutor.edly.io>`__ Deck
###########################################

This is a plugin for `Tutor`_ that provides an administration dashboard and integrates `Plugin Marketplace`_ in an Open edX platform.


.. _Tutor: https://docs.tutor.edly.io
.. _Plugin Marketplace: https://edly.io/tutor/plugins-and-themes/


Installation
************

::

   tutor plugins update
   tutor plugins install deck
   tutor plugins enable deck

Run Tutor Deck with::

   tutor deck runserver

And access the interface at http://127.0.0.1:3274

Development
***********

Install requirements::

    pip install -e .[dev]
    npm clean-install

Compile SCSS files::

    make scss       # compile once
    make scss-watch # compile and watch for changes

Run a development server::

    make runserver

Usage
*****

Discover and install plugins from plugin marketplace:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/marketplace.png
   :alt: Marketplace Image

Browse your installed plugins:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/installed.png
   :alt: Installed Image

Enable/Disable plugin:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/android.png
   :alt: Android Image

Change plugin parameters:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/android_settings.png
   :alt: Android Settings Image

Use Developer mode for all tutor CLI commands:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/developer.png
   :alt: Developer Image

Restart platform via GUI to apply changes:

.. image:: https://github.com/overhangio/tutor-deck/raw/release/images/apply.png
   :alt: Apply Image

Troubleshooting
***************

This Tutor plugin is maintained by Muhammad Labeeb from `Edly`_.
Community support is available from the official `Open edX forum`_.
Do you need help with this plugin? See the `troubleshooting`_
section from the Tutor documentation.

.. _Edly: https://edly.io/
.. _Open edX forum: https://discuss.openedx.org
.. _troubleshooting: https://docs.tutor.edly.io/troubleshooting.html

License
*******

This work is licensed under the terms of the `GNU Affero General Public License (AGPL)`_.

.. _GNU Affero General Public License (AGPL): https://github.com/overhangio/tutor/blob/release/LICENSE.txt
