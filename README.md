fairview-fccv
=============

Comment validation for Django. It runs comments through a chain of validators, which can be easily extended.

Comment validation for Django
=============================

This package provides chainable validation for django.contrib.comments. It's
available under the MIT license.

Installation
============

1) Download the source and unzip it or check it out with:

    hg clone http://bitbucket.org/fairview/fccv/

2) Change directory to the top of the source tree and run python setup.py install or simply copy the fccv subdirectory to your PYTHONPATH.

3) Add 'fccv' to your Django INSTALLED_APPS setting.

4) Run 'manage.py syncdb' to create the blacklist and banned IP tables, and
load the starter set of blacklists.

5) By default, only local validation is performed. If you want to add Akismet
or TypePad AntiSpam, you'll need to add another setting, FCCV_VALIDATORS,
e.g.:

    FCCV_VALIDATORS = (
        'fccv.check_comment_email',
        'fccv.check_comment_ip',
        'fccv.check_comment_link_limit',
        'fccv.check_comment_name',
        'fccv.check_comment_text',
        'fccv.check_comment_url',
        'fccv.check_typepad_antispam',
    )

Then add your API key. For Akismet:

    AKISMET_API_KEY = "your_API_key"

For TypePad:

    TYPEPAD_ANTISPAM_API_KEY = "your_API_key"

6) If you want to write your own validator, create a module containing a
function that takes two arguments: a django.contrib.comments.models.Comment
and a django.http.HttpRequest. The function should either return None if it
doesn't want to make a call on the comment, or a score from 0 to 1 indicating
the probability that the comment is spam. Then just add that function to
FCCV_VALIDATORS.

Further information
===================

The project is hosted at http://bitbucket.org/fairview/fccv/. If you have
problems or questions related to it, please look there.

Acknowledgments
===============

The Akismet support is essentially this:

http://sciyoshi.com/blog/2008/aug/27/using-akismet-djangos-new-comments-framework/

I learned how to apply the Tanimoto coefficient from the excellent O'Reilly
book "Programming Collective Intelligence", by Toby Segaran. The book's a
treasure trove.
