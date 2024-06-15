

Google Cloud Speech API Python Samples
===============================================================================


This directory contains samples for streaming audio translation using:
- Google Speech to Text API
- Google Cloud Translation AI


Setup
-------------------------------------------------------------------------------


Authentication
++++++++++++++

This sample requires you to have authentication setup. Refer to the
`Authentication Getting Started Guide`_ for instructions on setting up
credentials for applications.

.. _Authentication Getting Started Guide:
    https://cloud.google.com/docs/authentication/getting-started

Install Dependencies
++++++++++++++++++++

#. Clone python-docs-samples and change directory to the sample directory you want to use.

    .. code-block:: bash

        $ git clone https://github.com/gangchen03/speech-ai.git

#. Install `pip`_ and `virtualenv`_ if you do not already have them. You may want to refer to the `Python Development Environment Setup Guide`_ for Google Cloud Platform for instructions.

   .. _Python Development Environment Setup Guide:
       https://cloud.google.com/python/setup

#. Create a virtualenv. Samples are compatible with Python 2.7 and 3.4+.

    .. code-block:: bash

        $ virtualenv env
        $ source env/bin/activate

#. Install the dependencies needed to run the samples.

    .. code-block:: bash

        $ pip install -r requirements.txt

#. Run the sample streaming with Microphone.

    .. code-block:: bash

        $ python translate_streaming_audio.py your_gcp_project_id

.. _pip: https://pip.pypa.io/
.. _virtualenv: https://virtualenv.pypa.io/



The client library
-------------------------------------------------------------------------------

This sample uses the `Google Cloud Client Library for Python`_.
You can read the documentation for more details on API usage and use GitHub
to `browse the source`_ and  `report issues`_.

.. _Google Cloud Client Library for Python:
    https://googlecloudplatform.github.io/google-cloud-python/
.. _browse the source:
    https://github.com/GoogleCloudPlatform/google-cloud-python
.. _report issues:
    https://github.com/GoogleCloudPlatform/google-cloud-python/issues


.. _Google Cloud SDK: https://cloud.google.com/sdk/